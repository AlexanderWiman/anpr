const STEP_LABELS = [
  "Välkommen",
  "Anläggning",
  "Kamera",
  "Anslutning",
  "Installera",
  "Klart",
];

const CAM_LABELS = {
  tapo: "Tapo (RTSP)",
  ip_webcam: "IP Webcam",
  rtsp: "RTSP",
};

let currentStep = 0;
let sites = [];
let defaultBackend = "";
let pollTimer = null;
let prereqPollTimer = null;
let prereqData = { ok: false, items: [] };
let installInfo = { installed: false };

const $ = (id) => document.getElementById(id);

function buildNav() {
  const nav = $("steps-nav");
  nav.innerHTML = STEP_LABELS.map(
    (label, i) => `<li data-nav="${i}">${label}</li>`
  ).join("");
}

function setStep(n) {
  currentStep = n;
  document.querySelectorAll(".step").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) === n);
  });
  document.querySelectorAll("#steps-nav li").forEach((el) => {
    const i = Number(el.dataset.nav);
    el.classList.toggle("active", i === n);
    el.classList.toggle("done", i < n);
  });

  $("btn-back").style.visibility = n === 0 || n === 5 ? "hidden" : "visible";
  $("btn-next").textContent =
    n === 4
      ? installInfo.installed
        ? "Spara inställningar"
        : "Installera"
      : n === 5
        ? "Stäng"
        : "Fortsätt";
  $("btn-next").classList.toggle("hidden", n === 5);

  if (n === 4) fillSummary();
  if (n === 0) updateNextForPrereqs();
}

function updateNextForPrereqs() {
  const btn = $("btn-next");
  if (currentStep !== 0) {
    btn.disabled = false;
    return;
  }
  btn.disabled = !prereqData.ok;
  btn.title = prereqData.ok ? "" : "Installera Python och ffmpeg först";
}

function camType() {
  return document.querySelector('input[name="cam-type"]:checked').value;
}

function needsAuth() {
  const t = camType();
  return t === "tapo" || t === "rtsp";
}

function buildPreviewUrl() {
  const ip = $("camera-ip").value.trim();
  const port = $("camera-port").value;
  if (!ip) return "";

  const type = camType();
  if (type === "ip_webcam") {
    return `http://${ip}:${port || 8080}/videofeed`;
  }

  const path = type === "tapo" ? "/stream1" : ($("rtsp-path").value || "/stream1");
  const user = $("rtsp-user").value.trim();
  const pass = $("rtsp-pass").value;
  const auth =
    user && pass ? `${encodeURIComponent(user)}:****@` : user ? `${encodeURIComponent(user)}@` : "";

  return `rtsp://${auth}${ip}:${port || 554}${path.startsWith("/") ? path : `/${path}`}`;
}

function updateCameraUi() {
  const type = camType();
  const auth = needsAuth();

  $("auth-fields").classList.toggle("hidden", !auth);
  $("rtsp-extra").classList.toggle("hidden", type !== "rtsp");

  if (type === "tapo") {
    $("camera-port").value = "554";
    $("rtsp-path").value = "/stream1";
  } else if (type === "ip_webcam") {
    $("camera-port").value = "8080";
  } else if (type === "rtsp" && $("camera-port").value === "8080") {
    $("camera-port").value = "554";
  }

  const url = buildPreviewUrl();
  $("camera-preview").textContent = url ? `Kamera-URL: ${url}` : "";
}

function fillSummary() {
  const site = sites.find((s) => s.id === $("site").value);
  const user = $("rtsp-user").value.trim();
  $("summary").innerHTML = `
    <dt>Anläggning</dt><dd>${site?.label || "—"}</dd>
    <dt>Kamera</dt><dd>${$("camera-ip").value} (${CAM_LABELS[camType()] || camType()})</dd>
    ${user ? `<dt>Kamerakonto</dt><dd>${user}</dd>` : ""}
    <dt>Backend</dt><dd>${$("backend-url").value || "—"}</dd>
  `;
}

