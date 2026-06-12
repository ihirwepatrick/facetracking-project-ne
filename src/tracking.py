"""
Pan tracking controller for the MQTT servo camera.

Responsibilities
----------------
TRACKING: Keep the locked face centered using a PID controller on the
  normalised horizontal error, with:
  - pixel dead zone (no micro-jitter when centred)
  - EMA smoothing on both the raw error AND the commanded output angle
  - per-update rate limit so the servo never jumps violently
  - SERVO_OUTPUT_SMOOTHING applied to the final angle command → smooth motion

SEARCH: When the locked target is lost (or has been unrecognised too long),
  run an autonomous direction-aware expanding sweep that keeps publishing
  servo waypoints until the target is reacquired.  The sweep is time-driven
  (not frame-driven) and loops indefinitely — it will NEVER stop until
  pan.reset() is called by the caller when the target returns.

Key design rules
----------------
- Servo control is ONLY ever driven by the locked face.  Other known faces
  have zero influence on the PanTracker.
- Search mode runs unconditionally once started; it is the caller's
  responsibility to call pan.reset() (which cancels search) when the target
  is reacquired.
- Output-angle EMA (SERVO_OUTPUT_SMOOTHING) is applied after the PID so the
  angle command changes smoothly even when the PID output jumps.
"""

import time
from typing import List, Optional, Tuple, TYPE_CHECKING

from . import config
from .mqtt_camera_controller import MQTTCameraController

