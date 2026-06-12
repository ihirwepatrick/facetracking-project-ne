@echo off
REM Run as Administrator: right-click -> Run as administrator
REM Opens Mosquitto to your LAN so ESP8266 can connect on port 1883.

net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Run this script as Administrator.
    pause
    exit /b 1
)

set CONF=C:\Program Files\mosquitto\mosquitto.conf
findstr /C:"FaceLocking - allow ESP8266" "%CONF%" >nul 2>&1
if errorlevel 1 (
    echo.>> "%CONF%"
    echo # FaceLocking - allow ESP8266 on LAN>> "%CONF%"
    echo listener 1883 0.0.0.0>> "%CONF%"
    echo allow_anonymous true>> "%CONF%"
    echo Added LAN listener to mosquitto.conf
) else (
    echo LAN listener already configured in mosquitto.conf
)

netsh advfirewall firewall add rule name="Mosquitto MQTT 1883" dir=in action=allow protocol=TCP localport=1883 >nul 2>&1

net stop mosquitto
net start mosquitto

echo.
echo Mosquitto restarted. Use your PC LAN IP in config.py and the Arduino sketch.
echo Find it with: ipconfig   ^(look for IPv4 on Wi-Fi or Ethernet^)
echo.
pause
