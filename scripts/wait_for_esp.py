#!/usr/bin/env python3
"""Wait until ESP8266 publishes camera/status on MQTT (used by start_all.ps1)."""

import socket
import sys
import time

from src.mqtt_camera_controller import MQTTCameraController


def check_broker_port() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", 1883))
        s.close()
        print("Python MQTT port check: OK")
        return True
    except OSError as exc:
        print(f"Python MQTT port check: FAILED — {exc}")
        return False


def main() -> int:
    if not check_broker_port():
        return 1

    ctrl = MQTTCameraController()
    ctrl.wait_for_connection(10)
    ok = False
    for attempt in range(3):
        if ctrl.wait_for_esp(30):
            ok = True
            break
        if attempt < 2:
            print("  ESP not seen yet — tap RESET on NodeMCU, retrying...")
            time.sleep(5)
    if not ok:
        print("  Still offline: Serial Monitor 115200 on COM5 shows WiFi/MQTT errors.")
        print("  If upload failed earlier, run: .\\upload_esp8266.ps1 -Port COM5")
        print("  If Broker TCP fails on ESP -> setup_mqtt_broker.bat as Administrator.")
    ctrl.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
