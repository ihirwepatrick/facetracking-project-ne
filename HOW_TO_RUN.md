# FaceLocking — How to Run

Face recognition on your PC webcam + MQTT pan servo on ESP8266. This guide covers first-time setup, daily startup, and retries for every common failure.

For system design, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## What you need

| Item | Notes |
|------|--------|
| Windows 10/11 PC | Same Wi-Fi as ESP8266 |
| Python 3.12+ | With `venv` support |
| USB webcam | Usually index `0` |
| ESP8266 (NodeMCU / Wemos D1 Mini) | USB serial (e.g. COM5, CH9102/CH340) |
| SG90 servo | Signal on **D4 (GPIO2)** — not D6 |
| Mosquitto MQTT broker | Port `1883` on your PC |
| Arduino CLI | For ESP firmware upload |
| Wi-Fi 2.4 GHz | ESP8266 cannot use 5 GHz-only networks |

---

## First-time setup (once)

### 1. Clone / open the project

```powershell
cd "C:\Users\RCA_USER_65\Documents\NE_Preps_Ihirwe\New folder\FaceLocking-master\FaceLocking-master"
```

### 2. Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_model.py
```

**Retry if models fail to download:** run `python download_model.py` again or check your internet connection.

### 3. Install Mosquitto (MQTT broker)

1. Install [Mosquitto for Windows](https://mosquitto.org/download/).
2. **Run as Administrator:** right-click `setup_mqtt_broker.bat` → **Run as administrator**.
   - Adds LAN listener on `0.0.0.0:1883`
   - Opens Windows Firewall for port 1883
   - Restarts the Mosquitto service

**Verify:**

```powershell
netstat -an | findstr ":1883"
```

You should see `0.0.0.0:1883` in `LISTENING` state.

### 4. Install Arduino CLI + ESP8266 core

```powershell
winget install ArduinoSA.CLI
arduino-cli core update-index
arduino-cli core install esp8266:esp8266
```

### 5. Wi-Fi and broker IP

Edit Wi-Fi in `arduino/esp8266_camera_tracker/esp8266_camera_tracker.ino` if needed:

```cpp
const char* ssid = "YourNetwork";
const char* password = "YourPassword";
```

Sync your PC LAN IP into Python config and the Arduino sketch:

```powershell
python scripts\sync_broker_ip.py
```

If your PC IP changes (different network), run this again and **re-upload ESP firmware**.

### 6. Enroll faces (required before tracking)

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.enroll
```

Follow prompts to capture samples for each person. Data is stored in `data/db/`.

---

## Daily run (recommended — one command)

```powershell
.\start_all.bat
```

This script automatically:

1. Activates `.venv`
2. Syncs MQTT broker IP (`scripts/sync_broker_ip.py`)
3. Starts/checks Mosquitto on port 1883
4. Stops old `track.py` / Arduino sessions (frees COM port)
5. Uploads ESP8266 firmware (`upload_esp8266.ps1`)
6. Waits up to 90s for ESP on MQTT (`scripts/wait_for_esp.py`)
7. Starts `python track.py --dashboard`

**Dashboard:** http://127.0.0.1:8765

When prompted, enter a person number or name to lock/track, or press Enter for recognition-only mode.

### Startup flags

| Command | Effect |
|---------|--------|
| `.\start_all.bat` | Full startup + ESP flash + dashboard |
| `.\start_all.bat -SkipUpload` | Skip ESP flash (faster restart) |
| `.\start_all.bat -NoDashboard` | Tracking without web dashboard |
| `.\start_all.bat -EspPort COM5` | Force ESP serial port |

PowerShell equivalent:

```powershell
.\start_all.ps1 -SkipUpload -NoDashboard -EspPort COM5
```

---

## Manual step-by-step (if you prefer control)

```powershell
# 1. Activate venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"

# 2. Sync broker IP
python scripts\sync_broker_ip.py

# 3. Ensure Mosquitto is running (or run setup_mqtt_broker.bat as Admin once)

# 4. Upload ESP (close track.py and Arduino IDE first)
.\upload_esp8266.ps1 -Port COM5 -Baud 57600

# 5. Wait for ESP on MQTT
python scripts\wait_for_esp.py

# 6. Start tracking
python track.py --dashboard
```

