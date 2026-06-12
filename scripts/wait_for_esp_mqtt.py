"""Wait until ESP8266 publishes camera/status on MQTT (after boot/flash)."""

import sys
import time

from src import config
from src.mqtt_camera_controller import MQTTCameraController


def main() -> int:
    timeout = 25.0
    print(f"Waiting up to {int(timeout)}s for ESP8266 on MQTT ({config.MQTT_TOPIC_STATUS})...")
    ctrl = MQTTCameraController()
    if not ctrl.wait_for_connection(timeout_sec=8.0):
        print("ERROR: Python cannot reach MQTT broker")
        ctrl.close()
        return 1

    deadline = time.time() + timeout
    while time.time() < deadline:
        if ctrl.last_status.get("angle") is not None:
            angle = ctrl.current_angle
            print(f"ESP online - servo at {angle} degrees")
            # Quick wiggle so you can see/hear the motor
            for test_angle in (angle + 8, angle - 8, angle):
                test_angle = max(config.SERVO_MIN_ANGLE, min(config.SERVO_MAX_ANGLE, test_angle))
                ctrl.move_to_angle(int(test_angle), force=True)
                time.sleep(1.2)
            ctrl.close()
            print("Servo wiggle test sent (motor should have moved slightly)")
            return 0
        time.sleep(0.25)

    print("WARNING: No ESP status received.")
    print("  Check: ESP powered, WiFi SSID/password in .ino, same network as PC.")
    print(f"  Broker IP in sketch must be {config.MQTT_BROKER_HOST}")
    ctrl.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
