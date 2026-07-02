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
let savedHallCount = null;

const INSTALLER_OFFLINE_MSG =
  "Installationsguiden svarar inte (127.0.0.1:17880).\n\n" +
  "Låt terminalfönstret som startade guiden vara öppet.\n" +
  "Om det stängdes: öppna Terminal och kör python3 -m installer igen.";

const $ = (id) => document.getElementById(id);

function setServerOffline(offline) {
  const banner = $("server-offline-banner");
  if (banner) banner.classList.toggle("hidden", !offline);
  const btn = $("btn-next");
  if (btn && currentStep > 0 && currentStep < 5) {
    btn.disabled = offline;
  }
}

async function installerFetch(path, options = {}) {
  try {
    const res = await fetch(path, options);
    setServerOffline(false);
    return { ok: true, res };
  } catch {
    setServerOffline(true);
    return { ok: false, res: null };
  }
}

async function pingInstaller() {
  const result = await installerFetch("/api/ping", { cache: "no-store" });
  if (!result.ok || !result.res?.ok) {
    setServerOffline(true);
    return false;
  }
  setServerOffline(false);
  return true;
}

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
  return camTypeFor(1);
}

function camTypeFor(hallIndex) {
  const name = hallIndex === 2 ? "cam2-type" : "cam-type";
  return document.querySelector(`input[name="${name}"]:checked`).value;
}

function hallCount() {
  return Number($("hall-count").value || 1);
}

function selectedSite() {
  return sites.find((s) => s.id === $("site").value);
}

function needsAuth() {
  return needsAuthFor(camType());
}

function needsAuthFor(type) {
  return type === "tapo" || type === "rtsp";
}

function buildPreviewUrlFor(hallIndex = 1) {
  const isSecond = hallIndex === 2;
  const ip = $(isSecond ? "camera2-ip" : "camera-ip").value.trim();
  const port = $(isSecond ? "camera2-port" : "camera-port").value;
  if (!ip) return "";

  const type = camTypeFor(hallIndex);
  if (type === "ip_webcam") {
    return `http://${ip}:${port || 8080}/videofeed`;
  }
  const user = $(isSecond ? "rtsp2-user" : "rtsp-user").value.trim();
  const pass = $(isSecond ? "rtsp2-pass" : "rtsp-pass").value;
  const path =
    type === "tapo" ? "/stream1" : $(isSecond ? "rtsp2-path" : "rtsp-path").value || "/stream1";
  const auth =
    user && pass
      ? `${encodeURIComponent(user)}:${encodeURIComponent(pass)}@`
      : user
        ? `${encodeURIComponent(user)}@`
        : "";
  return `rtsp://${auth}${ip}:${port || 554}${path.startsWith("/") ? path : `/${path}`}`;
}

function buildPreviewUrl() {
  return buildPreviewUrlFor(1);
}

function readCameraForm(hallIndex = 1) {
  const isSecond = hallIndex === 2;
  const type = camTypeFor(hallIndex);
  return {
    camera_id: isSecond ? "hall-2" : "hall-1",
    label: isSecond ? "Hall 2" : "Hall 1",
    direction: "entry",
    camera_ip: $(isSecond ? "camera2-ip" : "camera-ip").value.trim(),
    camera_type: type,
    camera_port: Number($(isSecond ? "camera2-port" : "camera-port").value),
    rtsp_path: type === "tapo" ? "/stream1" : $(isSecond ? "rtsp2-path" : "rtsp-path").value,
    rtsp_user: $(isSecond ? "rtsp2-user" : "rtsp-user").value.trim(),
    rtsp_password: $(isSecond ? "rtsp2-pass" : "rtsp-pass").value,
  };
}

function buildInstallCameras() {
  const cameras = [readCameraForm(1)];
  if (hallCount() === 2) {
    cameras.push(readCameraForm(2));
  }
  return cameras;
}

function updateHallCountUi() {
  const count = hallCount();
  const site = selectedSite();
  $("hall-2-panel").classList.toggle("hidden", count < 2);
  $("hall-1-title").textContent = count > 1 ? "Hall 1" : "Kamera";

  const hint = $("hall-count-hint");
  if (site?.defaultHalls === 2) {
    hint.textContent = `${site.label} har två hallar med kamera.`;
  } else {
    hint.textContent =
      "Välj 2 om ni har (eller får) kamera i mer än en hall. Hall 1 räcker om ni bara har en kamera.";
  }

  const expandHint = $("hall-expand-hint");
  const showExpand =
    installInfo.installed && savedHallCount === 1 && count === 1;
  if (showExpand) {
    expandHint.textContent =
      "Har ni lagt till en ny hall? Välj 2 hallar ovan och fyll i den nya kameran i nästa steg. Hall 1 behåller sina nuvarande uppgifter.";
    expandHint.classList.remove("hidden");
  } else if (installInfo.installed && savedHallCount === 1 && count === 2) {
    expandHint.textContent =
      "Bra — fyll i kamerauppgifter för den nya hallen (Hall 2) i nästa steg.";
    expandHint.classList.remove("hidden");
  } else {
    expandHint.textContent = "";
    expandHint.classList.add("hidden");
  }
}

