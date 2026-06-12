# FaceLocking - one command: venv + MQTT broker + ESP upload + tracking dashboard
#
# Usage:
#   .\start_all.ps1
#   .\start_all.ps1 -SkipUpload
#   .\start_all.ps1 -NoDashboard

param(
    [switch]$SkipUpload,
    [switch]$NoDashboard,
    [string]$EspPort = ""
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-MqttPort {
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect("127.0.0.1", 1883, $null, $null)
        $connected = $result.AsyncWaitHandle.WaitOne(2000, $false)
        if ($connected -and $client.Connected) {
            return $true
        }
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $client) {
            $client.Close()
        }
    }
    return $false
}

function Ensure-MqttBroker {
    if (Test-MqttPort) {
        Write-Host "MQTT broker listening on port 1883" -ForegroundColor Green
        return $true
    }

    $svc = Get-Service -Name mosquitto -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "Starting Mosquitto service..."
        try {
            if ($svc.Status -ne "Running") {
                Start-Service mosquitto -ErrorAction Stop
                Start-Sleep -Seconds 2
            }
        }
        catch {
            Write-Host "Could not start Mosquitto (try setup_mqtt_broker.bat as Admin)." -ForegroundColor Yellow
        }
    }

    if (Test-MqttPort) {
        Write-Host "MQTT broker ready" -ForegroundColor Green
        return $true
    }

    Write-Host ""
    Write-Host "MQTT broker NOT reachable on port 1883." -ForegroundColor Red
    Write-Host "One-time fix: right-click setup_mqtt_broker.bat -> Run as administrator" -ForegroundColor Yellow
    Write-Host "Continuing anyway - servo may not move until broker is fixed." -ForegroundColor Yellow
    return $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  FaceLocking - full system startup" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Write-Step "Activating Python virtual environment"
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "ERROR: .venv not found. Run: python -m venv .venv" -ForegroundColor Red
    Write-Host "       then: pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
. $venvActivate
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Python: $(python --version)" -ForegroundColor Green

Write-Step "Syncing MQTT broker IP (PC LAN address)"
python (Join-Path $ProjectRoot "scripts\sync_broker_ip.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "Checking MQTT broker (Mosquitto)"
$mqttOk = Ensure-MqttBroker

Write-Step "Stopping previous track.py / Arduino sessions"
Get-Process python, pythonw, "Arduino IDE" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (-not $SkipUpload) {
    Write-Step "Uploading firmware to ESP8266 (unplug webcam USB if upload fails)"
    $uploadScript = Join-Path $ProjectRoot "upload_esp8266.ps1"
    if ($EspPort) {
        & $uploadScript -Port $EspPort
    }
    else {
        & $uploadScript
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ESP upload failed. Options:" -ForegroundColor Yellow
        Write-Host "  Retry:       .\start_all.bat"
        Write-Host "  Skip flash:  .\start_all.bat -SkipUpload"
        Write-Host "  Manual:      .\upload_esp8266.ps1 -Port COM5 -Baud 57600"
        Write-Host "ESP flash may be CORRUPT (partial upload) — servo will NOT work until upload succeeds." -ForegroundColor Red
        $answer = Read-Host "Continue anyway without working ESP? [y/N]"
        if ($answer -notmatch '^[yY]') { exit $LASTEXITCODE }
    }
    else {
        Write-Host "ESP firmware uploaded." -ForegroundColor Green
        Write-Host "Plug webcam USB back in now (if you unplugged it for upload)." -ForegroundColor Yellow
        Write-Host "Waiting 15s for ESP boot + WiFi..." -ForegroundColor Gray
        Start-Sleep -Seconds 15
    }
}
else {
    Write-Host "Skipping ESP upload (-SkipUpload)" -ForegroundColor Yellow
}

if ($mqttOk) {
    Write-Step "Verifying MQTT from Python"
    python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1', 1883)); s.close(); print('Python MQTT port check: OK')"
    Write-Step "Waiting for ESP8266 on WiFi/MQTT (up to 90s)"
    python -c @"
import time
from src.mqtt_camera_controller import MQTTCameraController
c = MQTTCameraController()
c.wait_for_connection(10)
ok = False
for attempt in range(3):
    if c.wait_for_esp(30):
        ok = True
        break
    if attempt < 2:
        print('  ESP not seen yet — tap RESET on NodeMCU, retrying...')
        time.sleep(5)
if not ok:
    print('  Still offline: Serial Monitor 115200 on COM5 shows WiFi/MQTT errors.')
    print('  If Broker TCP: FAILED -> run setup_mqtt_broker.bat as Administrator.')
c.close()
"@
}

Write-Step "Starting face tracking"
if ($NoDashboard) {
    Write-Host "Command: python track.py" -ForegroundColor Gray
    python track.py
}
else {
    Write-Host "Command: python track.py --dashboard" -ForegroundColor Gray
    Write-Host "Dashboard: http://127.0.0.1:8765" -ForegroundColor Green
    python track.py --dashboard
}

exit $LASTEXITCODE