---

## Tracking modes

| Command | Description |
|---------|-------------|
| `python track.py --dashboard` | Face tracking + web dashboard (default via `start_all`) |
| `python track.py` | OpenCV window only, no dashboard |
| `python track.py --no-mqtt` | Recognition only, servo disabled |
| `python track.py --fullscreen` | Fullscreen preview |
| `python track.py --headless` | Dashboard only, no OpenCV window |

At startup you can **lock one enrolled person**:

- Enter `1`, `2`, … or a name like `ihirwe`
- Locked + visible → servo holds still
- Locked + lost → slow ping-pong search 0° → 180° → 0°

---

## Diagnostic commands

Run these from the project folder with `.venv` activated.

| Command | Purpose |
|---------|---------|
| `python debug_mqtt_tracking.py` | Live MQTT topic monitor (expect `camera/status` every ~150 ms) |
| `python scripts\diagnose_esp_mqtt.py` | Full ESP/MQTT checklist |
| `python scripts\wait_for_esp.py` | Wait up to 90s for ESP online |
| `python test_mqtt_system.py` | Send test servo commands via MQTT |
| `python scripts\sync_broker_ip.py` | Update broker IP in config + Arduino sketch |
| `ipconfig` | Find your PC IPv4 (must match `src/config.py`) |

---

## Troubleshooting and retries

### A. `start_all.bat` PowerShell parse errors

**Symptom:** Red errors about `from`, `for`, missing `(`.

**Fix:** Use the current `start_all.ps1` (ESP wait logic lives in `scripts/wait_for_esp.py`, not inline Python). Pull latest project files and retry:

```powershell
.\start_all.bat
```

---

