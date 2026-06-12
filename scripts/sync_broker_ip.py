"""Sync PC LAN IP into config.py and Arduino sketch (MQTT broker host)."""

import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "src" / "config.py"
INO = ROOT / "arduino" / "esp8266_camera_tracker" / "esp8266_camera_tracker.ino"


def get_lan_ip() -> str:
    """Best-effort LAN IPv4 (same subnet ESP8266 uses)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        pass
    return "127.0.0.1"


def patch_file(path: Path, pattern: str, replacement: str) -> bool:
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(pattern, replacement, text, count=1)
    if n == 0:
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    ip = get_lan_ip()
    print(f"LAN IP: {ip}")

    changed = False
    if CONFIG.exists():
        c = patch_file(
            CONFIG,
            r'MQTT_BROKER_HOST\s*=\s*"[^"]*"',
            f'MQTT_BROKER_HOST = "{ip}"',
        )
        changed = changed or c
        print(f"  config.py: {'updated' if c else 'already OK'}")

    if INO.exists():
        c = patch_file(
            INO,
            r'const char\* mqtt_server\s*=\s*"[^"]*"',
            f'const char* mqtt_server = "{ip}"',
        )
        changed = changed or c
        print(f"  esp8266_camera_tracker.ino: {'updated' if c else 'already OK'}")

    if changed:
        print("Broker IP synced — re-upload ESP if the sketch changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
