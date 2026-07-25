(() => {
  const NAV = [
    {
      group: "Drift",
      items: [
        { id: "overview", label: "Översikt", icon: "◫", title: "Översikt", subtitle: "Driftstatus och snabbkontroller" },
        { id: "cameras", label: "Kameror", icon: "◎", title: "Kameror", subtitle: "Live-förhandsbild och anslutningsstatus" },
        { id: "events", label: "Händelser", icon: "≡", title: "Händelser", subtitle: "Detekteringar och leveranser" },
      ],
    },
    {
      group: "Support",
      items: [
        { id: "logs", label: "Loggar", icon: "▤", title: "Loggar", subtitle: "Felsökning och export till IT" },
        { id: "system", label: "System", icon: "⚙", title: "System", subtitle: "Backend, OCR, kö och strömmar" },
      ],
    },
    {
      group: "Admin",
      items: [
        { id: "updates", label: "Uppdatering", icon: "↑", title: "Uppdatering", subtitle: "Version och uppdatering" },
        { id: "settings", label: "Inställningar", icon: "⎘", title: "Inställningar", subtitle: "Miljövariabler (skrivskyddad vy)" },
      ],
    },
  ];

  const AGENT_LABELS = {
    stopped: { text: "Stoppad", hint: "Tryck Starta för att börja läsa registreringsskyltar.", cls: "stopped" },
    running: { text: "Aktiv", hint: "Systemet läser registreringsskyltar från kamerorna.", cls: "running" },
    starting: { text: "Startar", hint: "Ansluter till kamerorna — vänta ett ögonblick.", cls: "stopped" },
    stopping: { text: "Stoppar", hint: "Avslutar kameraströmmar.", cls: "stopped" },
    error: { text: "Fel", hint: "Något gick fel. Prova Starta igen eller kontakta IT.", cls: "error" },
  };

  const CAMERA_STATE_LABELS = {
    connected: "Ansluten",
    connecting: "Ansluter",
    reconnecting: "Återansluter",
    disconnected: "Frånkopplad",
    error: "Fel",
    unconfigured: "Ej konfigurerad",
  };

  const EVENT_LABELS = {
    delivered: { text: "Levererad", cls: "ok" },
    queued: { text: "I kö", cls: "warn" },
    failed: { text: "Misslyckad", cls: "err" },
    detected: { text: "Detekterad", cls: "warn" },
  };

  let currentPage = "overview";
  let statusData = null;
  let eventsData = [];
  let queueData = { queue: [], size: 0 };
  let settingsData = null;
  let updateData = null;
  let agentBusy = false;
  let updateBusy = false;
  let updatePollTimer = null;
  let logPaused = false;
  let logBusy = false;
  let logSearchTimer = null;
  let previewTimers = [];
  let pollTimer = null;

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function capitalize(value) {
    if (!value) return "—";
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  function fmtTimeShort(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  function tag(status) {
    const item = EVENT_LABELS[status] || { text: status, cls: "warn" };
    return `<span class="tag ${item.cls}">${escapeHtml(item.text)}</span>`;
  }

  function cameraLabel(cameraId) {
    const camera = (statusData?.cameras || []).find((item) => item.id === cameraId);
    return camera?.label || cameraId || "—";
  }

  function cameraStatusTag(status) {
    const label = CAMERA_STATE_LABELS[status] || status;
    const cls = status === "connected" ? "ok" : status === "error" || status === "disconnected" ? "err" : "warn";
    return `<span class="tag ${cls}">${escapeHtml(label)}</span>`;
  }

  function goto(pageId) {
    currentPage = pageId;
    document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
    $(`page-${pageId}`)?.classList.add("active");
    const item = NAV.flatMap((group) => group.items).find((entry) => entry.id === pageId);
    if (item) {
      $("page-title").textContent = item.title;
      $("page-subtitle").textContent = item.subtitle;
    }
    renderNav();
    history.replaceState(null, "", `#${pageId}`);
    if (pageId === "logs") refreshLogs(true);
    if (pageId === "settings" && !settingsData) refreshSettings();
    if (pageId === "updates") refreshUpdateStatus();
    if (pageId === "cameras") startPreviewPolling();
    else stopPreviewPolling();
  }

  function renderNav() {
    const nav = $("sidebar-nav");
    nav.innerHTML = NAV.map((group) => `
      <div class="nav-group">
        <div class="nav-group-label">${group.group}</div>
        ${group.items.map((item) => `
          <button class="nav-item${item.id === currentPage ? " active" : ""}" data-page="${item.id}" type="button">
            <span class="nav-icon">${item.icon}</span>${item.label}
          </button>
        `).join("")}
      </div>
    `).join("");
    nav.querySelectorAll(".nav-item").forEach((button) => {
      button.addEventListener("click", () => goto(button.dataset.page));
    });
  }

  function renderHeader() {
    if (!statusData) return;

    const hints = statusData.bookingHints || {};
    let hintsText = "";
    if (hints.enabled) {
      hintsText = ` · ${hints.plateCount ?? 0} bokade idag`;
      if (hints.lastError) hintsText += " · bokningar ej hämtade";
      else if (!hints.refreshedAt) hintsText += " · hämtar bokningar";
    }

    const cameras = statusData.cameras || [];
    const siteLabel = cameras.length > 1
      ? `${capitalize(statusData.site?.siteId)} · ${cameras.length} kameror${hintsText}`
      : `${capitalize(statusData.site?.siteId)}${hintsText}`;

    $("nav-site").textContent = siteLabel;
    $("nav-version").textContent = `v${statusData.version || window.__ANPR_VERSION || "?"}`;
    $("topbar-version").textContent = `v${statusData.version || window.__ANPR_VERSION || "?"}`;
    $("nav-host").textContent = statusData.host?.hostname || "—";

    const agentState = statusData.agent?.state || "stopped";
    const badge = $("header-badge");
    if (agentState === "running") {
      badge.className = "badge ok";
      badge.innerHTML = '<span class="dot"></span>Aktiv';
    } else if (agentState === "error") {
      badge.className = "badge err";
      badge.innerHTML = '<span class="dot"></span>Fel';
    } else {
      badge.className = "badge warn";
      badge.innerHTML = '<span class="dot"></span>Stoppad';
    }
  }

  function renderHero() {
    if (!statusData) return;
    const state = statusData.agent?.state || "stopped";
    const meta = AGENT_LABELS[state] || AGENT_LABELS.stopped;
    const hero = $("hero");
    hero.className = `hero ${meta.cls}`;
    $("hero-title").textContent = meta.text;
    $("hero-hint").textContent = statusData.agent?.message || meta.hint;
    $("btn-start").disabled = agentBusy || state === "running" || state === "starting";
    $("btn-stop").disabled = agentBusy || state === "stopped" || state === "stopping";
  }

  function renderOverview() {
    if (!statusData) return;

    const hints = statusData.bookingHints || {};
    $("stat-bookings").textContent = hints.enabled ? (hints.plateCount ?? 0) : "—";
    $("stat-delivered").textContent = statusData.queue?.deliveries_succeeded ?? 0;
    $("stat-failed").textContent = `${statusData.queue?.deliveries_failed ?? 0} misslyckade`;

    const last = statusData.lastDetection;
    $("stat-plate").textContent = last?.plate || "—";
    $("stat-plate-time").textContent = last?.seen_at ? fmtTimeShort(last.seen_at) : "Ingen detektering ännu";

    const cameras = statusData.cameras || [];
    const online = cameras.filter((camera) => camera.status === "connected").length;
    $("stat-cameras").textContent = `${online}/${cameras.length || 0}`;
    $("stat-cameras-sub").textContent = cameras.length
      ? cameras.map((camera) => camera.label || camera.id).join(", ")
      : "Ingen kamera konfigurerad";

    $("overview-events").innerHTML = eventsData.slice(0, 5).length
      ? eventsData.slice(0, 5).map((event) => `
        <tr>
          <td>${escapeHtml(fmtTimeShort(event.capturedAt))}</td>
          <td class="mono">${escapeHtml(event.plate)}</td>
          <td>${Math.round((event.confidence || 0) * 100)}%</td>
          <td>${tag(event.status)}</td>
        </tr>
      `).join("")
      : '<tr><td colspan="4" class="empty">Inga händelser ännu</td></tr>';

    const backendOk = statusData.backend?.ok;
    const ocrReady = statusData.anpr?.ready;
    $("overview-health").innerHTML = `
      <div class="status-row"><span class="status-label">Backend</span><span class="status-val ${backendOk ? "ok" : "warn"}">${backendOk ? "OK" : "Fel"}</span></div>
      <div class="status-row"><span class="status-label">OCR</span><span class="status-val ${ocrReady ? "ok" : "warn"}">${ocrReady ? "Redo" : "Fel"}</span></div>
      <div class="status-row"><span class="status-label">Heartbeat</span><span class="status-val ${statusData.heartbeat?.enabled ? "ok" : ""}">${statusData.heartbeat?.enabled ? "OK" : "Av"}</span></div>
      <div class="status-row"><span class="status-label">Kö</span><span class="status-val">${queueData.size ?? 0} väntande</span></div>
    `;
  }

  function previewUrl(cameraId) {
    return `/api/cameras/${encodeURIComponent(cameraId)}/preview?t=${Date.now()}`;
  }

  function renderCameras() {
    const cameras = statusData?.cameras || [];
    if (!cameras.length) {
      $("camera-grid").innerHTML = '<div class="card"><div class="empty">Ingen kamera konfigurerad</div></div>';
      return;
    }

    $("camera-grid").innerHTML = cameras.map((camera, index) => `
      <div class="card">
        <div class="card-body">
          <div class="camera-card" style="border:none;padding:0">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:12px">
              <h3>${escapeHtml(camera.label || camera.id)}</h3>
              ${cameraStatusTag(camera.status)}
            </div>
            <div class="camera-meta">
              ID: <span class="mono">${escapeHtml(camera.id)}</span> · Riktning: ${escapeHtml(camera.direction || "—")}
            </div>
            <div class="camera-preview" id="camera-preview-wrap-${index}">
              <img id="camera-preview-${index}" alt="Kamerabild ${escapeHtml(camera.label || camera.id)}" hidden>
              <div class="camera-preview-placeholder" id="camera-preview-ph-${index}">Väntar på bild…</div>
              <div class="camera-preview-overlay"></div>
              <div class="camera-live"><span class="dot"></span>Live</div>
              <div class="camera-preview-time" id="camera-preview-time-${index}">${escapeHtml(fmtTime(camera.lastFrameAt))}</div>
            </div>
            <div class="camera-preview-note">Senaste bildruta från agenten · uppdateras var 2:e sekund</div>
            <div class="camera-meta" style="margin-top:10px"><span class="mono">${escapeHtml(camera.streamUrl || "—")}</span></div>
          </div>
        </div>
      </div>
    `).join("");

    cameras.forEach((camera, index) => refreshCameraPreview(camera, index));
  }

  async function refreshCameraPreview(camera, index) {
    const img = $(`camera-preview-${index}`);
    const placeholder = $(`camera-preview-ph-${index}`);
    const timeEl = $(`camera-preview-time-${index}`);
    if (!img) return;

    try {
      const response = await fetch(previewUrl(camera.id));
      if (!response.ok) throw new Error("no preview");
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
      img.dataset.objectUrl = objectUrl;
      img.src = objectUrl;
      img.hidden = false;
      if (placeholder) placeholder.hidden = true;
      if (timeEl) timeEl.textContent = fmtTime(new Date().toISOString());
    } catch {
      img.hidden = true;
      if (placeholder) {
        placeholder.hidden = false;
        placeholder.textContent = camera.status === "connected"
          ? "Ingen bild ännu — väntar på nästa frame"
          : (camera.statusMessage || "Kamera ej ansluten");
      }
      if (timeEl && camera.lastFrameAt) timeEl.textContent = fmtTime(camera.lastFrameAt);
    }
  }

  function startPreviewPolling() {
    stopPreviewPolling();
    const cameras = statusData?.cameras || [];
    if (!cameras.length) return;
    previewTimers.push(setInterval(() => {
      cameras.forEach((camera, index) => refreshCameraPreview(camera, index));
    }, 2000));
  }

  function stopPreviewPolling() {
    previewTimers.forEach(clearInterval);
    previewTimers = [];
  }

  function renderEvents(filter = "") {
    const query = filter.trim().toUpperCase();
    const rows = eventsData.filter((event) => !query || String(event.plate || "").toUpperCase().includes(query));
    $("events-body").innerHTML = rows.length
      ? rows.map((event) => `
        <tr>
          <td>${escapeHtml(fmtTime(event.capturedAt))}</td>
          <td class="mono">${escapeHtml(event.plate)}</td>
          <td>${escapeHtml(cameraLabel(event.cameraId))}</td>
          <td>${Math.round((event.confidence || 0) * 100)}%</td>
          <td>${tag(event.status)}</td>
        </tr>
      `).join("")
      : '<tr><td colspan="5" class="empty">Inga händelser ännu</td></tr>';
  }

  function renderSystem() {
    if (!statusData) return;

    const backend = statusData.backend || {};
    const heartbeat = statusData.heartbeat || {};
    const anpr = statusData.anpr || {};
    const remote = statusData.remoteCameraConfig || {};

    $("system-connections").innerHTML = `
      <div class="status-row"><span class="status-label">Backend</span><span class="status-val ${backend.ok ? "ok" : "warn"}">${backend.ok ? "OK" : "Fel"}</span></div>
      <div class="status-row"><span class="status-label">Token</span><span class="status-val mono">…${escapeHtml(backend.tokenHint || "????")}</span></div>
      <div class="status-row"><span class="status-label">Heartbeat</span><span class="status-val ${heartbeat.enabled ? "ok" : ""}">${heartbeat.enabled ? `OK · var ${heartbeat.intervalSeconds || "?"}s` : "Av"}</span></div>
      <div class="status-row"><span class="status-label">Senaste heartbeat</span><span class="status-val">${escapeHtml(fmtTime(heartbeat.lastSentAt))}</span></div>
    `;

    $("system-ocr").innerHTML = `
      <div class="status-row"><span class="status-label">Provider</span><span class="status-val">${escapeHtml(anpr.provider || "—")}</span></div>
      <div class="status-row"><span class="status-label">OCR</span><span class="status-val ${anpr.ready ? "ok" : "warn"}">${anpr.ready ? "Redo" : "Fel"}</span></div>
      <div class="status-row"><span class="status-label">Bearbetar</span><span class="status-val">${anpr.ocrProcessing ? "Ja" : "Nej"}</span></div>
      <div class="status-row"><span class="status-label">Cooldown</span><span class="status-val">${anpr.cooldownSeconds ?? "—"}s</span></div>
      <div class="status-row"><span class="status-label">Köade bilder</span><span class="status-val">${anpr.pendingFrames ?? 0}</span></div>
    `;

    $("system-queue").innerHTML = `
      <div class="status-row"><span class="status-label">Levererade</span><span class="status-val">${statusData.queue?.deliveries_succeeded ?? 0}</span></div>
      <div class="status-row"><span class="status-label">Misslyckade</span><span class="status-val">${statusData.queue?.deliveries_failed ?? 0}</span></div>
      <div class="status-row"><span class="status-label">I kö</span><span class="status-val">${queueData.size ?? 0}</span></div>
    `;

    const streams = remote.cameras || [];
    $("system-streams").innerHTML = remote.enabled
      ? (streams.length
        ? streams.map((camera) => `
          <div style="margin-bottom:12px;font-size:0.85rem">
            <strong>${escapeHtml(camera.label || camera.id)}${camera.direction ? ` · ${escapeHtml(camera.direction)}` : ""}</strong><br>
            <span class="mono" style="color:var(--text-secondary)">${escapeHtml(camera.streamUrl || "—")}</span><br>
            <span style="color:var(--text-tertiary);font-size:0.78rem">Uppdaterad ${escapeHtml(fmtTime(remote.lastUpdatedAt))} · var ${remote.refreshSeconds || 60}:e sekund</span>
          </div>
        `).join("")
        : '<div class="empty">Inga fjärrströmmar</div>')
      : '<div class="empty">Fjärrkonfiguration av kameror är av</div>';
  }

  function renderSettings() {
    if (!settingsData) {
      $("settings-env").innerHTML = '<div class="empty">Laddar…</div>';
      return;
    }
    const entries = Object.entries(settingsData.settings || {});
    $("settings-path").textContent = settingsData.configPath || "—";
    $("settings-env").innerHTML = entries.length
      ? entries.map(([key, value]) => `
        <div class="setting-row">
          <div class="setting-key">${escapeHtml(key)}</div>
          <div class="setting-val">${escapeHtml(value)}</div>
        </div>
      `).join("")
      : '<div class="empty">Ingen .env hittades</div>';
  }

  function renderUpdates() {
    const banner = $("update-banner");
    const info = $("update-info");
    const actions = $("update-actions");
    if (!updateData) {
      banner.className = "alert info hidden";
      info.innerHTML = '<div class="empty">Laddar versionsinformation…</div>';
      actions.innerHTML = "";
      return;
    }

    const job = updateData.job || {};
    const jobStatus = job.status;
    banner.className = "alert hidden";

    if (jobStatus === "running") {
      banner.className = "alert info";
      banner.innerHTML = `<span><strong>Uppdaterar…</strong> ${escapeHtml(job.message || "Det kan ta några minuter.")}</span>`;
    } else if (jobStatus === "failed") {
      banner.className = "alert failed";
      banner.innerHTML = `<span><strong>Uppdatering misslyckades.</strong> ${escapeHtml(job.error || job.message || "Försök igen.")}</span>`;
    } else if (jobStatus === "completed") {
      banner.className = "alert success";
      banner.innerHTML = `<span><strong>Uppdatering klar</strong>${job.newVersion ? ` v${escapeHtml(job.newVersion)}` : ""}.</span>`;
    } else if (updateData.updateAvailable) {
      banner.className = "alert info";
      banner.innerHTML = `<span>Ny version tillgänglig: <strong>v${escapeHtml(updateData.remoteVersion || "?")}</strong> (du har v${escapeHtml(updateData.currentVersion || "?")}).</span>`;
    }

    info.innerHTML = `
      <div class="setting-row"><div class="setting-key">Installerad</div><div class="setting-val">${escapeHtml(updateData.currentVersion || statusData?.version || "—")}</div></div>
      <div class="setting-row"><div class="setting-key">Senaste godkända</div><div class="setting-val">${escapeHtml(updateData.remoteVersion || "—")}</div></div>
      <div class="setting-row"><div class="setting-key">Källa</div><div class="setting-val">${escapeHtml(updateData.updateSource || "—")}</div></div>
      <div class="setting-row"><div class="setting-key">Uppdatering tillgänglig</div><div class="setting-val">${updateData.updateAvailable ? "Ja" : "Nej"}</div></div>
    `;

    if (updateData.updateAvailable && jobStatus !== "running") {
      actions.innerHTML = `<button class="btn btn-primary" id="btn-update" type="button">${updateBusy ? "Startar…" : `Uppdatera till v${escapeHtml(updateData.remoteVersion || "?")}`}</button>`;
      $("btn-update")?.addEventListener("click", startUpdate);
    } else {
      actions.innerHTML = "";
    }
  }

  async function refreshStatus() {
    try {
      const [status, events, queue] = await Promise.all([
        fetch("/api/status").then((response) => response.json()),
        fetch("/api/events?limit=50").then((response) => response.json()),
        fetch("/api/queue").then((response) => response.json()),
      ]);
      statusData = status;
      eventsData = events.events || [];
      queueData = queue;
      renderHeader();
      renderHero();
      renderOverview();
      renderCameras();
      renderEvents($("event-search")?.value || "");
      renderSystem();
      if (currentPage === "cameras") startPreviewPolling();
    } catch (error) {
      console.error(error);
    }
  }

  async function refreshSettings() {
    try {
      settingsData = await fetch("/api/settings").then((response) => response.json());
      renderSettings();
    } catch (error) {
      $("settings-env").innerHTML = '<div class="empty">Kunde inte läsa inställningar</div>';
    }
  }

  async function refreshUpdateStatus() {
    try {
      updateData = await fetch("/api/update/status").then((response) => response.json());
      renderUpdates();
      if (updateData?.job?.status === "running" && !updatePollTimer) {
        updatePollTimer = setInterval(async () => {
          await refreshUpdateStatus();
          if (updateData?.job?.status !== "running") {
            clearInterval(updatePollTimer);
            updatePollTimer = null;
            updateBusy = false;
            await refreshStatus();
          }
        }, 3000);
      }
    } catch (error) {
      $("update-info").innerHTML = '<div class="empty">Kunde inte hämta versionsstatus</div>';
    }
  }

  function highlightSearch(text, query) {
    const safe = escapeHtml(text || "");
    if (!query) return safe;
    const pattern = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig");
    return safe.replace(pattern, '<mark class="log-mark">$1</mark>');
  }

  function logLevelClass(level) {
    const normalized = String(level || "INFO").toLowerCase();
    if (normalized === "warning") return "log-level-warning";
    if (normalized === "error" || normalized === "critical") return "log-level-error";
    return "log-level-info";
  }

  function renderLogLine(entry, query) {
    const time = entry.timestamp ? escapeHtml(entry.timestamp) : "—";
    const level = escapeHtml(entry.level || "INFO");
    const source = entry.source ? `[${escapeHtml(entry.source)}] ` : "";
    const message = highlightSearch(entry.message || entry.raw || "", query);
    const event = entry.event ? ` · ${highlightSearch(entry.event, query)}` : "";
    return `<div class="log-line"><span class="log-time">${time}</span> ` +
      `<span class="${logLevelClass(entry.level)}">${level}</span> ` +
      `${source}${message}${event}</div>`;
  }

  async function refreshLogs(force = false) {
    if (logPaused && !force) return;
    if (logBusy) return;
    logBusy = true;

    const level = $("log-level")?.value || "";
    const source = $("log-source")?.value || "all";
    const query = $("log-search")?.value?.trim() || "";
    const params = new URLSearchParams({ tail: query ? "200" : "100", source });
    if (level) params.set("level", level);
    if (query) params.set("q", query);

    const view = $("log-view");
    try {
      const data = await fetch(`/api/logs?${params}`).then((response) => response.json());
      const files = (data.files || []).map((file) => `${file.name} (${file.size} B)`).join(" · ");
      const matchInfo = query
        ? `${data.matched || 0} träffar (sökte ${data.scanned || 0} rader)`
        : `${(data.entries || []).length} rader`;
      $("log-meta").textContent = `${data.logDir || "—"}${files ? ` · ${files}` : ""} · ${matchInfo}`;
      if (!data.entries?.length) {
        view.innerHTML = '<span class="empty">Inga loggrader matchar sökningen.</span>';
      } else {
        view.innerHTML = data.entries.map((entry) => renderLogLine(entry, query)).join("");
        view.scrollTop = view.scrollHeight;
      }
    } catch {
      view.textContent = "Kunde inte läsa loggar";
    } finally {
      logBusy = false;
    }
  }

  async function startAgent() {
    if (agentBusy) return;
    agentBusy = true;
    renderHero();
    try {
      const response = await fetch("/api/agent/start", { method: "POST" });
      const data = await response.json();
      $("hero-hint").textContent = data.message || data.detail || (response.ok ? "Startad" : "Kunde inte starta");
    } catch {
      $("hero-hint").textContent = "Kunde inte nå agenten";
    }
    agentBusy = false;
    await refreshStatus();
  }

  async function stopAgent() {
    if (agentBusy) return;
    agentBusy = true;
    renderHero();
    try {
      const response = await fetch("/api/agent/stop", { method: "POST" });
      const data = await response.json();
      $("hero-hint").textContent = data.message || data.detail || (response.ok ? "Stoppad" : "Kunde inte stoppa");
    } catch {
      $("hero-hint").textContent = "Kunde inte nå agenten";
    }
    agentBusy = false;
    await refreshStatus();
  }

  async function startUpdate() {
    if (updateBusy) return;
    updateBusy = true;
    renderUpdates();
    try {
      const response = await fetch("/api/update/start", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Uppdatering misslyckades");
      await refreshUpdateStatus();
    } catch (error) {
      $("update-banner").className = "alert failed";
      $("update-banner").innerHTML = `<span>${escapeHtml(error.message || "Uppdatering misslyckades")}</span>`;
      updateBusy = false;
      renderUpdates();
    }
  }

  async function exportLogs() {
    const button = $("log-export-btn");
    if (!button || button.disabled) return;
    button.disabled = true;
    button.textContent = "Skickar…";
    try {
      const response = await fetch("/api/logs/export", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Export misslyckades");
      button.textContent = "Skickat!";
    } catch (error) {
      button.textContent = "Misslyckades";
      alert(error.message || "Kunde inte exportera loggar");
    } finally {
      setTimeout(() => {
        button.disabled = false;
        button.textContent = "Skicka till IT";
      }, 2500);
    }
  }

  function applyLogChip(button) {
    document.querySelectorAll(".log-chip").forEach((chip) => chip.classList.remove("active"));
    button.classList.add("active");
    $("log-search").value = button.dataset.query || "";
    if ($("log-pause")) $("log-pause").checked = true;
    logPaused = true;
    refreshLogs(true);
  }

  function init() {
    renderNav();
    $("btn-start")?.addEventListener("click", startAgent);
    $("btn-stop")?.addEventListener("click", stopAgent);
    $("event-search")?.addEventListener("input", (event) => renderEvents(event.target.value));
    $("log-search")?.addEventListener("input", () => {
      clearTimeout(logSearchTimer);
      logSearchTimer = setTimeout(() => refreshLogs(true), 300);
    });
    $("log-level")?.addEventListener("change", () => refreshLogs(true));
    $("log-source")?.addEventListener("change", () => refreshLogs(true));
    $("log-pause")?.addEventListener("change", (event) => {
      logPaused = event.target.checked;
      if (!logPaused) refreshLogs(true);
    });
    $("log-export-btn")?.addEventListener("click", exportLogs);
    document.querySelectorAll(".log-chip").forEach((chip) => {
      chip.addEventListener("click", () => applyLogChip(chip));
    });
    document.querySelectorAll("[data-goto]").forEach((element) => {
      element.addEventListener("click", () => goto(element.dataset.goto));
    });

    const hash = location.hash.replace("#", "");
    if (hash && $(`page-${hash}`)) goto(hash);

    refreshStatus();
    pollTimer = setInterval(refreshStatus, 5000);
    setInterval(() => {
      if (currentPage === "logs" && !logPaused) refreshLogs();
    }, 4000);
  }

  window.__ANPR_VERSION = window.__ANPR_VERSION || "";
  init();
})();