### B. `.venv not found`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_model.py
```

---

### C. MQTT broker NOT reachable on port 1883

**Symptom:** `MQTT broker NOT reachable on port 1883`

**Retries:**

1. Run `setup_mqtt_broker.bat` **as Administrator** (once).
2. Start Mosquitto manually:
   ```powershell
   net start mosquitto
   ```
3. Confirm listener:
   ```powershell
   netstat -an | findstr ":1883"
   ```
4. Retry:
   ```powershell
   .\start_all.bat -SkipUpload
   ```

---

### D. ESP8266 upload failed (C100, timeout, Access denied)

**Symptoms:**

- `Failed to write compressed data to flash (result was C100)`
- `Timed out waiting for packet header`
- `PermissionError: Access is denied` on COM5

**Important:** Do **not** press `Y` to continue after a failed upload. Partial flash corrupts the ESP and it will crash-loop — MQTT will never work.

**Retry checklist (in order):**

1. **Stop everything using COM5:**
   ```powershell
   Get-Process python, pythonw, "Arduino IDE" -ErrorAction SilentlyContinue | Stop-Process -Force
   ```
   Close Arduino IDE completely (not just Serial Monitor).

2. **Wait 5–8 seconds**, then upload alone:
   ```powershell
   .\upload_esp8266.ps1 -Port COM5 -Baud 57600
   ```
   The script auto-erases flash (fixes crash loops) and retries up to 5 times.

3. **Unplug webcam USB** during upload (reduces USB power draw). Servo on D4 can stay connected.

4. **Use a rear USB 2.0 port** on the PC, not a hub.

5. **Manual boot mode:** hold **FLASH**, tap **RESET**, release **FLASH**, then run upload again.

6. If still failing, try slower baud:
   ```powershell
   .\upload_esp8266.ps1 -Port COM5 -Baud 57600
   ```

7. After **SUCCESS**, plug webcam back in and run:
   ```powershell
   .\start_all.bat -SkipUpload
   ```

---

### E. ESP8266 NOT on MQTT

**Symptom:**

```
⚠ ESP8266 NOT on MQTT — servo will NOT move until it connects.
```

**Retries:**

1. **Confirm firmware uploaded successfully** (see section D). Partial flash = crash loop.

2. **Tap RESET** on the NodeMCU, then:
   ```powershell
   python scripts\wait_for_esp.py
   ```

3. **Monitor MQTT:**
   ```powershell
   python debug_mqtt_tracking.py
   ```
   You should see `[camera/status] {"angle":90,...}` repeatedly.

4. **Serial Monitor (Arduino IDE, 115200 baud, COM5):**
   - `✓ WiFi connected!` → Wi-Fi OK
   - `✓ MQTT connected!` → broker OK
   - `✗ Cannot reach broker` → firewall or wrong PC IP
   - `Fatal exception` → corrupt flash → re-upload (section D)

5. **Re-sync IP** if you changed networks:
   ```powershell
   python scripts\sync_broker_ip.py
   .\upload_esp8266.ps1 -Port COM5
   ```

6. **Run broker setup as Admin** if ESP shows broker TCP failure:
   ```powershell
   # Right-click → Run as administrator
   setup_mqtt_broker.bat
   ```

7. **Router AP / client isolation:** some Wi-Fi networks block device-to-device traffic. Fixes:
   - Plug PC into router with **Ethernet**, run `sync_broker_ip.py`, re-upload ESP
   - Or disable “AP isolation” / “client isolation” in router settings

8. **Wi-Fi credentials:** ESP must use **2.4 GHz** SSID (not 5 GHz-only). Edit `esp8266_camera_tracker.ino` and re-upload.

---

### F. Servo does not move (but ESP shows online)

**Retries:**

1. Test MQTT commands directly:
   ```powershell
   python test_mqtt_system.py
   ```

2. Check wiring: servo signal on **D4 (GPIO2)**, VCC 5V, GND common.

3. Confirm `camera/status` angle changes in `debug_mqtt_tracking.py` when commands are sent.

4. If angles change in MQTT but servo is still: check power supply (weak USB may move Wi-Fi but not servo under load).

---

### G. Webcam / camera errors

**Retries:**

1. Close other apps using the camera (Teams, Zoom, browser).

2. Try a different USB port; unplug ESP briefly if bandwidth is an issue.

3. Set camera index in `src/config.py` (`CAMERA_INDEX = 0`).

4. Run without dashboard to isolate:
   ```powershell
   python track.py --no-mqtt
   ```

---

### H. No enrolled identities

**Symptom:** `ERROR: No enrolled identities. Run: python -m src.enroll`

```powershell
python -m src.enroll
```

Then restart tracking.

---

### I. Wrong person tracked / false “target lost”

Tune in `src/config.py`:

- `LOST_TARGET_TIMEOUT`, `LOST_TARGET_FRAMES` — how long before “lost”
- `LOCK_HOLD_SERVO = True` — hold servo when locked person is visible
- `LOCK_FOLLOW_CENTER = False` — no auto-centering while locked

Restart `track.py` after config changes (no ESP re-flash needed).

---

## Quick reference — file map

| File | Role |
|------|------|
| `start_all.bat` / `start_all.ps1` | One-command full startup |
| `upload_esp8266.ps1` | Reliable ESP flash (erase + retries) |
| `setup_mqtt_broker.bat` | One-time Mosquitto LAN + firewall (Admin) |
| `track.py` | Main tracking entry point |
| `scripts/sync_broker_ip.py` | Sync PC IP → config + Arduino |
| `scripts/wait_for_esp.py` | Wait for ESP MQTT status |
| `scripts/diagnose_esp_mqtt.py` | ESP/MQTT diagnostic |
| `debug_mqtt_tracking.py` | Live MQTT topic viewer |
| `src/config.py` | All tuning (MQTT, servo, detection) |
| `arduino/esp8266_camera_tracker/` | ESP8266 firmware |

---

## Typical successful startup log

```
========================================
  FaceLocking - full system startup
========================================

==> Activating Python virtual environment
Python: Python 3.12.x

==> Syncing MQTT broker IP (PC LAN address)
LAN IP: 192.168.8.105

==> Checking MQTT broker (Mosquitto)
MQTT broker listening on port 1883

==> Uploading firmware to ESP8266
SUCCESS.

==> Verifying MQTT from Python and waiting for ESP8266 (up to 90s)
✓ ESP8266 online — servo reported at 90°

==> Starting face tracking
Dashboard: http://127.0.0.1:8765
✓ Loaded 2 enrolled identities
```

---

## Stopping the system

1. Press **Ctrl+C** in the terminal running `track.py`.
2. ESP keeps last angle; next `start_all.bat` re-centers on connect.