function validateStep(n) {
  if (n === 2) {
    if (!$("camera-ip").value.trim()) {
      alert("Ange kamera-IP.");
      return false;
    }
    if (needsAuth()) {
      if (!$("rtsp-user").value.trim() || !$("rtsp-pass").value) {
        alert("Ange användarnamn och lösenord för kameran (Tapo Camera Account).");
        return false;
      }
    }
  }
  if (n === 3) {
    if (!$("token").value.trim()) {
      alert("Ange backend-token från IT.");
      return false;
    }
  }
  return true;
}

async function validateBackendCredentials() {
  const res = await fetch("/api/install/validate-credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_id: $("site").value,
      backend_url: $("backend-url").value.trim(),
      anpr_token: $("token").value.trim(),
    }),
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.message || "Token kunde inte verifieras.");
    return false;
  }
  return true;
}

async function loadExistingInstall() {
  const res = await fetch("/api/install/existing");
  installInfo = await res.json();
  renderUpdatePanel();
  applySavedConfig(installInfo.savedConfig);
}

function applySavedConfig(cfg) {
  if (!cfg) return;

  if (cfg.site_id) {
    const siteEl = $("site");
    const known = [...siteEl.options].some((opt) => opt.value === cfg.site_id);
    if (!known) {
      const opt = document.createElement("option");
      opt.value = cfg.site_id;
      opt.textContent = cfg.site_id;
      siteEl.appendChild(opt);
    }
    siteEl.value = cfg.site_id;
  }

  if (cfg.camera_id) $("camera-id").value = cfg.camera_id;
  if (cfg.direction) $("direction").value = cfg.direction;
  if (cfg.camera_ip) $("camera-ip").value = cfg.camera_ip;
  if (cfg.camera_port) $("camera-port").value = String(cfg.camera_port);
  if (cfg.rtsp_path) $("rtsp-path").value = cfg.rtsp_path;
  if (cfg.rtsp_user) $("rtsp-user").value = cfg.rtsp_user;
  if (cfg.rtsp_password) $("rtsp-pass").value = cfg.rtsp_password;
  if (cfg.backend_url) $("backend-url").value = cfg.backend_url;
  if (cfg.anpr_token) $("token").value = cfg.anpr_token;

  if (cfg.camera_type) {
    const radio = document.querySelector(`input[name="cam-type"][value="${cfg.camera_type}"]`);
    if (radio) radio.checked = true;
  }

  updateCameraUi();
}

function renderUpdatePanel() {
  const panel = $("update-panel");
  if (!installInfo.installed) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }

  const current = installInfo.currentVersion || "okänd";
  const remote = installInfo.remoteVersion;
  const hasRemote = installInfo.remoteUpdateAvailable;
  const hasLocal = installInfo.localUpdateAvailable;
  const hasUpdate = installInfo.updateAvailable;

  panel.classList.remove("hidden");

  if (!hasUpdate) {
    let statusLine = `Installerad version <strong>${current}</strong> — ingen nyare version hittades.`;
    if (installInfo.newerThanServer && remote) {
      statusLine = `Installerad version <strong>${current}</strong> — du har nyare än servern (<strong>${remote}</strong>).`;
    }
    const remoteLine = remote && remote !== current && !installInfo.newerThanServer
      ? `<p class="hint">Servern anger senaste version <strong>${remote}</strong>.</p>`
      : "";
    panel.innerHTML = `
      <h2>ANPR är installerat</h2>
      <p>${statusLine}</p>
      ${remoteLine}
      <p class="hint">Behöver du ändra kamera eller token? Gå vidare i guiden — dina nuvarande inställningar fylls i automatiskt.</p>
    `;
    return;
  }

  let remoteLine;
  if (hasRemote && remote) {
    remoteLine = `Ny version tillgänglig: <strong>${remote}</strong> (du har ${current})`;
  } else if (hasLocal && installInfo.availableVersion) {
    remoteLine = `Ny version i den här mappen: <strong>${installInfo.availableVersion}</strong> (du har ${current})`;
  } else {
    remoteLine = "En nyare version finns tillgänglig.";
  }

  panel.innerHTML = `
    <h2>Uppdatering tillgänglig</h2>
    <p>${remoteLine}</p>
    <p>Klicka nedan — programmet laddas ner och installeras automatiskt. Kamera, token och inställningar behålls.</p>
    <div class="prereq-toolbar">
      <button type="button" class="btn primary small" id="btn-update-remote">Uppdatera automatiskt</button>
      ${hasLocal ? '<button type="button" class="btn ghost small" id="btn-update">Uppdatera från den här mappen</button>' : ""}
    </div>
    <p class="update-progress hidden" id="update-progress"></p>
  `;

  $("btn-update-remote")?.addEventListener("click", () => startUpdate("/api/update/remote"));
  $("btn-update")?.addEventListener("click", () => startUpdate("/api/update"));
}

