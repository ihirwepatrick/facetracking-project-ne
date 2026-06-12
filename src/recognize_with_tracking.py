"""
Live face recognition with MQTT pan tracking and autonomous lost-target search.

State machine
-------------
IDLE      : no identity selected to lock (recognition still runs).
TRACKING  : locked target visible, servo actively centering it.
LOCKED    : locked target visible and centered/stable.
SEARCHING : locked target missing beyond LOST_TARGET_TIMEOUT — autonomous,
            direction-aware servo sweep while recognition keeps hunting for the
            ORIGINAL locked identity. Never locks anyone else.

Performance & multi-face strategy
---------------------------------
Detection runs every frame (smooth boxes). ArcFace embedding is the expensive
step, so the FaceTracker caches recognition per persistent track ID and only
re-embeds on an interval (more often for the locked track). The lock is bound
to a track ID, which prevents identity/lock switching when other known faces
appear.
"""

import sys
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import config
from . import actions as action_module
from .activity_logger import ActivityLogger
from .align import FaceAligner
from .embed import ArcFaceEmbedder
from .haar_5pt import HaarMediaPipeFaceDetector
from .face_tracker import FaceTracker
from .mqtt_camera_controller import MQTTCameraController
from .recognition_core import (
    choose_lock_identity,
    draw_tracks,
    load_database,
    open_camera,
    recognize_face,
)
from .tracking import PanTracker
from .tracking_log import TrackingLogger
from .camera_utils import CameraStream
from .dashboard_state import DashboardState, faces_from_tracks
from .dashboard_server import get_state, start_dashboard_server


def _draw_debug_overlay(
    vis: np.ndarray,
    state: str,
    lock_name: Optional[str],
    servo_angle,
    face_count: int,
    recog_fps: float,
    track_fps: float,
    mqtt_ok: bool,
    threshold: float,
    lost_for: float,
) -> None:
    """On-screen diagnostics panel (Issue #8)."""
    lines = [
        f"State: {state}",
        f"Locked: {lock_name or '(none)'}",
        f"Servo: {servo_angle}",
        f"Faces: {face_count}",
        f"Recog FPS: {recog_fps:.1f}",
        f"Track FPS: {track_fps:.1f}",
        f"MQTT: {'OK' if mqtt_ok else '--'}",
        f"Thresh: {threshold:.2f}",
    ]
    if state == "SEARCHING":
        lines.append(f"Lost for: {lost_for:.1f}s")

    font = cv2.FONT_HERSHEY_SIMPLEX
    pad = 6
    line_h = 20
    panel_w = 210
    panel_h = line_h * len(lines) + pad
    overlay = vis.copy()
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, vis, 0.55, 0, vis)

    state_color = {
        "LOCKED": config.COLOR_LOCKED,
        "TRACKING": (0, 255, 255),
        "SEARCHING": config.COLOR_LOST,
        "IDLE": (200, 200, 200),
    }.get(state, config.COLOR_HUD)

    y = pad + 14
    for i, t in enumerate(lines):
        color = state_color if i == 0 else config.COLOR_HUD
        cv2.putText(vis, t, (pad, y), font, 0.5, color, 1, cv2.LINE_AA)
        y += line_h


def _draw_search_banner(vis: np.ndarray, lock_name: str) -> None:
    text = f"SEARCHING FOR TARGET: {lock_name}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, 0.8, 2)
    x = (vis.shape[1] - tw) // 2
    y = 40
    cv2.rectangle(vis, (x - 10, y - th - 8), (x + tw + 10, y + 8), config.COLOR_LOST, -1)
    cv2.putText(vis, text, (x, y), font, 0.8, (0, 0, 0), 2, cv2.LINE_AA)


