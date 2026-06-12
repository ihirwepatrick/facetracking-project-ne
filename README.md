# FaceLocking

CPU-based face recognition with face locking, activity logging, MQTT pan tracking, and an optional web dashboard. An ESP8266 drives a servo-mounted camera to follow a locked person and search when they leave the frame.

---

## What this system does

```
Webcam → Face detect → 5-point align → ArcFace embed → Match database → Name
       → [optional] Lock one person → Log blinks/smiles/movement
       → [optional] MQTT → ESP8266 servo pans camera to follow / search
       → [optional] Web dashboard (live video + servo telemetry)
```

| Mode | Command | Servo | Dashboard |
|------|---------|-------|-----------|
| Enrollment | `python -m src.enroll` | No | No |
| Recognition only | `python -m src.recognize` | No | No |
| Tracking + servo | `python track.py` | Yes | Optional (`--dashboard`) |

---

## Requirements

### Software

- **Python 3.10+** (3.13 tested)
- **Linux / macOS / Windows** (Linux recommended for camera + MQTT lab setup)
- Packages listed in [`requirements.txt`](requirements.txt):

| Package | Purpose |
|---------|---------|
| `opencv-python` | Camera capture and display |
| `numpy`, `scipy` | Numerical processing |
| `onnxruntime` | ArcFace embedding inference |
| `mediapipe` | Face landmarks (Tasks API) |
| `paho-mqtt` | Servo control via MQTT |
| `flask` | Web dashboard |
| `tqdm` | Progress bars |

### Hardware (tracking mode only)

- USB webcam
- ESP8266 (NodeMCU / Wemos D1 Mini)
- SG90 (or similar) servo + camera mount
- MQTT broker reachable by PC and ESP8266 (e.g. Mosquitto on a VPS or LAN)

See [arduino/README.md](arduino/README.md) and [arduino/WIRING_DIAGRAM.txt](arduino/WIRING_DIAGRAM.txt) for wiring.

---

## Installation

### Step 1 — Get the project

Clone or download the repo, then open a terminal in the project folder.

**Linux / macOS:**

```bash
cd /path/to/FaceLocking
```

**Windows (Command Prompt or PowerShell):**

```cmd
cd C:\path\to\FaceLocking
```

---

### Linux / macOS

#### Automated setup (recommended)

```bash
bash setup.sh
```

This script:

1. Checks for Python 3
2. Creates `.venv` (recreates it if broken)
3. Runs `pip install -r requirements.txt`
4. Creates `data/` and `models/` directories

#### Manual setup (alternative)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -c "from src import config; config.ensure_dirs()"
```

Activate the environment **every time** you open a new terminal:

```bash
source .venv/bin/activate
```

---

### Windows

#### Prerequisites

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/)
2. During install, check **“Add python.exe to PATH”**
3. Use **Command Prompt** or **PowerShell** (not required to use WSL)

#### Automated setup (recommended)

Double-click `setup.bat`, or run from the project folder:

```cmd
setup.bat
```

This script:

1. Creates `.venv` if it does not exist
2. Bootstraps `pip` with `ensurepip`
3. Runs `pip install -r requirements.txt`
4. Creates `data/` and `models/` directories

#### Manual setup (alternative)

**Command Prompt:**

```cmd
cd C:\path\to\FaceLocking
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -c "from src import config; config.ensure_dirs()"
```

**PowerShell:**

```powershell
cd C:\path\to\FaceLocking
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -c "from src import config; config.ensure_dirs()"
```

> If PowerShell blocks activation (`execution policy`), run once as Administrator:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Or use **Command Prompt** with `.venv\Scripts\activate.bat` instead.

Activate the environment **every time** you open a new terminal:

```cmd
.venv\Scripts\activate.bat
```

You should see `(.venv)` at the start of your prompt.

#### Windows notes

| Topic | Tip |
|-------|-----|
| Virtual env | Use **`.venv`**, not `venv` |
| Webcam | Allow camera access when Windows prompts (Settings → Privacy → Camera) |
| `curl` for models | `download_model.py` needs network access; install [curl](https://curl.se/windows/) or use Git Bash if download fails |
| Arduino | Use Arduino IDE on Windows — same firmware file as Linux |
| Firewall | Allow Python through the firewall if using MQTT or the dashboard on LAN |

---

### Step 2 — Verify installation (all platforms)

With the virtual environment activated:

```bash
python verify.py
```

On Windows the same command works after activation:

```cmd
python verify.py
```

All checks should pass. Fix any missing files or import errors before continuing.

---

## Download AI models

ArcFace and MediaPipe models are **not** in the repo (too large).

**Linux / macOS:**

```bash
source .venv/bin/activate
python download_model.py
```

**Windows:**

```cmd
.venv\Scripts\activate.bat
python download_model.py
```

This downloads:

- `models/embedder_arcface.onnx` — face embeddings (~170 MB)
- `models/face_landmarker.task` — MediaPipe landmarks

---

## Configure camera and MQTT

Edit [`src/config.py`](src/config.py) for your environment:

```python
CAMERA_INDEX = 1              # See below to find the right index
CAMERA_AUTO_DETECT = True     # Try other indices if primary fails

