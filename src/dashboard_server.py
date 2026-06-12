"""
Web dashboard: live camera MJPEG + servo telemetry + tracking status.

Run standalone (status only):  python -m src.dashboard_server
With tracking:                 python track.py --dashboard
"""

import socket
import threading
import time
from pathlib import Path
from typing import Optional

from . import config
from .dashboard_state import DashboardState

_DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
_STATIC_DIR = _DASHBOARD_DIR / "static"
_state: Optional[DashboardState] = None
_app = None


def get_state() -> DashboardState:
    global _state
    if _state is None:
        _state = DashboardState(history_size=config.DASHBOARD_SERVO_HISTORY)
    return _state


def _mjpeg_generator():
    state = get_state()
    while True:
        jpeg = state.get_jpeg()
        if jpeg:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
        time.sleep(1.0 / max(config.DASHBOARD_STREAM_FPS, 1))


def create_app():
    try:
        from flask import Flask, Response, jsonify, send_from_directory
    except ImportError as exc:
        raise ImportError(
            "Flask is required for the dashboard. Install with: pip install flask"
        ) from exc

    # static_folder must be dashboard/static/ (not dashboard/) so /static/*.css resolves.
    app = Flask(__name__, static_folder=str(_STATIC_DIR), static_url_path="/static")

    @app.route("/")
    def index():
        return send_from_directory(_DASHBOARD_DIR, "index.html")

    @app.route("/video")
    def video():
        return Response(
            _mjpeg_generator(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/api/status")
    def api_status():
        return jsonify(get_state().get_status())

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "has_frame": get_state().get_jpeg() is not None})

    return app


def _wait_for_listen(host: str, port: int, timeout: float = 5.0) -> bool:
    """Wait until the dashboard port accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host if host != "0.0.0.0" else "127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def start_dashboard_server(
    host: str = None,
    port: int = None,
    state: DashboardState = None,
) -> threading.Thread:
    """Start Flask in a background daemon thread."""
    global _state, _app
    if state is not None:
        _state = state
    host = host or config.DASHBOARD_HOST
    port = port or config.DASHBOARD_PORT

    if not _DASHBOARD_DIR.is_dir():
        raise FileNotFoundError(f"Dashboard directory missing: {_DASHBOARD_DIR}")
    if not (_STATIC_DIR / "dashboard.css").is_file():
        raise FileNotFoundError(f"Dashboard static files missing: {_STATIC_DIR}")

    _app = create_app()

    def _run():
        # suppress Flask startup banner in the tracking terminal
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.WARNING)
        _app.run(host=host, port=port, threaded=True, use_reloader=False)

    thread = threading.Thread(target=_run, name="FaceLockingDashboard", daemon=True)
    thread.start()

    if _wait_for_listen(host, port):
        display_host = "127.0.0.1" if host == "0.0.0.0" else host
        print(f"✓ Dashboard ready: http://{display_host}:{port}")
    else:
        print(f"✗ Dashboard failed to start on {host}:{port} (port in use or Flask error)")

    return thread


if __name__ == "__main__":
    start_dashboard_server()
    print("Dashboard running (no video until tracking starts). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")