async function startUpdate(url = "/api/update") {
  const btnRemote = $("btn-update-remote");
  const btnLocal = $("btn-update");
  const progress = $("update-progress");
  if (btnRemote) btnRemote.disabled = true;
  if (btnLocal) btnLocal.disabled = true;
  if (progress) {
    progress.classList.remove("hidden");
    progress.textContent = "Uppdaterar… Det kan ta några minuter. Stäng inte fönstret.";
  }

  await fetch(url, { method: "POST" });
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const res = await fetch("/api/install/status");
    const data = await res.json();
    if (progress) progress.textContent = data.message || "Arbetar…";

    if (data.status === "running") return;

    clearInterval(pollTimer);
    pollTimer = null;
    if (data.status === "done") {
      await loadExistingInstall();
      if (progress) progress.textContent = "Klart! ANPR har startats om.";
      if (btnRemote) btnRemote.disabled = false;
      if (btnLocal) btnLocal.disabled = false;
    }
    if (data.status === "error") {
      alert("Fel: " + (data.error || data.message));
      if (btnRemote) btnRemote.disabled = false;
      if (btnLocal) btnLocal.disabled = false;
    }
  }, 800);
}

async function loadPrereqs() {
  const res = await fetch("/api/check");
  const data = await res.json();
  prereqData = data;
  renderPrereqs(data);
  updateNextForPrereqs();
}

function renderPrereqs(data) {
  const panel = $("prereq-panel");
  const canAutoAny = data.items.some((item) => !item.ok && item.can_auto_install);

  const toolbar = canAutoAny
    ? `<div class="prereq-toolbar">
         <button type="button" class="btn primary small" id="btn-install-all">Installera allt automatiskt</button>
         <button type="button" class="btn ghost small" id="btn-recheck">Kontrollera igen</button>
       </div>`
    : `<div class="prereq-toolbar">
         <button type="button" class="btn ghost small" id="btn-recheck">Kontrollera igen</button>
       </div>`;

  const rows = data.items
    .map((item) => {
      const statusClass = item.ok ? "ok" : "missing";
      const icon = item.ok ? "✓" : "!";
      const manual = item.manual_url
        ? `<a href="${item.manual_url}" target="_blank" rel="noopener">Ladda ner manuellt</a>`
        : "";
      const hint = item.manual_hint ? `<span>${item.manual_hint}</span>` : "";
      const installBtn =
        !item.ok && item.can_auto_install
          ? `<button type="button" class="btn primary small" data-install="${item.id}">Installera</button>`
          : "";
      return `
        <div class="prereq-row ${statusClass}">
          <div class="prereq-info">
            <strong>${icon} ${item.name}</strong>
            <span>${item.message}</span>
            ${hint}
            ${manual}
          </div>
          <div class="prereq-actions">${installBtn}</div>
        </div>`;
    })
    .join("");

  panel.innerHTML = toolbar + rows;

  const restart = $("prereq-restart-hint");
  if (data.restart_hint && !data.ok) {
    restart.textContent = data.restart_hint;
    restart.classList.remove("hidden");
  } else {
    restart.classList.add("hidden");
  }

  $("btn-recheck")?.addEventListener("click", loadPrereqs);
  $("btn-install-all")?.addEventListener("click", () => startPrereqInstall("/api/prerequisites/install-all"));
  panel.querySelectorAll("[data-install]").forEach((btn) => {
    btn.addEventListener("click", () =>
      startPrereqInstall(`/api/prerequisites/install/${btn.dataset.install}`)
    );
  });
}

async function startPrereqInstall(url) {
  $("btn-next").disabled = true;
  const panel = $("prereq-panel");
  const status = document.createElement("p");
  status.className = "prereq-status-msg";
  status.id = "prereq-status-msg";
  status.textContent = "Installerar… Det kan ta några minuter.";
  panel.prepend(status);

  await fetch(url, { method: "POST" });
  if (prereqPollTimer) clearInterval(prereqPollTimer);
  prereqPollTimer = setInterval(pollPrereqInstall, 1000);
}