if TYPE_CHECKING:
    from .tracking_log import TrackingLogger


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class PanTracker:
    """Maps a locked face's horizontal position to smooth servo motion."""

    def __init__(
        self,
        mqtt: Optional[MQTTCameraController] = None,
        logger: Optional["TrackingLogger"] = None,
    ):
        self.mqtt = mqtt
        self.log = logger

        # PID state
        self.smoothed_error: Optional[float] = None
        self.prev_error: float = 0.0
        self.integral: float = 0.0
        self.target_angle: float = float(config.SERVO_CENTER_ANGLE)

        # EMA on the OUTPUT angle command — prevents jitter / sudden jumps.
        self._smooth_angle: Optional[float] = None

        # Centering state
        self.frames_in_center = 0
        self.center_locked = False

        # Reacquisition memory — which side did the face exit from?
        self.last_error_sign: int = 0
        self.last_known_angle: float = float(config.SERVO_CENTER_ANGLE)

        # Search state
        self.search_manual = False
        self._search_waypoints: List[int] = []
        self._search_index = 0
        self._last_search_step_time = 0.0
        self._last_search_angle: Optional[int] = None
        self._endpoint_dwell_until = 0.0
        self._search_stuck_since = None
        self._search_stuck_angle = None
        self._search_dir = 1
        self._search_step_count = 0

    # ------------------------------------------------------------------ utils
    def reset(self) -> None:
        """Cancel any active search and reset PID + smoothing state."""
        self.smoothed_error = None
        self.prev_error = 0.0
        self.integral = 0.0
        self._smooth_angle = None
        self.frames_in_center = 0
        self.center_locked = False
        self.search_manual = False
        self._search_waypoints = []
        self._search_index = 0
        self._last_search_angle = None
        self._endpoint_dwell_until = 0.0
        self._search_stuck_since = None
        self._search_stuck_angle = None
        self._search_dir = 1
        self._search_step_count = 0

    @property
    def current_angle(self) -> float:
        """Last angle acknowledged by the MQTT controller (or our local target)."""
        if self.mqtt:
            return float(self.mqtt.current_angle)
        return self.target_angle

    def normalized_error(self, face_center_x: float, frame_width: int) -> float:
        return (face_center_x - frame_width / 2.0) / (frame_width / 2.0)

    def _in_dead_zone(self, face_center_x: float, frame_width: int) -> bool:
        """Return True only if face is within CENTER_DEAD_ZONE pixels of frame centre."""
        return abs(face_center_x - frame_width / 2.0) < config.CENTER_DEAD_ZONE

    def in_center_zone(self, error: float) -> bool:
        return abs(error) < config.CENTERING_TOLERANCE

    # ---------------------------------------------------------------- tracking
    def track(self, face_center_x: float, frame_width: int) -> Tuple[str, Optional[int]]:
        """
        PID-control the servo to centre the locked face.

        Returns (state_label, commanded_angle | None).
        state_label is one of: "centered", "tracking".
        """
        # Cancel any active search the instant we have a confirmed target.
        if self._search_waypoints:
            self._search_waypoints = []
            self._search_index = 0

        raw_error = self.normalized_error(face_center_x, frame_width)

        # Remember exit direction for later search bias.
        if abs(raw_error) > config.CENTERING_TOLERANCE:
            self.last_error_sign = 1 if raw_error > 0 else -1
        self.last_known_angle = self.current_angle

        # Centering state bookkeeping.
        if self.in_center_zone(raw_error):
            self.frames_in_center += 1
            self.center_locked = self.frames_in_center >= config.FRAMES_TO_LOCK_CENTER
        else:
            self.frames_in_center = 0
            self.center_locked = False

        # Dead zone: do not chase micro-offsets (prevents jitter at centre).
        if self._in_dead_zone(face_center_x, frame_width):
            self.prev_error = raw_error
            self.integral = 0.0
            label = "centered" if self.center_locked else "tracking"
            if self.log:
                reason = "face centred in dead zone" if self.center_locked else "within dead zone"
                self.log.servo_hold(self.current_angle, reason)
            return (label, None)

        # EMA on raw error — attenuates detection noise.
        a = config.SMOOTHING_FACTOR
        if self.smoothed_error is None:
            self.smoothed_error = raw_error
        else:
            self.smoothed_error = a * raw_error + (1.0 - a) * self.smoothed_error
        error = self.smoothed_error

        # PID terms.
        ki = config.SERVO_PID_KI
        if ki > 0:
            clamp_val = config.SERVO_PID_I_CLAMP / ki
            self.integral = _clamp(self.integral + error, -clamp_val, clamp_val)
        else:
            self.integral = 0.0

        derivative = error - self.prev_error
        self.prev_error = error

        delta = (
            config.SERVO_PID_KP * error
            + config.SERVO_PID_KI * self.integral
            + config.SERVO_PID_KD * derivative
        )
        delta *= config.SERVO_DIRECTION_SIGN

        # Rate limit — prevents violent servo jumps.
        delta = _clamp(delta, -config.SERVO_MAX_SPEED, config.SERVO_MAX_SPEED)

        desired_angle = _clamp(
            self.current_angle + delta,
            config.SERVO_MIN_ANGLE,
            config.SERVO_MAX_ANGLE,
        )
        self.target_angle = desired_angle

        # Output-angle EMA — smooths the command sent to the servo so motion
        # is fluid even when the PID output jumps.
        alpha = config.SERVO_OUTPUT_SMOOTHING
        if self._smooth_angle is None:
            self._smooth_angle = desired_angle
        else:
            self._smooth_angle = self._smooth_angle + alpha * (desired_angle - self._smooth_angle)

        commanded = None
        command_angle = int(round(self._smooth_angle))
        from_angle = self.current_angle

        if not self.mqtt:
            if self.log:
                self.log.servo_hold(from_angle, "MQTT not connected")
            return ("tracking", None)

        # Skip tiny corrections (face already centered in dead zone handled above).
        if abs(command_angle - from_angle) < config.SERVO_MIN_COMMAND_DELTA:
            if self.log:
                self.log.servo_hold(from_angle, "follow — within command threshold")
            return ("centered" if self.center_locked else "tracking", None)

        if self.mqtt.move_to_angle(command_angle):
            commanded = command_angle
            if self.log:
                side = "right" if raw_error > 0 else "left"
                self.log.servo_move(
                    from_angle, command_angle,
                    f"centering face ({side}, err={raw_error:+.2f})",
                )
        elif self.log:
            if abs(command_angle - self.mqtt._last_command_angle) < 2:
                self.log.servo_hold(from_angle, "command already sent")
            else:
                self.log.servo_hold(from_angle, "rate limited or command skipped")

        return ("tracking", commanded)

    # ------------------------------------------------------------------ search
    def _build_search_waypoints(self) -> List[int]:
        """Slow ping-pong: 0° → 180° → 0° → … (full range, no expand jitter)."""
        lo = config.SEARCH_MIN_ANGLE
        hi = config.SEARCH_MAX_ANGLE
        step = max(1, config.SEARCH_SWEEP_STEP)

        forward = list(range(lo, hi + 1, step))
        if not forward or forward[-1] != hi:
            forward.append(hi)

        backward = list(range(hi - step, lo - 1, -step))
        if not backward or backward[-1] != lo:
            backward.append(lo)

        return forward + backward

    def _servo_caught_up(self) -> bool:
        """True when ESP reported angle is close to the last command we sent."""
        if not self.mqtt:
            return True
        # No ESP status (WiFi/MQTT down) — pace by timer only; still publish commands.
        if not self.mqtt.esp_is_online:
            return True
        pending = abs(int(self.mqtt.current_angle) - int(self.mqtt._last_command_angle))
        if pending <= config.SEARCH_SWEEP_CATCHUP_DEG:
            self._search_stuck_since = None
            self._search_stuck_angle = None
            return True
        now = time.time()
        reported = int(self.mqtt.current_angle)
        if self._search_stuck_angle != reported:
            self._search_stuck_angle = reported
            self._search_stuck_since = now
        elif self._search_stuck_since is None:
            self._search_stuck_since = now
        return False

    def _search_resend_if_stuck(self) -> bool:
        """Re-publish last command if the servo has not moved for a long time."""
        if not self.mqtt or not self.mqtt.esp_is_online:
            return False
        if self._search_stuck_since is None:
            return False
        if (time.time() - self._search_stuck_since) < config.SEARCH_STUCK_TIMEOUT_SEC:
            return False
        angle = int(self.mqtt._last_command_angle)
        self.mqtt._last_publish_ms = 0.0  # bypass rate limit for resend
        return self.mqtt.move_to_angle(angle, force=True, search_step=True)

    def hold_locked(self) -> Tuple[str, None]:
        """Cancel search and hold servo (used during grace / idle)."""
        if self._search_waypoints:
            self.reset()
        return ("centered", None)

    def search(self) -> Tuple[str, Optional[int]]:
        """
        Slow ping-pong search from the ESP's *actual* reported angle.

        Each step moves SEARCH_SWEEP_STEP degrees toward 180 or 0.  The next
        command is sent only after the servo catches up — no command flooding.
        """
        if not self._search_waypoints:
            self.smoothed_error = None
            self._smooth_angle = None
            self.integral = 0.0
            self.center_locked = False
            self.frames_in_center = 0
            self._search_waypoints = [1]  # sentinel: search episode active
            self._search_index = 0
            self._search_step_count = 0
            self._last_search_step_time = 0.0
            lo, hi = config.SEARCH_MIN_ANGLE, config.SEARCH_MAX_ANGLE
            cur = int(self.current_angle)
            if cur >= (lo + hi) // 2:
                self._search_dir = -1
            elif self.last_error_sign > 0:
                self._search_dir = 1
            elif self.last_error_sign < 0:
                self._search_dir = -1
            else:
                self._search_dir = -1 if cur > 90 else 1
            if self.mqtt and not self.mqtt.esp_is_online:
                print(
                    "⚠ ESP8266 not on MQTT — commands sent but motor may not move. "
                    "Check ESP power, WiFi 'Stay Hydrated', broker 192.168.8.105"
                )

        if not self.mqtt:
            if self.log:
                self.log.servo_hold(self.current_angle, "search paused — MQTT not connected")
            return ("searching", None)

        now = time.time()
        if now < self._endpoint_dwell_until:
            if self.log:
                self.log.servo_hold(self.current_angle, "search dwell at endpoint")
            return ("searching", None)

        if not self._servo_caught_up():
            if self._search_resend_if_stuck():
                if self.log:
                    self.log.servo_search_step(
                        self.current_angle,
                        int(self.mqtt._last_command_angle),
                        self._search_step_count,
                    )
            elif self.log:
                self.log.servo_hold(
                    self.current_angle,
                    f"search — moving toward {int(self.mqtt._last_command_angle)}°",
                )
            return ("searching", None)

        step_interval = config.SEARCH_SWEEP_STEP / max(config.SEARCH_SWEEP_SPEED, 1e-3)
        if now - self._last_search_step_time < step_interval:
            return ("searching", None)

        lo, hi = config.SEARCH_MIN_ANGLE, config.SEARCH_MAX_ANGLE
        step = max(1, config.SEARCH_SWEEP_STEP)
        from_angle = int(self.current_angle)
        next_angle = from_angle + self._search_dir * step

        if next_angle >= hi:
            next_angle = hi
            self._search_dir = -1
            self._endpoint_dwell_until = now + config.SEARCH_ENDPOINT_DWELL_SEC
        elif next_angle <= lo:
            next_angle = lo
            self._search_dir = 1
            self._endpoint_dwell_until = now + config.SEARCH_ENDPOINT_DWELL_SEC

        at_endpoint = next_angle in (lo, hi)
        if self.mqtt.move_to_angle(next_angle, force=at_endpoint, search_step=True):
            self._search_step_count += 1
            self._last_search_step_time = now
            self._last_search_angle = next_angle
            if self.log:
                self.log.servo_search_step(from_angle, next_angle, self._search_step_count)
            return ("searching", next_angle)

        if self.log:
            self.log.servo_hold(from_angle, "search — waiting to send next step")
        return ("searching", None)

    # ------------------------------------------------------------------ manual
    def toggle_search(self) -> None:
        """Toggle manual search mode (keyboard shortcut 's')."""
        self.search_manual = not self.search_manual
        if self.search_manual:
            self._search_waypoints = []
            self._search_index = 0

    def force_center(self) -> None:
        """Center the servo immediately (keyboard shortcut 'c')."""
        self.reset()
        self.target_angle = float(config.SERVO_CENTER_ANGLE)
        if self.mqtt:
            self.mqtt.center()
