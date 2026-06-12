#!/usr/bin/env python3
"""Shortcut: face recognition + MQTT camera tracking."""

import sys
from src.recognize_with_tracking import main

if __name__ == "__main__":
    fullscreen = "--fullscreen" in sys.argv or "-f" in sys.argv
    no_mqtt = "--no-mqtt" in sys.argv
    dashboard = "--dashboard" in sys.argv or "-d" in sys.argv
    headless = "--headless" in sys.argv
    success = main(
        start_fullscreen=fullscreen,
        enable_mqtt=not no_mqtt,
        enable_dashboard=dashboard,
        headless=headless,
    )
    sys.exit(0 if success else 1)
