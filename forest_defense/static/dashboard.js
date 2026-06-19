const healthEl = document.getElementById("health");
const deviceTotalEl = document.getElementById("deviceTotal");
const onlineTotalEl = document.getElementById("onlineTotal");
const staleTotalEl = document.getElementById("staleTotal");
const offlineTotalEl = document.getElementById("offlineTotal");
const deviceCardsEl = document.getElementById("deviceCards");
const incidentTotalEl = document.getElementById("incidentTotal");
const classBreakdownEl = document.getElementById("classBreakdown");
const deviceBreakdownEl = document.getElementById("deviceBreakdown");
const incidentRowsEl = document.getElementById("incidentRows");
const refreshButton = document.getElementById("refreshButton");
const deviceFilterEl = document.getElementById("deviceFilter");
const selectedIncidentBadgeEl = document.getElementById("selectedIncidentBadge");
const incidentDetailEl = document.getElementById("incidentDetail");
const operatorFormEl = document.getElementById("operatorForm");
const adminKeyInputEl = document.getElementById("adminKeyInput");
const operatorInputEl = document.getElementById("operatorInput");
const notesInputEl = document.getElementById("notesInput");
const acknowledgeButton = document.getElementById("acknowledgeButton");
const resolveButton = document.getElementById("resolveButton");
const reopenButton = document.getElementById("reopenButton");
const actionMessageEl = document.getElementById("actionMessage");

let selectedIncidentId = null;

function formatTime(value) {
  if (!value) return "Unknown";
  return new Date(value).toLocaleString();
}

