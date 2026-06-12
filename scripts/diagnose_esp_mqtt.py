#!/usr/bin/env python3
"""Diagnose why ESP8266 is not publishing camera/status on MQTT."""

import socket
import sys
import time

from src import config
from src.mqtt_camera_controller import MQTTCameraController


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "?"


def tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except OSError as exc:
        print(f"  TCP {host}:{port} FAILED — {exc}")
        return False


def main() -> int:
    ip = lan_ip()
    print("=== FaceLocking ESP / MQTT diagnosis ===\n")
    print(f"PC LAN IP (broker host): {ip}")
    print(f"config MQTT_BROKER_HOST: {config.MQTT_BROKER_HOST}")
    if ip != config.MQTT_BROKER_HOST and ip != "?":
        print("  WARNING: config IP differs from current LAN IP — run: python scripts/sync_broker_ip.py")

    print("\nBroker port checks:")
    tcp_ok("127.0.0.1", config.MQTT_BROKER_PORT)
    tcp_ok(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT)

    print("\nListening for ESP camera/status (45s)...")
    print("  Open Arduino Serial Monitor 115200 on COM5 — look for:")
    print("    'WiFi connected' and 'Broker TCP: OK' and 'MQTT connected'")
    print("  If 'Broker TCP: FAILED' -> router may block WiFi-to-WiFi (AP isolation).")
    print("    Fix: plug PC into router with Ethernet, OR disable AP/client isolation.\n")

    ctrl = MQTTCameraController()
    ctrl.wait_for_connection(8)
    ok = ctrl.wait_for_esp(45)
    ctrl.close()

    if ok:
        print("\nRESULT: ESP is online on MQTT.")
        return 0

    print("\nRESULT: ESP still offline.")
    print("Checklist:")
    print("  1. ESP powered (USB), tap RESET")
    print("  2. WiFi SSID 'Stay Hydrated' (2.4 GHz, not 5 GHz-only)")
    print("  3. Re-flash: .\\upload_esp8266.ps1 -Port COM5  (do NOT skip after failed upload)")
    print("  4. Admin once: setup_mqtt_broker.bat")
    print("  5. AP isolation: use Ethernet for PC or disable client isolation on router")
    return 1


if __name__ == "__main__":
    sys.exit(main())
