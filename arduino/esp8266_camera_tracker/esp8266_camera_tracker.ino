/*
 * ESP8266 Camera Tracker with Servo Motor
 * 
 * This Arduino sketch controls a servo motor to track a person's face
 * based on MQTT commands received from the Python face recognition system.
 * 
 * Hardware:
 * - ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
 * - Servo motor (SG90 or similar)
 * - Camera mounted on servo
 * 
 * Connections:
 * - Servo Signal -> D4 (GPIO2)
 * - Servo VCC -> 5V
 * - Servo GND -> GND
 * 
 * MQTT Topics:
 * - camera/track/horizontal - Receives horizontal position (0-180 degrees)
 * - camera/track/command - Receives movement commands (left, right, center)
 * - camera/status - Publishes current servo position
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Servo.h>

// ============================================================================
// CONFIGURATION - MODIFY THESE VALUES
// ============================================================================

// WiFi credentials
const char* ssid = "Stay Hydrated";
const char* password = "stayhydratedforlife";

// const char* ssid = "EdNet";
// const char* password = "Huawei@123";

// MQTT Broker settings
const char* mqtt_server = "192.168.8.105";  // Your PC LAN IP (same as src/config.py MQTT_BROKER_HOST)
const int mqtt_port = 1883;
const char* mqtt_user = "";  // Leave empty if no authentication
const char* mqtt_password = "";

// MQTT Topics
const char* topic_horizontal = "camera/track/horizontal";
const char* topic_command = "camera/track/command";
const char* topic_status = "camera/status";

// Servo settings
const int SERVO_PIN = 2;  // GPIO2 = NodeMCU D4; do NOT use GPIO12 (D6) — breaks upload with servo wired
const int SERVO_MIN_ANGLE = 0;
const int SERVO_MAX_ANGLE = 180;
const int SERVO_CENTER_ANGLE = 90;
const int SERVO_STEP_SIZE = 10;  // Degrees per movement command

// Movement — smooth pan/search (no Serial spam in mqtt_callback or loop blocks servo)
const int MOVEMENT_DELAY = 10;      // ms between servo updates
const int SERVO_FAST_STEP = 3;      // degrees per tick when far from target
const int SERVO_MID_STEP = 2;       // degrees per tick when moderately off
const int SERVO_FINE_STEP = 1;      // degrees per tick when nearly there
const int SERVO_MIN_TARGET_DELTA = 1;  // ignore duplicate MQTT targets only

// Debug mode (set false for faster runtime — serial delays slow the servo loop)
#define DEBUG false
const int SERIAL_PRINT_DELAY = 5;

#if DEBUG
void serialPause() { delay(SERIAL_PRINT_DELAY); }
#else
void serialPause() {}
#endif

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

WiFiClient espClient;
PubSubClient client(espClient);
Servo cameraServo;

int currentAngle = SERVO_CENTER_ANGLE;
int targetAngle = SERVO_CENTER_ANGLE;
unsigned long lastStatusUpdate = 0;
const unsigned long STATUS_UPDATE_INTERVAL = 150;  // Frequent status so Python tracks real angle
unsigned long lastMqttAttempt = 0;
unsigned long lastWifiAttempt = 0;
const unsigned long MQTT_RETRY_MS = 3000;
const unsigned long WIFI_RETRY_MS = 5000;

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.println("\n\n=================================");
  Serial.println("ESP8266 Camera Tracker Starting");
  Serial.println("=================================\n");

  // Initialize servo
  cameraServo.attach(SERVO_PIN);
  cameraServo.write(SERVO_CENTER_ANGLE);
  currentAngle = SERVO_CENTER_ANGLE;
  targetAngle = SERVO_CENTER_ANGLE;
  Serial.println("✓ Servo initialized at center position");

  // Connect to WiFi
  setup_wifi();

  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqtt_callback);
  client.setSocketTimeout(15);

  Serial.println("\n✓ Setup complete!");
  Serial.println("Waiting for MQTT commands...\n");
}

// ============================================================================
// WIFI SETUP
// ============================================================================

bool tcpBrokerReachable() {
  WiFiClient probe;
  probe.setTimeout(5000);
  bool ok = probe.connect(mqtt_server, mqtt_port);
  if (ok) {
    probe.stop();
  }
  return ok;
}

void setup_wifi() {
  delay(10);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("  IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("  MQTT broker: ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.println(mqtt_port);
    Serial.print("  Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n✗ WiFi connection failed!");
    Serial.println("  Check SSID/password and use 2.4 GHz WiFi (ESP8266 cannot use 5 GHz)");
  }
}

bool ensure_wifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }
  unsigned long now = millis();
  if (now - lastWifiAttempt < WIFI_RETRY_MS) {
    return false;
  }
  lastWifiAttempt = now;
  Serial.println("WiFi lost — reconnecting...");
  WiFi.disconnect();
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("✓ WiFi back: ");
    Serial.println(WiFi.localIP());
    return true;
  }
  Serial.println("✗ WiFi still down");
  return false;
}

// ============================================================================
// MQTT RECONNECT
// ============================================================================

void onMqttConnected() {
  client.subscribe(topic_horizontal);
  client.subscribe(topic_command);
  Serial.println("✓ MQTT connected and subscribed");
  publishStatus();
}

void mqttMaintain() {
  if (client.connected()) {
    return;
  }

  unsigned long now = millis();
  if (now - lastMqttAttempt < MQTT_RETRY_MS) {
    return;
  }
  lastMqttAttempt = now;

  if (!ensure_wifi()) {
    return;
  }

  if (!tcpBrokerReachable()) {
    Serial.print("✗ Cannot reach broker ");
    Serial.print(mqtt_server);
    Serial.println(" — run setup_mqtt_broker.bat as Admin on the PC");
    return;
  }

  Serial.print("MQTT connect ");
  Serial.print(mqtt_server);
  Serial.print(":");
  Serial.println(mqtt_port);

  String clientId = "ESP8266_CameraTracker_";
  clientId += String(random(0xffff), HEX);

  if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
    Serial.println("✓ MQTT connected!");
    onMqttConnected();
  } else {
    Serial.print("✗ MQTT failed rc=");
    Serial.print(client.state());
    Serial.print(" WiFi=");
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println(WiFi.localIP());
    } else {
      Serial.println("DOWN");
    }
  }
}

// ============================================================================
// MESSAGE PARSING — plain text or JSON {"angle":N} / {"command":"left"}
// ============================================================================

int parseAngleFromMessage(const String& message) {
  String trimmed = message;
  trimmed.trim();
  if (trimmed.startsWith("{")) {
    int keyPos = trimmed.indexOf("\"angle\"");
    if (keyPos >= 0) {
      int colonPos = trimmed.indexOf(':', keyPos);
      if (colonPos >= 0) {
        return trimmed.substring(colonPos + 1).toInt();
      }
    }
    return -1;
  }
  return trimmed.toInt();
}

String parseCommandFromMessage(const String& message) {
  String trimmed = message;
  trimmed.trim();
  if (trimmed.startsWith("{")) {
    int keyPos = trimmed.indexOf("\"command\"");
    if (keyPos >= 0) {
      int colonPos = trimmed.indexOf(':', keyPos);
      if (colonPos >= 0) {
        int quoteStart = trimmed.indexOf('"', colonPos + 1);
        int quoteEnd = trimmed.indexOf('"', quoteStart + 1);
        if (quoteStart >= 0 && quoteEnd > quoteStart) {
          return trimmed.substring(quoteStart + 1, quoteEnd);
        }
      }
    }
    return "";
  }
  return trimmed;
}

// ============================================================================
// MQTT CALLBACK - Handle incoming messages
// ============================================================================

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  // Convert payload to string
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  // Handle horizontal position (degrees) — no Serial here (blocks servo loop)
  if (strcmp(topic, topic_horizontal) == 0) {
    int angle = parseAngleFromMessage(message);
    if (angle >= SERVO_MIN_ANGLE && angle <= SERVO_MAX_ANGLE) {
      if (abs(angle - targetAngle) >= SERVO_MIN_TARGET_DELTA
          || angle == SERVO_MIN_ANGLE || angle == SERVO_MAX_ANGLE) {
        targetAngle = angle;
      }
      if (DEBUG) {
        Serial.print("Target angle: ");
        Serial.println(targetAngle);
        serialPause();
      }
    }
    return;
  }

  // Handle movement commands (left, right, center)
  if (strcmp(topic, topic_command) == 0) {
    String command = parseCommandFromMessage(message);
    command.toLowerCase();

    if (command == "left" || command == "move_left") {
      targetAngle = constrain(currentAngle - SERVO_STEP_SIZE, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    } else if (command == "right" || command == "move_right") {
      targetAngle = constrain(currentAngle + SERVO_STEP_SIZE, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    } else if (command == "center") {
      targetAngle = SERVO_CENTER_ANGLE;
    }
    if (DEBUG) {
      Serial.print("Command ");
      Serial.print(command);
      Serial.print(" -> ");
      Serial.println(targetAngle);
      serialPause();
    }
  }
}

// ============================================================================
// SMOOTH SERVO MOVEMENT
// ============================================================================
int servoStepForDelta(int diff) {
  int ad = abs(diff);
  if (ad > 20) return SERVO_FAST_STEP;
  if (ad > 8) return SERVO_MID_STEP;
  return SERVO_FINE_STEP;
}

void updateServoPosition() {
  if (currentAngle == targetAngle) {
    return;
  }

  int diff = targetAngle - currentAngle;
  int step = servoStepForDelta(diff);
  if (diff > 0) {
    currentAngle = min(currentAngle + step, targetAngle);
  } else {
    currentAngle = max(currentAngle - step, targetAngle);
  }

  cameraServo.write(currentAngle);
  delay(MOVEMENT_DELAY);

  if (currentAngle == targetAngle) {
    if (DEBUG) {
      Serial.print("Movement complete at ");
      Serial.println(currentAngle);
      serialPause();
    }
    publishStatus();
  }
}

// ============================================================================
// PUBLISH STATUS
// ============================================================================

void publishStatus() {
  String status = "{\"angle\":" + String(currentAngle) + 
                  ",\"target\":" + String(targetAngle) + 
                  ",\"moving\":" + (currentAngle != targetAngle ? "true" : "false") + "}";

  client.publish(topic_status, status.c_str());

  if (DEBUG) {
    Serial.print("📤 Published Status: ");
    Serial.println(status);
    serialPause();
  }
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  mqttMaintain();
  client.loop();

  // Update servo position smoothly
  updateServoPosition();

  // Publish status periodically
  unsigned long now = millis();
  if (now - lastStatusUpdate > STATUS_UPDATE_INTERVAL) {
    publishStatus();
    lastStatusUpdate = now;
  }
}