function formatAge(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return `${value}s ago`;
  if (value < 3600) return `${Math.floor(value / 60)}m ago`;
  return `${Math.floor(value / 3600)}h ago`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderDevices(devices, health) {
  const currentValue = deviceFilterEl.value;
  deviceTotalEl.textContent = devices.length;
  onlineTotalEl.textContent = health.online || 0;
  staleTotalEl.textContent = health.stale || 0;
  offlineTotalEl.textContent = health.offline || 0;
  deviceCardsEl.innerHTML = devices.length
    ? devices.map((device) => `<button class="device-card ${device.health || device.status}" data-node-id="${device.node_id}" type="button">
        <strong>${device.node_id}</strong>
        <span>${device.health || device.status}</span>
        <small>${device.latitude}, ${device.longitude}</small>
        <small>Last seen ${formatAge(device.seconds_since_seen)}</small>
      </button>`).join("")
    : '<div class="empty-card">No devices registered</div>';

  const options = ['<option value="">All devices</option>'].concat(
    devices.map((device) => `<option value="${device.node_id}">${device.node_id}</option>`)
  );
  deviceFilterEl.innerHTML = options.join("");
  if (devices.some((device) => device.node_id === currentValue)) {
    deviceFilterEl.value = currentValue;
  }
}

function renderSummary(summary) {
  incidentTotalEl.textContent = summary.total_incidents || 0;
  const byClass = summary.by_class || {};
  const labels = Object.keys(byClass);
  classBreakdownEl.innerHTML = labels.length
    ? labels.map((label) => `<span class="chip">${label}: ${byClass[label]}</span>`).join("")
    : '<span class="chip">No alerts yet</span>';

  const byDevice = summary.by_device || {};
  const devices = Object.keys(byDevice);
  deviceBreakdownEl.innerHTML = devices.length
    ? devices.map((nodeId) => `<span class="chip device-chip">${nodeId}: ${byDevice[nodeId]}</span>`).join("")
    : "";
}

function renderIncidents(records) {
  if (!records.length) {
    incidentRowsEl.innerHTML = '<tr><td class="empty" colspan="6">No verified alerts logged</td></tr>';
    return;
  }

  incidentRowsEl.innerHTML = records
    .slice()
    .reverse()
    .map((record) => {
      const confidence = Number(record.confidence || 0).toFixed(3);
      const location = `${record.latitude}, ${record.longitude}`;
      const selected = selectedIncidentId === record.id ? " selected" : "";
      return `<tr class="incident-row${selected}" data-incident-id="${record.id}">
        <td>${formatTime(record.timestamp)}</td>
        <td>${escapeHtml(record.class_label)}</td>
        <td>${confidence}</td>
        <td><span class="status-tag ${record.status || "open"}">${escapeHtml(record.status || "open")}</span></td>
        <td>${escapeHtml(record.node_id)}</td>
        <td>${location}</td>
      </tr>`;
    })
    .join("");
}

function renderIncidentDetail(data) {
  const incident = data.incident;
  const events = data.events || [];
  selectedIncidentBadgeEl.textContent = incident.status || "open";
  selectedIncidentBadgeEl.className = `status-tag ${incident.status || "open"}`;
  const timeline = events.length
    ? events.map((event) => `<li>
        <strong>${escapeHtml(event.event_type)}</strong>
        <span>${formatTime(event.timestamp)}</span>
        <small>${escapeHtml(event.operator)}${event.notes ? ` - ${escapeHtml(event.notes)}` : ""}</small>
      </li>`).join("")
    : "<li><strong>No events</strong><span>Timeline has not started</span></li>";

  incidentDetailEl.className = "detail-body";
  incidentDetailEl.innerHTML = `
    <dl class="detail-grid">
      <dt>Device</dt><dd>${escapeHtml(incident.node_id)}</dd>
      <dt>Class</dt><dd>${escapeHtml(incident.class_label)}</dd>
      <dt>Confidence</dt><dd>${Number(incident.confidence || 0).toFixed(3)}</dd>
      <dt>Location</dt><dd>${incident.latitude}, ${incident.longitude}</dd>
      <dt>Detected</dt><dd>${formatTime(incident.timestamp)}</dd>
      <dt>Model</dt><dd>${escapeHtml(incident.model_path)}</dd>
    </dl>
    <h3>Response Timeline</h3>
    <ol class="timeline">${timeline}</ol>
  `;

  acknowledgeButton.disabled = incident.status === "acknowledged";
  resolveButton.disabled = incident.status === "resolved";
  reopenButton.disabled = incident.status === "open";
}

function clearIncidentDetail() {
  selectedIncidentId = null;
  selectedIncidentBadgeEl.textContent = "none";
  selectedIncidentBadgeEl.className = "status-tag";
  incidentDetailEl.className = "detail-empty";
  incidentDetailEl.textContent = "Select an alert to inspect response history.";
  acknowledgeButton.disabled = true;
  resolveButton.disabled = true;
  reopenButton.disabled = true;
}

async function loadIncidentDetail(incidentId) {
  selectedIncidentId = Number(incidentId);
  actionMessageEl.textContent = "";
  const response = await fetch(`/incidents/${selectedIncidentId}`);
  if (!response.ok) {
    clearIncidentDetail();
    return;
  }
  renderIncidentDetail(await response.json());
}

async function updateIncident(action) {
  if (!selectedIncidentId) return;
  const adminKey = adminKeyInputEl.value.trim();
  if (!adminKey) {
    actionMessageEl.textContent = "Enter the admin key before changing an incident.";
    actionMessageEl.className = "action-message error";
    return;
  }

  const payload = {
    operator: operatorInputEl.value.trim() || "operator",
    notes: notesInputEl.value.trim(),
  };
  const response = await fetch(`/incidents/${selectedIncidentId}/${action}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    actionMessageEl.textContent = error.detail || "Action failed";
    actionMessageEl.className = "action-message error";
    return;
  }

  actionMessageEl.textContent = `${action} saved`;
  actionMessageEl.className = "action-message success";
  notesInputEl.value = "";
  await loadIncidentDetail(selectedIncidentId);
  await refresh();
}

async function refresh() {
  try {
    const nodeId = deviceFilterEl.value;
    const query = nodeId ? `&node_id=${encodeURIComponent(nodeId)}` : "";
    const summaryQuery = nodeId ? `?node_id=${encodeURIComponent(nodeId)}` : "";
    const [health, status, devices, summary, incidents] = await Promise.all([
      fetch("/health").then((response) => response.json()),
      fetch("/status").then((response) => response.json()),
      fetch("/devices").then((response) => response.json()),
      fetch(`/incidents/summary${summaryQuery}`).then((response) => response.json()),
      fetch(`/incidents?limit=25${query}`).then((response) => response.json()),
    ]);

    healthEl.textContent = health.status === "ok" ? "Online" : "Check";
    healthEl.classList.remove("offline");
    renderDevices(devices.devices || [], devices.health || {});
    renderSummary(summary || status.incident_summary || {});
    renderIncidents(incidents.incidents || []);
    if (selectedIncidentId) {
      await loadIncidentDetail(selectedIncidentId);
    }
  } catch (error) {
    healthEl.textContent = "Offline";
    healthEl.classList.add("offline");
  }
}

refreshButton.addEventListener("click", refresh);
deviceFilterEl.addEventListener("change", refresh);
deviceCardsEl.addEventListener("click", (event) => {
  const card = event.target.closest("[data-node-id]");
  if (!card) return;
  deviceFilterEl.value = card.dataset.nodeId;
  refresh();
});
incidentRowsEl.addEventListener("click", (event) => {
  const row = event.target.closest("[data-incident-id]");
  if (!row) return;
  loadIncidentDetail(row.dataset.incidentId);
});
acknowledgeButton.addEventListener("click", () => updateIncident("acknowledge"));
resolveButton.addEventListener("click", () => updateIncident("resolve"));
reopenButton.addEventListener("click", () => updateIncident("reopen"));
operatorFormEl.addEventListener("submit", (event) => event.preventDefault());
clearIncidentDetail();
refresh();
setInterval(refresh, 10000);