MQTT_BROKER_HOST = "157.173.101.159"   # Your broker IP
MQTT_BROKER_PORT = 1883
```

**Find your camera index:**

```bash
python -m src.camera_utils
```

Set `CAMERA_INDEX` to the recommended value.

**Test the camera:**

```bash
python -m src.camera
```

---

## ESP8266 firmware (tracking only)

1. Open `arduino/esp8266_camera_tracker/esp8266_camera_tracker.ino` in Arduino IDE
2. Set WiFi SSID/password and `mqtt_server` (same broker as `src/config.py`)
3. Install board: **ESP8266** + library: **PubSubClient**
4. Upload to the board
5. Open Serial Monitor (115200) — confirm WiFi + MQTT connected

Servo wiring: Signal → **D4 (GPIO2)**, VCC → 5V, GND → GND

---

## Running the system

Activate the virtual environment first:

```bash
source .venv/bin/activate          # Linux / macOS
```

```cmd
.venv\Scripts\activate.bat         # Windows
```

### 1. Enroll faces

```bash
python -m src.enroll
```

- Enter a name when prompted
- Look at the camera; ~15 samples are captured automatically
- Press `q` to finish
- Data saved to `data/db/face_db.npz` and `data/enroll/<name>/`

Re-run to add more people. To wipe all data:

```bash
python reset_data.py
```

### 2. Recognition only (no servo)

```bash
python -m src.recognize
```

- Optionally lock one enrolled person at startup (enter number or name)
- Locked person gets activity logging (blinks, smiles, movement) in `data/history/`

**Keyboard controls:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reload face database |
| `l` | Clear lock |
| `f` | Toggle fullscreen |
| `+` / `-` | Adjust recognition threshold |

**Bounding box colors:**

| Color | Meaning |
|-------|---------|
| Red | Unknown |
| Blue | Known, not locked |
| Green | Locked target |
| Orange | Lock lost / searching |

### 3. Tracking + servo (full system)

```bash
python track.py
```

Or:

```bash
python -m src.recognize_with_tracking
```

**At startup you must select a person to lock** — tracking and servo only work when a lock target is set.

**Additional controls:**

| Key | Action |
|-----|--------|
| `k` | Change lock target |
| `s` | Toggle manual search sweep |
| `c` | Center servo |

**What happens when the locked person leaves the frame:**

1. Grace period (~0.8 s)
2. **SEARCH MODE** — servo sweeps 0° → 180° looking for them
3. Recognition keeps running; lock is **never** transferred to another face
4. When the original person is found again, tracking resumes

### 4. Web dashboard

```bash
python track.py --dashboard
```

Open in browser: **http://127.0.0.1:8765**

Shows live camera feed, servo angle gauge, movement log, face list, FPS, and MQTT status.

**Browser only (no OpenCV window):**

```bash
python track.py --dashboard --headless
```

Press **Ctrl+C** in the terminal to stop in headless mode.

To allow access from other devices on your LAN, set in `src/config.py`:

```python
DASHBOARD_HOST = "0.0.0.0"
```

Then open `http://<your-pc-ip>:8765` from another device.

---

## MQTT testing (without camera)

```bash
# Test broker + servo commands
python test_simple_tracking.py

# Full MQTT integration test
python test_mqtt_system.py

# Monitor all MQTT messages
python debug_mqtt_tracking.py
```

If these fail, fix MQTT/network before running `track.py`.

---

## Project structure