def main(
    start_fullscreen: bool = False,
    enable_mqtt: bool = True,
    mqtt_broker: str = None,
    mqtt_port: int = None,
    enable_dashboard: bool = None,
    headless: bool = None,
) -> bool:
    db = load_database()
    if not db:
        print("ERROR: No enrolled identities. Run: python -m src.enroll")
        return False

    print(f"✓ Loaded {len(db)} enrolled identities")

    detector = HaarMediaPipeFaceDetector(min_size=config.HAAR_MIN_SIZE)
    aligner = FaceAligner()
    embedder = ArcFaceEmbedder(config.ARCFACE_MODEL_PATH)

    names = sorted(db.keys())
    embeddings_matrix = np.stack([db[n].reshape(-1) for n in names], axis=0).astype(np.float32)

    lock_name: Optional[str] = choose_lock_identity(names)
    if not lock_name:
        print("WARNING: No lock selected. Running recognition only (IDLE).")

    if enable_dashboard is None:
        enable_dashboard = config.DASHBOARD_ENABLED
    if headless is None:
        headless = config.DASHBOARD_HEADLESS and enable_dashboard

    dashboard: Optional[DashboardState] = None
    if enable_dashboard:
        try:
            dashboard = get_state()
            start_dashboard_server(state=dashboard)
        except ImportError as exc:
            print(f"✗ Dashboard disabled: {exc}")
            enable_dashboard = False
        except OSError as exc:
            print(f"✗ Dashboard failed to bind port {config.DASHBOARD_PORT}: {exc}")
            enable_dashboard = False

    mqtt: Optional[MQTTCameraController] = None
    if enable_mqtt:
        mqtt = MQTTCameraController(broker_host=mqtt_broker, broker_port=mqtt_port)
        if not mqtt.wait_for_connection(timeout_sec=5.0):
            print("✗ MQTT NOT CONNECTED — servo will NOT move.")
            print(f"  Broker: {mqtt_broker or config.MQTT_BROKER_HOST}:{mqtt_port or config.MQTT_BROKER_PORT}")
            print("  Fix: run python test_mqtt_system.py  OR  python test_simple_tracking.py")
            print("  Check: broker IP reachable, ESP8266 on same WiFi, firmware flashed.")
        else:
            mqtt.center()
            print("✓ MQTT ready — servo centered to start")
            if not mqtt.wait_for_esp(timeout_sec=30.0):
                print("  Retrying ESP connection for 20s more...")
                mqtt.wait_for_esp(timeout_sec=20.0)
    tracker = FaceTracker()
    tlog = TrackingLogger(dashboard=dashboard)
    pan = PanTracker(mqtt=mqtt, logger=tlog)

    activity_logger: Optional[ActivityLogger] = None
    if lock_name:
        activity_logger = ActivityLogger(lock_name, config.HISTORY_DIR)

    cam = open_camera()
    if cam is None:
        print("ERROR: Cannot open camera.")
        print("Run: python -m src.camera_utils to find the correct camera index.")
        return False

    threshold = config.RECOGNITION_THRESHOLD
    baseline_mouth_width = None
    mouth_width_samples: List[float] = []
    last_action_frame: Dict[str, int] = {}
    frame_idx = 0
    action_display: List[Tuple[str, int]] = []
    ACTION_DISPLAY_DURATION = 15

    lost_since: Optional[float] = None
    locked_unrecog_since: Optional[float] = None  # track visible but not recognised as target
    prev_locked_track_id: Optional[int] = None
    lock_armed_at: Optional[float] = None
    state = "IDLE"

    # FPS accounting (tracking = loop rate, recognition = embeddings/sec).
    t_loop = time.time()
    loop_count = 0
    track_fps = 0.0
    recog_events = 0
    t_recog = time.time()
    recog_fps = 0.0
    last_frame = None
    camera_warning_frames = 0

    window_name = "Face Tracking"
    show_window = not headless
    if show_window:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.resizeWindow(window_name, config.DISPLAY_WINDOW_WIDTH, config.DISPLAY_WINDOW_HEIGHT)
        if start_fullscreen:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    print("\nFace Recognition + MQTT Tracking + Search")
    if enable_dashboard:
        dash_host = "127.0.0.1" if config.DASHBOARD_HOST in ("0.0.0.0", "127.0.0.1") else config.DASHBOARD_HOST
        print(f"Dashboard: http://{dash_host}:{config.DASHBOARD_PORT}")
    print("Controls: q=quit  r=reload  l=unlock  k=lock  s=search  c=center  f=fullscreen  +/-=threshold")
    if config.TRACKING_LOG_ENABLED:
        print("Tracking logs: ON (set TRACKING_LOG_ENABLED=False in config.py to disable)")
        if lock_name:
            tlog.lock_armed(lock_name)

    if lock_name:
        lock_armed_at = time.time()

    try:
        while True:
            ret, frame = cam.read()
            if not ret:
                if last_frame is None:
                    time.sleep(0.05)
                    continue
                frame = last_frame.copy()
                camera_warning_frames += 1
                if camera_warning_frames == 1:
                    print("⚠ Camera frame lost — retrying (tracking continues)...")
            else:
                last_frame = frame
                camera_warning_frames = 0

            frame_idx += 1
            loop_count += 1
            frame_w = frame.shape[1]

            # --- Detect + associate (every frame when faces/search active) ---
            search_active = (
                lock_name
                and lost_since is not None
                and (time.time() - lost_since) >= config.LOST_TARGET_TIMEOUT
            )
            tracking_active = (
                bool(tracker.visible_tracks())
                or tracker.locked_track_id is not None
                or bool(lock_name)
                or search_active
                or pan.search_manual
            )
            if lock_name or tracking_active:
                run_detect = frame_idx % config.DETECT_EVERY_N_FRAMES_FACE == 0
            else:
                run_detect = frame_idx % config.DETECT_EVERY_N_FRAMES_IDLE == 0
            if run_detect:
                detections = detector.detect(frame)[: config.MAX_FACES]
                visible = tracker.update(detections, frame_idx, frame_w)
            else:
                visible = tracker.visible_tracks()
            faces_present = bool(visible)

            # --- Recognition pass (locked track first; budget caps cost) -----
            locked = tracker.locked_track
            ordered = sorted(
                visible,
                key=lambda t: (t.track_id != tracker.locked_track_id, t.track_id),
            )
            # During active search, only re-recognise the formerly locked track
            # so the budget is not wasted on bystanders.
            is_searching_now = (state == "SEARCHING")
            budget = config.MAX_FACES_TO_PROCESS
            for tr in ordered:
                if budget <= 0:
                    break
                is_lk = tr.track_id == tracker.locked_track_id
                if is_searching_now and not is_lk:
                    # During search still process unknown faces — they might be the target
                    # returning with a new track ID — but deprioritise known bystanders.
                    if tr.accepted and tr.name != lock_name:
                        continue
                if tr.needs_recognition(frame_idx, is_lk, faces_present=faces_present):
                    name, dist, accepted = recognize_face(
                        frame, tr.landmarks, aligner, embedder,
                        embeddings_matrix, names, threshold,
                    )
                    tr.apply_recognition(name, dist, accepted, frame_idx)
                    recog_events += 1
                    budget -= 1

            # --- Lock acquisition / reacquisition --------------------------
            if lock_name and tracker.locked_track_id is None:
                candidate = tracker.acquire_lock(lock_name)
                if candidate is not None:
                    pan.reset()  # cancel search sweep; resume clean tracking
                    locked_unrecog_since = None
                    print(f"✓ Locked onto {lock_name} (track #{candidate.track_id})")

            locked = tracker.locked_track
            locked_in_frame = (
                locked is not None
                and locked.misses == 0
                and locked.track_id == tracker.locked_track_id
            )
            locked_confirmed = (
                locked_in_frame
                and locked.accepted
                and locked.name == lock_name
            )
            # --- Servo control + state machine -----------------------------
            if not lock_name:
                state = "IDLE"
                lost_since = None
                locked_unrecog_since = None
                prev_locked_track_id = None
                tlog.idle()

            elif locked_in_frame:
                # ── Locked bbox visible: center in viewport and follow movement ──
                if locked_confirmed:
                    if prev_locked_track_id is None and lost_since is not None:
                        tlog.target_visible(
                            lock_name, locked.track_id, locked.center, pan.current_angle,
                        )
                    elif prev_locked_track_id != locked.track_id:
                        tlog.target_visible(
                            lock_name, locked.track_id, locked.center, pan.current_angle,
                        )
                    lost_since = None
                    locked_unrecog_since = None
                    prev_locked_track_id = locked.track_id
                else:
                    if locked_unrecog_since is None:
                        locked_unrecog_since = time.time()
                    unrecog_for = time.time() - locked_unrecog_since
                    if unrecog_for >= config.LOST_TARGET_UNRECOGNIZED_SEC:
                        if lost_since is None:
                            lost_since = time.time()
                            prev_locked_track_id = None
                            tlog.target_lost(lock_name)
                        if state != "SEARCHING":
                            direction = (
                                "right" if pan.last_error_sign > 0
                                else "left" if pan.last_error_sign < 0
                                else "center"
                            )
                            tlog.search_started(lock_name, pan.last_known_angle, direction)
                        state = "SEARCHING"
                        pan.search()
                        locked_in_frame = False  # skip follow below

                if locked_in_frame:
                    pan.hold_locked()
                    state = "LOCKED"

            else:
                # ── Track is gone entirely ────────────────────────────────
                locked_unrecog_since = None
                in_startup_grace = (
                    lock_armed_at is not None
                    and (time.time() - lock_armed_at) < config.TRACKING_STARTUP_GRACE_SEC
                )
                if in_startup_grace:
                    state = "TRACKING"
                    lost_since = None
                    tlog.servo_hold(
                        pan.current_angle,
                        "startup grace — camera warming up",
                    )
                elif lost_since is None:
                    lost_since = time.time()
                    prev_locked_track_id = None
                    tlog.target_lost(lock_name)
                if not in_startup_grace:
                    lost_for = time.time() - lost_since
                if not in_startup_grace and (
                    lost_for >= config.LOST_TARGET_TIMEOUT or pan.search_manual
                ):
                    if state != "SEARCHING":
                        direction = (
                            "right" if pan.last_error_sign > 0
                            else "left" if pan.last_error_sign < 0
                            else "center"
                        )
                        tlog.search_started(lock_name, pan.last_known_angle, direction)
                    state = "SEARCHING"
                    pan.search()
                elif not in_startup_grace:
                    # Brief grace period — hold position before starting sweep.
                    state = "TRACKING"
                    tlog.target_still_missing(lock_name, lost_for)
                    tlog.servo_hold(
                        pan.current_angle,
                        "target out of frame — holding during grace period",
                    )

            # --- Activity logging for the locked, visible target -----------
            if (
                lock_name and activity_logger and locked_confirmed
                and frame_idx % config.ACTION_DETECT_EVERY_N_FRAMES == 0
                and locked is not None and locked.full_landmarks
            ):
                detected_actions, baseline_mouth_width, mouth_width_samples = action_module.detect_smile_blink(
                    frame, baseline_mouth_width, mouth_width_samples,
                    last_action_frame, frame_idx,
                    cooldown_frames=config.LOCK_ACTION_COOLDOWN_FRAMES,
                    landmarks_list=locked.full_landmarks,
                )
                for act in detected_actions:
                    activity_logger.log_activity(act, frame_idx, locked.center)
                    action_display.append((act.capitalize() + "!", ACTION_DISPLAY_DURATION))
                for mv in activity_logger.detect_and_log_movement(locked.center, frame_idx):
                    action_display.append((mv.replace("_", " ").title() + "!", ACTION_DISPLAY_DURATION))

            action_display = [(label, n - 1) for label, n in action_display if n > 1]

            # --- FPS counters ----------------------------------------------
            now = time.time()
            if now - t_loop >= 1.0:
                track_fps = loop_count / (now - t_loop)
                loop_count = 0
                t_loop = now
            if now - t_recog >= 1.0:
                recog_fps = recog_events / (now - t_recog)
                recog_events = 0
                t_recog = now

            # --- Render ----------------------------------------------------
            vis = frame
            draw_tracks(
                vis, visible, tracker.locked_track_id,
                searching=(state == "SEARCHING"),
                lock_name=lock_name,
            )
            if state == "SEARCHING" and lock_name:
                _draw_search_banner(vis, lock_name)

            servo_angle = f"{int(round(pan.current_angle))}" if mqtt else "-"
            _draw_debug_overlay(
                vis, state, lock_name, servo_angle, len(visible),
                recog_fps, track_fps, bool(mqtt and mqtt.is_connected),
                threshold, (time.time() - lost_since) if lost_since else 0.0,
            )

            y_action = vis.shape[0] - 16 * len(action_display) - 8
            for lbl, _ in action_display:
                cv2.putText(vis, lbl, (vis.shape[1] - 160, y_action),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
                y_action += 18

            if dashboard:
                dashboard.update_frame(vis)
                dashboard.update_telemetry(
                    state=state,
                    lock_name=lock_name,
                    servo_angle=float(pan.current_angle),
                    servo_min=config.SEARCH_MIN_ANGLE,
                    servo_max=config.SEARCH_MAX_ANGLE,
                    mqtt_connected=bool(mqtt and mqtt.is_connected),
                    face_count=len(visible),
                    track_fps=track_fps,
                    recog_fps=recog_fps,
                    threshold=threshold,
                    lost_for=(time.time() - lost_since) if lost_since else 0.0,
                    search_manual=pan.search_manual,
                    faces=faces_from_tracks(visible, tracker.locked_track_id),
                    enrolled_count=len(names),
                    frame_idx=frame_idx,
                )

            if show_window:
                cv2.imshow(window_name, vis)

            # --- Keyboard --------------------------------------------------
            if show_window:
                key = cv2.waitKey(1) & 0xFF
                if not CameraStream.is_window_open(window_name):
                    print("\nDisplay window closed — exiting.")
                    break
            else:
                key = 0xFF
                time.sleep(0.001)
            if key == ord("q"):
                break
            if key == ord("r"):
                db = load_database()
                names = sorted(db.keys())
                embeddings_matrix = np.stack([db[n].reshape(-1) for n in names], axis=0).astype(np.float32)
                if lock_name and lock_name not in names:
                    lock_name = None
                    tracker.release_lock()
                    pan.reset()
                print(f"✓ Reloaded {len(db)} identities")
            elif key == ord("l"):
                if activity_logger:
                    activity_logger.save_summary()
                    activity_logger = None
                lock_name = None
                tracker.release_lock()
                pan.reset()
                lost_since = None
                locked_unrecog_since = None
                print("Lock cleared")
            elif key == ord("k"):
                new_lock = choose_lock_identity(names)
                if new_lock:
                    lock_name = new_lock
                    tracker.release_lock()
                    pan.reset()
                    lost_since = None
                    locked_unrecog_since = None
                    if activity_logger is None:
                        activity_logger = ActivityLogger(lock_name, config.HISTORY_DIR)
                    print(f"Lock target set to {lock_name}")
            elif key == ord("s"):
                pan.toggle_search()
                print(f"Manual search: {'ON' if pan.search_manual else 'OFF'}")
            elif key == ord("c"):
                pan.force_center()
                print("Camera centered")
            elif key == ord("f"):
                prop = cv2.WND_PROP_FULLSCREEN
                cur = cv2.getWindowProperty(window_name, prop)
                cv2.setWindowProperty(
                    window_name, prop,
                    cv2.WINDOW_FULLSCREEN if cur != cv2.WINDOW_FULLSCREEN else cv2.WINDOW_NORMAL,
                )
            elif key in (ord("+"), ord("=")):
                threshold = min(1.0, threshold + 0.01)
            elif key == ord("-"):
                threshold = max(0.0, threshold - 0.01)

    finally:
        if activity_logger:
            activity_logger.save_summary()
        if mqtt:
            mqtt.close()
        detector.close()
        cam.release()
        if show_window:
            cv2.destroyAllWindows()

    print("✓ Tracking ended.")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Face recognition with MQTT camera tracking")
    parser.add_argument("--fullscreen", "-f", action="store_true")
    parser.add_argument("--no-mqtt", action="store_true", help="Disable MQTT servo control")
    parser.add_argument("--broker", type=str, default=None, help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=None, help="MQTT broker port")
    parser.add_argument("--dashboard", "-d", action="store_true", help="Enable web dashboard")
    parser.add_argument("--headless", action="store_true", help="Dashboard only (no OpenCV window)")
    args = parser.parse_args()

    ok = main(
        start_fullscreen=args.fullscreen,
        enable_mqtt=not args.no_mqtt,
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        enable_dashboard=args.dashboard,
        headless=args.headless,
    )
    sys.exit(0 if ok else 1)
