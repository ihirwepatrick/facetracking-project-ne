# FaceLocking — System Architecture

For setup and retries, see [HOW_TO_RUN.md](HOW_TO_RUN.md).

## Block diagram

Camera, AI processing, MQTT, ESP8266, and servo.

```mermaid
flowchart LR
    CAM[Webcam] --> PY[Python track.py]
    PY -->|detect + recognize| PY
    PY -->|pan angles| MQTT[(Mosquitto MQTT)]
    MQTT -->|Wi-Fi| ESP[ESP8266]
    ESP --> SERVO[Servo pan 0-180°]
    SERVO -.->|camera moves| CAM
    ESP -->|camera/status| MQTT
    MQTT -->|current angle| PY
    PY --> DASH[Dashboard :8765]
```

## Flowchart

Recognition → tracking → command generation → motor control.

```mermaid
flowchart TD
    START([Start frame loop]) --> CAP[Capture webcam frame]
    CAP --> DET[Face detection<br/>Haar + MediaPipe]
    DET --> REC[Recognition<br/>ArcFace match vs face_db]
    REC --> TRK[Tracking<br/>assign track ID + lock person]

    TRK --> Q{Locked person<br/>in frame?}
    Q -->|yes| HOLD[Hold servo still]
    Q -->|no| Q2{Was locked person<br/>selected?}
    Q2 -->|yes| SEARCH[Search sweep<br/>0° → 180° → 0°]
    Q2 -->|no| IDLE[No pan command]

    HOLD --> CMD[Command generation<br/>tracking.py → target angle]
    SEARCH --> CMD
    IDLE --> CMD

    CMD --> PUB[MQTT publish<br/>camera/track/horizontal]
    PUB --> ESP[ESP8266 receives command]
    ESP --> MOTOR[Motor control<br/>smooth servo steps on D4]
    MOTOR --> STAT[MQTT publish<br/>camera/status angle]
    STAT --> FB[Python reads current angle]
    FB --> START
```

**Start:** `start_all.bat` → sync IP → flash ESP → `track.py --dashboard`

**Lock behavior:** When a locked person is visible the servo holds. When they leave the frame the system searches until they reappear.