```
FaceLocking/
├── README.md                 ← this file
├── requirements.txt          ← Python dependencies
├── setup.sh                  ← one-command install
├── download_model.py         ← download ONNX + MediaPipe models
├── verify.py                 ← integrity check
├── reset_data.py             ← wipe enroll/db/history
├── track.py                  ← tracking entry point
├── track.sh                  ← shell wrapper
│
├── src/
│   ├── config.py             ← all settings (camera, MQTT, servo, thresholds)
│   ├── enroll.py             ← face enrollment
│   ├── recognize.py          ← recognition + activity log
│   ├── recognize_with_tracking.py  ← recognition + MQTT + search
│   ├── tracking.py           ← PID pan controller + search sweep
│   ├── mqtt_camera_controller.py
│   ├── face_tracker.py       ← multi-face ID tracking
│   ├── recognition_core.py   ← shared match/draw utilities
│   ├── dashboard_server.py   ← Flask web UI
│   └── ...
│
├── dashboard/                ← web UI (HTML/CSS/JS)
├── arduino/                  ← ESP8266 firmware
├── models/                   ← downloaded AI models
├── data/
│   ├── db/                   ← face embedding database
│   ├── enroll/               ← enrollment images
│   └── history/              ← activity session logs
│
├── TEST_GUIDE.md             ← detailed test procedures
└── PROJECT_GUIDE.md          ← architecture reference
```

---

## Utility scripts

| Script | Purpose |
|--------|---------|
| `python verify.py` | Check files and imports |
| `python download_model.py` | Download AI models |
| `python reset_data.py` | Delete all enrolled data |
| `python -m src.camera_utils` | Find camera index |
| `python -m src.view_activity_logs` | Review activity history |
| `python test_mqtt_system.py` | Test MQTT + servo |
| `python debug_mqtt_tracking.py` | Monitor MQTT topics |

---

## Troubleshooting

### `ModuleNotFoundError` / wrong environment

```bash
source .venv/bin/activate   # Linux / macOS — NOT venv/
python -m pip install -r requirements.txt
```

```cmd
.venv\Scripts\activate.bat   # Windows
python -m pip install -r requirements.txt
```

### `can't open camera by index`

```bash
python -m src.camera_utils
# Update CAMERA_INDEX in src/config.py
```

### Recognition stops with `ioctl(VIDIOC_QBUF): Bad file descriptor`

Transient camera failure. The system retries automatically. If it keeps happening, fix `CAMERA_INDEX` or close other apps using the webcam.

### Servo does not move

1. Use **`python track.py`**, not `python -m src.recognize`
2. **Select a lock target** at startup
3. Run `python test_simple_tracking.py` — if this fails, fix MQTT/ESP8266 first
4. Check terminal for `✓ MQTT ready` or `✗ MQTT NOT CONNECTED`
5. Stand **off-center** from the camera — servo holds when face is already centered (dead zone)
6. Reflash Arduino with matching broker IP and WiFi credentials

### Dashboard blank or unstyled

1. Ensure Flask is installed: `pip install flask`
2. Use `python track.py --dashboard` (not recognize-only mode)
3. Open **http://127.0.0.1:8765** after you see `✓ Dashboard ready`
4. Video appears only after the tracking loop starts sending frames

### Slow performance

- Use `python -m src.recognize` instead of `track.py` if you don't need servo
- Lower resolution is already set (`480×360`); tune `PROCESS_EVERY_N_FRAMES_FACE` in `config.py`
- Run with `--headless` to skip the OpenCV window

### `mediapipe` / `AttributeError: solutions`

Requires `mediapipe>=0.10.30`. Reinstall:

```bash
pip install "mediapipe>=0.10.30"
```

---

## Quick reference — full workflow

### Linux / macOS

```bash
# One-time setup
bash setup.sh
source .venv/bin/activate
python download_model.py
python verify.py

# Configure camera + MQTT in src/config.py
# Flash Arduino firmware

# Every session
source .venv/bin/activate
python -m src.enroll              # first time: enroll your face
python track.py --dashboard       # run tracking + dashboard
# → lock a person at prompt
# → open http://127.0.0.1:8765
```

### Windows

```cmd
REM One-time setup
setup.bat
.venv\Scripts\activate.bat
python download_model.py
python verify.py

REM Configure camera + MQTT in src\config.py
REM Flash Arduino firmware

REM Every session
.venv\Scripts\activate.bat
python -m src.enroll
python track.py --dashboard
REM → lock a person at prompt
REM → open http://127.0.0.1:8765
```

---

## Documentation

- [TEST_GUIDE.md](TEST_GUIDE.md) — step-by-step validation checklist
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) — architecture and data flow
- [arduino/README.md](arduino/README.md) — ESP8266 setup and MQTT topics

---

## License

Educational / research use — Intelligent Robotics coursework.
