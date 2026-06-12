"""
MQTT camera controller — publishes pan commands to ESP8266 servo firmware.
"""

import json
import time
from typing import Optional

import paho.mqtt.client as mqtt

from . import config


class MQTTCameraController:
    """Control camera servo via MQTT."""

    def __init__(
        self,
        broker_host: str = None,
        broker_port: int = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.broker_host = broker_host or config.MQTT_BROKER_HOST
        self.broker_port = broker_port or config.MQTT_BROKER_PORT
        self.username = username if username is not None else config.MQTT_USERNAME
        self.password = password if password is not None else config.MQTT_PASSWORD

        self.topic_horizontal = config.MQTT_TOPIC_HORIZONTAL
        self.topic_command = config.MQTT_TOPIC_COMMAND
        self.topic_status = config.MQTT_TOPIC_STATUS

        self.current_angle = config.SERVO_CENTER_ANGLE
        self._last_command_angle = config.SERVO_CENTER_ANGLE
        self.is_connected = False
        self.last_status: dict = {}
        self._last_publish_ms = 0.0
        self._last_status_time = 0.0

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="FaceLocking_Controller",
        )
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=config.MQTT_KEEPALIVE)
            self.client.loop_start()
            print(f"✓ MQTT connecting to {self.broker_host}:{self.broker_port}")
        except Exception as exc:
            print(f"✗ MQTT connection failed: {exc}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            client.subscribe(self.topic_status, qos=config.MQTT_QOS)
            print(f"✓ MQTT connected, subscribed to {self.topic_status}")
        else:
            print(f"✗ MQTT connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.is_connected = False
        if rc != 0:
            print(f"⚠ MQTT disconnected rc={rc}")

    def _on_message(self, client, userdata, msg):
        if msg.topic != self.topic_status:
            return
        try:
            payload = msg.payload.decode()
            if payload.startswith("{"):
                self.last_status = json.loads(payload)
            else:
                self.last_status = {"raw": payload}
            angle = self.last_status.get("angle")
            if angle is not None:
                self.current_angle = int(angle)
                self._last_status_time = time.time()
        except Exception:
            pass

    @property
    def esp_is_online(self) -> bool:
        if self._last_status_time <= 0:
            return False
        return (time.time() - self._last_status_time) < config.ESP_STATUS_TIMEOUT_SEC

    def _rate_limited(self, interval_ms: Optional[float] = None) -> bool:
        min_ms = config.MQTT_MIN_COMMAND_INTERVAL_MS if interval_ms is None else interval_ms
        now = time.time() * 1000.0
        if now - self._last_publish_ms < min_ms:
            return True
        self._last_publish_ms = now
        return False

    def _publish(self, topic: str, payload: str, interval_ms: Optional[float] = None) -> bool:
        if not self.is_connected:
            return False
        if self._rate_limited(interval_ms):
            return False
        result = self.client.publish(topic, payload, qos=config.MQTT_QOS)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    @property
    def is_servo_moving(self) -> bool:
        """True when ESP reports the servo is still travelling to target."""
        return bool(self.last_status.get("moving"))

    def move_to_angle(self, angle: int, force: bool = False, search_step: bool = False) -> bool:
        angle = int(max(config.SERVO_MIN_ANGLE, min(config.SERVO_MAX_ANGLE, angle)))
        # Dedupe by last command sent; real position comes from ESP status topic.
        if angle == self._last_command_angle and not force:
            return False
        if not force and abs(angle - self._last_command_angle) < config.SERVO_MIN_COMMAND_DELTA:
            return False
        interval = config.MQTT_SEARCH_COMMAND_INTERVAL_MS if search_step else None
        ok = self._publish(self.topic_horizontal, str(angle), interval_ms=interval)
        if ok:
            self._last_command_angle = angle
        return ok

    def send_command(self, command: str) -> bool:
        return self._publish(self.topic_command, command)

    def move_left(self, step: int = None) -> bool:
        step = step or config.SERVO_STEP_SIZE
        return self.move_to_angle(self.current_angle - step)

    def move_right(self, step: int = None) -> bool:
        step = step or config.SERVO_STEP_SIZE
        return self.move_to_angle(self.current_angle + step)

    def center(self) -> bool:
        return self.move_to_angle(config.SERVO_CENTER_ANGLE)

    def wait_for_connection(self, timeout_sec: float = 5.0) -> bool:
        """Block until connected or timeout (connect is async via loop_start)."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.is_connected:
                return True
            time.sleep(0.1)
        return self.is_connected

    def wait_for_esp(self, timeout_sec: float = 25.0) -> bool:
        """Wait until ESP publishes camera/status (WiFi + MQTT on device)."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.esp_is_online:
                print(f"✓ ESP8266 online — servo reported at {self.current_angle}°")
                return True
            time.sleep(0.4)
        print("⚠ ESP8266 NOT on MQTT — servo will NOT move until it connects.")
        print(f"  Broker: {self.broker_host}:{self.broker_port}")
        print("  Fix: 1) ESP USB powered  2) WiFi 'Stay Hydrated'  3) Reset ESP button")
        print("  Test: python debug_mqtt_tracking.py   (should see camera/status messages)")
        return False

    def close(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