function prefillHallTwoFromHallOne() {
  if ($("camera2-ip").value.trim()) {
    return;
  }
  if (!$("rtsp2-user").value.trim() && $("rtsp-user").value.trim()) {
    $("rtsp2-user").value = $("rtsp-user").value;
  }
  if (!$("rtsp2-pass").value && $("rtsp-pass").value) {
    $("rtsp2-pass").value = $("rtsp-pass").value;
  }
  const type1 = camTypeFor(1);
  const type2Radio = document.querySelector(`input[name="cam2-type"][value="${type1}"]`);
  if (type2Radio) type2Radio.checked = true;
  if (!$("camera2-port").value || $("camera2-port").value === "554") {
    $("camera2-port").value = $("camera-port").value;
  }
}

function onHallCountChanged() {
  if (hallCount() === 2) {
    prefillHallTwoFromHallOne();
  }
  updateCameraUi();
}

function applyCameraToForm(camera, hallIndex = 1) {
  if (!camera) return;
  const isSecond = hallIndex === 2;
  if (camera.camera_ip) $(isSecond ? "camera2-ip" : "camera-ip").value = camera.camera_ip;
  if (camera.camera_port) {
    $(isSecond ? "camera2-port" : "camera-port").value = String(camera.camera_port);
  }
  if (camera.rtsp_path) $(isSecond ? "rtsp2-path" : "rtsp-path").value = camera.rtsp_path;
  if (camera.rtsp_user) $(isSecond ? "rtsp2-user" : "rtsp-user").value = camera.rtsp_user;
  if (camera.rtsp_password) $(isSecond ? "rtsp2-pass" : "rtsp-pass").value = camera.rtsp_password;
  if (camera.camera_type) {
    const name = isSecond ? "cam2-type" : "cam-type";
    const radio = document.querySelector(`input[name="${name}"][value="${camera.camera_type}"]`);
    if (radio) radio.checked = true;
  }
}

function updateCameraUiFor(hallIndex = 1) {
  const isSecond = hallIndex === 2;
  const type = camTypeFor(hallIndex);
  const auth = needsAuthFor(type);

  $(isSecond ? "auth-fields-2" : "auth-fields").classList.toggle("hidden", !auth);
  $(isSecond ? "rtsp-extra-2" : "rtsp-extra").classList.toggle("hidden", type !== "rtsp");

  const portEl = $(isSecond ? "camera2-port" : "camera-port");
  const pathEl = $(isSecond ? "rtsp2-path" : "rtsp-path");
  if (type === "tapo") {
    portEl.value = "554";
    pathEl.value = "/stream1";
  } else if (type === "ip_webcam") {
    portEl.value = "8080";
  } else if (type === "rtsp" && portEl.value === "8080") {
    portEl.value = "554";
  }

  const url = buildPreviewUrlFor(hallIndex);
  const preview = $(isSecond ? "camera2-preview" : "camera-preview");
  preview.textContent = url ? `Kamera-URL: ${url.replace(/:([^:@/]+)@/, ":****@")}` : "";
}

function updateCameraUi() {
  updateHallCountUi();
  updateCameraUiFor(1);
  if (hallCount() === 2) {
    updateCameraUiFor(2);
  }
}

function fillSummary() {
  const site = selectedSite();
  const cameras = buildInstallCameras();
  const cameraRows = cameras
    .map(
      (camera) =>
        `<dt>${camera.label}</dt><dd>${camera.camera_ip} (${CAM_LABELS[camera.camera_type] || camera.camera_type})</dd>`
    )
    .join("");
  $("summary").innerHTML = `
    <dt>Anläggning</dt><dd>${site?.label || "—"}</dd>
    <dt>Hallar</dt><dd>${cameras.length}</dd>
    ${cameraRows}
    <dt>Backend</dt><dd>${$("backend-url").value || "—"}</dd>
  `;
}

function validateCameraForm(hallIndex = 1) {
  const isSecond = hallIndex === 2;
  const ip = $(isSecond ? "camera2-ip" : "camera-ip").value.trim();
  if (!ip) {
    alert(isSecond ? "Ange kamera-IP för hall 2." : "Ange kamera-IP.");
    return false;
  }
  const type = camTypeFor(hallIndex);
  if (needsAuthFor(type)) {
    const user = $(isSecond ? "rtsp2-user" : "rtsp-user").value.trim();
    const pass = $(isSecond ? "rtsp2-pass" : "rtsp-pass").value;
    if (!user || !pass) {
      alert(
        isSecond
          ? "Ange användarnamn och lösenord för hall 2."
          : "Ange användarnamn och lösenord för kameran (Tapo Camera Account)."
      );
      return false;
    }
  }
  return true;
}