async function pollPrereqInstall() {
  const res = await fetch("/api/prerequisites/status");
  const data = await res.json();
  const msg = $("prereq-status-msg");
  if (msg) msg.textContent = data.message || "Arbetar…";

  if (data.status === "running") return;

  clearInterval(prereqPollTimer);
  prereqPollTimer = null;
  await loadPrereqs();

  if (data.result?.needs_restart) {
    alert(
      (data.result.message || "Installation klar.") +
        "\n\nStäng guiden och starta Install ANPR igen."
    );
  }
}

async function loadSites() {
  const res = await fetch("/api/sites");
  const data = await res.json();
  sites = data.sites;
  defaultBackend = data.defaultBackendUrl;
  $("site").innerHTML = sites
    .map((s) => `<option value="${s.id}">${s.label}</option>`)
    .join("");
  $("backend-url").value = defaultBackend;
}

async function startInstall() {
  $("progress-wrap").classList.remove("hidden");
  $("progress-msg").textContent =
    "Startar installation… första gången kan det ta 10–15 minuter. Stäng inte fönstret.";
  $("btn-next").disabled = true;
  $("btn-back").disabled = true;

  const type = camType();
  const body = {
    site_id: $("site").value,
    camera_ip: $("camera-ip").value.trim(),
    camera_type: type,
    camera_port: Number($("camera-port").value),
    rtsp_path: type === "tapo" ? "/stream1" : $("rtsp-path").value,
    rtsp_user: $("rtsp-user").value.trim(),
    rtsp_password: $("rtsp-pass").value,
    camera_id: $("camera-id").value.trim() || "entrance-1",
    direction: $("direction").value,
    backend_url: $("backend-url").value.trim(),
    anpr_token: $("token").value.trim(),
  };

  await fetch("/api/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  pollTimer = setInterval(pollStatus, 800);
}

async function pollStatus() {
  const res = await fetch("/api/install/status");
  const data = await res.json();
  $("progress-msg").textContent = data.message || "Arbetar...";

  if (data.status === "running") {
    $("progress-fill").style.width = "65%";
  }
  if (data.status === "done") {
    $("progress-fill").style.width = "100%";
    clearInterval(pollTimer);
    setTimeout(() => setStep(5), 600);
  }
  if (data.status === "error") {
    clearInterval(pollTimer);
    $("btn-next").disabled = false;
    $("btn-back").disabled = false;
    alert("Fel: " + (data.error || data.message));
  }
}

$("btn-next").addEventListener("click", async () => {
  if (currentStep === 5) {
    window.close();
    return;
  }
  if (currentStep < 4) {
    if (!validateStep(currentStep)) return;
    if (currentStep === 3) {
      $("btn-next").disabled = true;
      const ok = await validateBackendCredentials();
      $("btn-next").disabled = false;
      if (!ok) return;
    }
    setStep(currentStep + 1);
    return;
  }
  if (currentStep === 4) {
    if (!validateStep(3)) {
      setStep(3);
      return;
    }
    $("btn-next").disabled = true;
    const tokenOk = await validateBackendCredentials();
    $("btn-next").disabled = false;
    if (!tokenOk) {
      setStep(3);
      return;
    }
    await startInstall();
  }
});

$("btn-back").addEventListener("click", () => {
  if (currentStep > 0) setStep(currentStep - 1);
});

$("btn-open").addEventListener("click", () => {
  window.open("http://127.0.0.1:8080", "_blank");
});

document.querySelectorAll('input[name="cam-type"]').forEach((el) => {
  el.addEventListener("change", updateCameraUi);
});
["camera-ip", "camera-port", "rtsp-path", "rtsp-user", "rtsp-pass"].forEach((id) => {
  $(id).addEventListener("input", updateCameraUi);
});

buildNav();
setStep(0);

async function initWizard() {
  await Promise.all([loadPrereqs(), loadSites()]);
  await loadExistingInstall();
  if (!installInfo.savedConfig) {
    updateCameraUi();
  }
}

initWizard();
