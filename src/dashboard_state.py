"""
Thread-safe shared state between the tracking loop and the web dashboard.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any, Deque, Dict, List, Optional

import cv2
import numpy as np


@dataclass
class FaceInfo:
    track_id: int = -1
    name: str = "Unknown"
    confidence: float = 0.0
    accepted: bool = False
    locked: bool = False
    bbox: List[int] = field(default_factory=list)


@dataclass
class ServoEvent:
    ts: float
    from_angle: float
    to_angle: float
    reason: str


class DashboardState:
    """Latest frame + telemetry for the dashboard HTTP server."""

    def __init__(self, history_size: int = 40):
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._telemetry: Dict[str, Any] = {
            "state": "IDLE",
            "lock_name": None,
            "servo_angle": 90.0,
            "servo_min": 0,
            "servo_max": 180,
            "mqtt_connected": False,
            "face_count": 0,
            "track_fps": 0.0,
            "recog_fps": 0.0,
            "threshold": 0.0,
            "lost_for": 0.0,
            "search_manual": False,
            "faces": [],
            "enrolled_count": 0,
            "frame_idx": 0,
        }
        self._servo_history: Deque[ServoEvent] = deque(maxlen=history_size)
        self._log_lines: Deque[str] = deque(maxlen=80)

    def update_frame(self, frame_bgr: np.ndarray, quality: int = 72) -> None:
        ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            return
        with self._lock:
            self._jpeg = buf.tobytes()

    def get_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    def update_telemetry(self, **kwargs) -> None:
        with self._lock:
            self._telemetry.update(kwargs)
            self._telemetry["updated_at"] = time.time()

    def add_servo_event(self, from_angle: float, to_angle: float, reason: str) -> None:
        evt = ServoEvent(time.time(), from_angle, to_angle, reason)
        with self._lock:
            self._servo_history.appendleft(evt)

    def add_log(self, line: str) -> None:
        with self._lock:
            self._log_lines.appendleft(f"{time.strftime('%H:%M:%S')} {line}")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            status = dict(self._telemetry)
            status["servo_history"] = [asdict(e) for e in self._servo_history]
            status["logs"] = list(self._log_lines)
            return status


def faces_from_tracks(visible, locked_track_id: Optional[int]) -> List[Dict[str, Any]]:
    """Serialize visible FaceTracker tracks for the dashboard API."""
    return [
        {
            "track_id": t.track_id,
            "name": t.name,
            "confidence": round(t.confidence, 3),
            "accepted": t.accepted,
            "locked": t.track_id == locked_track_id,
            "bbox": list(t.bbox),
        }
        for t in visible
    ]