function validateStep(n) {
  if (n === 2) {
    if (!validateCameraForm(1)) return false;
    if (hallCount() === 2 && !validateCameraForm(2)) return false;
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
  const backendUrl = $("backend-url").value.trim();
  if (backendUrl.endsWith(".railway") && !backendUrl.endsWith(".railway.app")) {
    alert("Backend-URL ser ofullständig ut. Den ska sluta med .railway.app");
    return false;
  }

  const result = await installerFetch("/api/install/validate-credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_id: $("site").value,
      backend_url: backendUrl,
      anpr_token: $("token").value.trim(),
    }),
  });
  if (!result.ok) {
    alert(INSTALLER_OFFLINE_MSG);
    return false;
  }

  let data;
  try {
    data = await result.res.json();
  } catch {
    alert("Kunde inte läsa svar från guiden. Försök ladda om sidan.");
    return false;
  }

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

  if (cfg.hall_count) {
    $("hall-count").value = String(cfg.hall_count);
    savedHallCount = Number(cfg.hall_count);
  }

  if (Array.isArray(cfg.cameras) && cfg.cameras.length) {
    applyCameraToForm(cfg.cameras[0], 1);
    if (cfg.cameras[1]) {
      applyCameraToForm(cfg.cameras[1], 2);
    }
  } else {
    applyCameraToForm(cfg, 1);
  }

  if (cfg.backend_url) $("backend-url").value = cfg.backend_url;
  if (cfg.anpr_token) $("token").value = cfg.anpr_token;

  updateCameraUi();
}

function applyDefaultHallCountForSite() {
  const site = selectedSite();
  if (!site) return;
  $("hall-count").value = String(site.defaultHalls || 1);
}

function onSiteChanged() {
  if (!installInfo.savedConfig) {
    applyDefaultHallCountForSite();
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
      <p class="hint">Behöver ni ändra kamera, lägga till en hall eller uppdatera token? Gå vidare i guiden — nuvarande inställningar fylls i automatiskt.</p>
      ${
        installInfo.savedConfig?.hall_count === 1
          ? '<p class="hint"><strong>Ny hall?</strong> Välj <em>2 hallar</em> i nästa steg och fyll i den nya kameran.</p>'
          : ""
      }
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
  onSiteChanged();
}

async function startInstall() {
  $("progress-wrap").classList.remove("hidden");
  $("progress-msg").textContent =
    "Startar installation… första gången kan det ta 10–15 minuter. Stäng inte fönstret.";
  $("btn-next").disabled = true;
  $("btn-back").disabled = true;

  const body = {
    site_id: $("site").value,
    hall_count: hallCount(),
    cameras: buildInstallCameras(),
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
    setTimeout(() => {
      setStep(5);
      waitForAgentDashboard();
    }, 600);
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
  openAgentDashboard();
});

async function waitForAgentDashboard() {
  const lead = $("done-lead");
  for (let i = 0; i < 120; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:8080/api/version", { cache: "no-store" });
      if (res.ok) {
        if (lead) {
          lead.textContent = "ANPR är installerat och körs.";
        }
        window.open("http://127.0.0.1:8080", "_blank");
        return;
      }
    } catch (_) {}
    if (lead && i > 2) {
      lead.textContent = "ANPR startar — väntar på kontrollpanelen…";
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  if (lead) {
    lead.textContent =
      "Installation klar. Starta via Start ANPR på skrivbordet om kontrollpanelen inte öppnas.";
  }
}

async function openAgentDashboard() {
  for (let i = 0; i < 30; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:8080/api/version", { cache: "no-store" });
      if (res.ok) {
        window.open("http://127.0.0.1:8080", "_blank");
        return;
      }
    } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  alert(
    "ANPR svarar inte på http://127.0.0.1:8080.\n\n" +
      "Dubbelklicka Start ANPR på skrivbordet och lämna terminalfönstret öppet.\n\n" +
      "Logg: ~/Library/Application Support/anpr-edge-agent/logs/launchd-stderr.log",
  );
}

document.querySelectorAll('input[name="cam-type"]').forEach((el) => {
  el.addEventListener("change", updateCameraUi);
});
document.querySelectorAll('input[name="cam2-type"]').forEach((el) => {
  el.addEventListener("change", updateCameraUi);
});
[
  "camera-ip",
  "camera-port",
  "rtsp-path",
  "rtsp-user",
  "rtsp-pass",
  "camera2-ip",
  "camera2-port",
  "rtsp2-path",
  "rtsp2-user",
  "rtsp2-pass",
].forEach((id) => {
  $(id).addEventListener("input", updateCameraUi);
});
$("hall-count").addEventListener("change", onHallCountChanged);
$("site").addEventListener("change", onSiteChanged);

buildNav();
setStep(0);

async function initWizard() {
  await pingInstaller();
  window.setInterval(() => {
    pingInstaller();
  }, 8000);

  try {
    await Promise.all([loadPrereqs(), loadSites()]);
    await loadExistingInstall();
    if (!installInfo.savedConfig) {
      updateCameraUi();
    }
  } catch {
    setServerOffline(true);
  }
}

initWizard();
