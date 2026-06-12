const $ = (id) => document.getElementById(id);

let _errorShown = false;
function showLoadError(msg) {
  if (_errorShown) return;
  _errorShown = true;
  const banner = document.createElement("div");
  banner.id = "dashboard-error";
  banner.style.cssText =
    "position:fixed;top:0;left:0;right:0;background:#7f1d1d;color:#fff;padding:12px;text-align:center;z-index:9999;font-size:14px";
  banner.textContent = msg;
  document.body.prepend(banner);
}

function stateClass(state) {
  const s = (state || "IDLE").toLowerCase();
  if (s === "locked") return "locked";
  if (s === "searching") return "searching";
  if (s === "tracking") return "tracking";
  return "idle";
}

function pctAngle(angle, min, max) {
  return ((angle - min) / (max - min)) * 100;
}

function renderStatus(data) {
  const badge = $("state-badge");
  badge.textContent = data.state || "IDLE";
  badge.className = `badge ${stateClass(data.state)}`;

  const mqtt = $("mqtt-badge");
  mqtt.textContent = data.mqtt_connected ? "MQTT OK" : "MQTT --";
  mqtt.className = `badge ${data.mqtt_connected ? "mqtt-on" : "mqtt-off"}`;

  const min = data.servo_min ?? 0;
  const max = data.servo_max ?? 180;
  const angle = data.servo_angle ?? 90;
  const pct = pctAngle(angle, min, max);

  $("servo-needle").style.left = `${pct}%`;
  $("servo-marker").style.left = `${pct}%`;
  $("servo-angle").textContent = `${Math.round(angle)}°`;
  $("lock-name").textContent = data.lock_name || "—";
  $("face-count").textContent = data.face_count ?? 0;
  $("track-fps").textContent = (data.track_fps ?? 0).toFixed(1);
  $("recog-fps").textContent = (data.recog_fps ?? 0).toFixed(1);
  $("threshold").textContent = (data.threshold ?? 0).toFixed(2);
  $("enrolled").textContent = data.enrolled_count ?? 0;

  const lost = data.lost_for ?? 0;
  $("lost-for").textContent =
    data.state === "SEARCHING" || lost > 0 ? `${lost.toFixed(1)}s` : "—";

  const banner = $("search-banner");
  if (data.state === "SEARCHING" && data.lock_name) {
    banner.textContent = `SEARCHING: ${data.lock_name}`;
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }

  const servoLog = $("servo-log");
  servoLog.innerHTML = "";
  (data.servo_history || []).slice(0, 12).forEach((e) => {
    const li = document.createElement("li");
    const moved = Math.abs(e.to_angle - e.from_angle) >= 1;
    li.className = moved ? "move" : "hold";
    const t = new Date(e.ts * 1000).toLocaleTimeString();
    li.textContent = moved
      ? `${t}  ${Math.round(e.from_angle)}° → ${Math.round(e.to_angle)}°  ${e.reason}`
      : `${t}  HOLD ${Math.round(e.from_angle)}°  ${e.reason}`;
    servoLog.appendChild(li);
  });

  const faceList = $("face-list");
  faceList.innerHTML = "";
  (data.faces || []).forEach((f) => {
    const li = document.createElement("li");
    li.className = f.locked ? "locked" : f.accepted ? "known" : "";
    li.innerHTML = `<span>${f.locked ? "🔒 " : ""}${f.name} #${f.track_id}</span>
      <span class="conf">${f.accepted ? (f.confidence * 100).toFixed(0) + "%" : "—"}</span>`;
    faceList.appendChild(li);
  });

  const sysLog = $("sys-log");
  sysLog.innerHTML = "";
  (data.logs || []).slice(0, 20).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    sysLog.appendChild(li);
  });
}

async function poll() {
  try {
    const res = await fetch("/api/status");
    if (res.ok) {
      renderStatus(await res.json());
      return;
    }
    showLoadError(`Dashboard API error: HTTP ${res.status}`);
  } catch (err) {
    showLoadError("Cannot reach dashboard API — is track.py --dashboard still running?");
  }
}

// Verify static assets loaded (404 CSS = broken layout)
(function checkAssets() {
  const sheets = [...document.styleSheets];
  const ok = sheets.some((s) => s.href && s.href.includes("dashboard.css"));
  if (!ok) {
    showLoadError("Dashboard CSS failed to load (check /static/dashboard.css)");
  }
})();

setInterval(poll, 400);
poll();
