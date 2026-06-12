# Reliable ESP8266 upload for FaceLocking (fixes C100 / timeout / COM port lock).
# Servo on GPIO2 (D4) can stay wired. Close Arduino IDE + track.py before upload.
# Usage:  .\upload_esp8266.ps1
#         .\upload_esp8266.ps1 -Port COM5

param(
    [string]$Port = "",
    [int]$Baud = 57600
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sketch = Join-Path $ProjectRoot "arduino\esp8266_camera_tracker"
$Fqbn = "esp8266:esp8266:nodemcu:baud=$Baud"

function Invoke-ArduinoCli {
    param([string[]]$CliArgs)
    # arduino-cli prints RAM/IRAM stats on stderr; must not treat that as a PowerShell error
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $lines = @(& $cli @CliArgs 2>&1)
    $exit = $LASTEXITCODE
    $ErrorActionPreference = $prev
    $text = ($lines | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { "$_" }
    }) -join "`n"
    $text -split "`n" | ForEach-Object { if ($_) { Write-Host $_ } }
    if ($exit -eq 0 -and $text -match 'fatal esptool|Failed uploading|Timed out waiting|PermissionError|Access is denied') {
        $exit = 1
    }
    return $exit
}

function Find-EspPort {
    Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.Name -match 'CH340|CH910|CP210|USB-SERIAL|USB-Enhanced-SERIAL' -and $_.Name -match 'COM\d+' } |
        ForEach-Object {
            if ($_.Name -match '\(COM(\d+)\)') { return "COM$($Matches[1])" }
        } | Select-Object -First 1
}

Write-Host ""
Write-Host "=== FaceLocking ESP8266 upload (baud $Baud) ===" -ForegroundColor Cyan
Write-Host "Close Arduino IDE + track.py. Servo on D4 can stay connected." -ForegroundColor Yellow
Write-Host "Unplug webcam USB if you can (reduces USB power issues)." -ForegroundColor Yellow
Write-Host ""

# Free COM port — another open handle causes "Access is denied" mid-flash
$lockers = @("python", "pythonw", "Arduino IDE", "arduino-cli", "serial-monitor")
foreach ($name in $lockers) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

if (-not $Port) {
    $Port = Find-EspPort
}
if (-not $Port) {
    $ports = [System.IO.Ports.SerialPort]::GetPortNames() | Where-Object { $_ -ne 'COM1' }
    if ($ports.Count -eq 1) { $Port = $ports[0] }
}
if (-not $Port) {
    Write-Host "ERROR: No ESP serial port found. Plug in NodeMCU USB and retry." -ForegroundColor Red
    exit 1
}

Write-Host "Port: $Port" -ForegroundColor Green
Write-Host "Compiling..." -ForegroundColor Cyan

$cli = Get-Command arduino-cli -ErrorAction SilentlyContinue
if (-not $cli) {
    $cliPath = "C:\Program Files\Arduino CLI\arduino-cli.exe"
    if (-not (Test-Path $cliPath)) {
        Write-Host "ERROR: arduino-cli not found. Run: winget install ArduinoSA.CLI" -ForegroundColor Red
        exit 1
    }
    $cli = $cliPath
}

$compileExit = Invoke-ArduinoCli @("compile", "--fqbn", $Fqbn, $Sketch)
if ($compileExit -ne 0) { exit $compileExit }

Write-Host ""
Write-Host "Uploading... (hold FLASH, tap RESET, release FLASH if it fails)" -ForegroundColor Cyan
Start-Sleep -Seconds 2

$code = 1
for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ($attempt -gt 1) {
        Write-Host "Retry $attempt/3 in 3s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
    $code = Invoke-ArduinoCli @("upload", "-p", $Port, "--fqbn", $Fqbn, $Sketch)
    if ($code -eq 0) { break }
}

if ($code -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS. Run: python track.py" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "FAILED (exit $code). Retry checklist:" -ForegroundColor Red
    Write-Host "  1. Ctrl+C track.py, CLOSE Arduino IDE completely (not just Serial Monitor)"
    Write-Host "  2. Wait 5s, run ONLY: .\upload_esp8266.ps1 -Port $Port"
    Write-Host "  3. Unplug webcam USB if possible (servo on D4 can stay)"
    Write-Host "  4. FLASH+RESET on ESP, then upload again"
    Write-Host "  5. Slower baud: .\upload_esp8266.ps1 -Port $Port -Baud 57600"
}

exit $code
