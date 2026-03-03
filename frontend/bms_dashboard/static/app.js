/**
 * BMS Operations — Command Post Dashboard
 * ========================================
 * Vanilla JS — SSE for live updates, no build step.
 */

const API_BASE = window.location.origin;

// ── State ────────────────────────────────────────────
let cases = [];
let selectedCaseId = null;
let activeFilter = "";

// ── DOM refs ─────────────────────────────────────────
const caseListEl = document.getElementById("case-list");
const caseDetailEl = document.getElementById("case-detail");
const activityFeedEl = document.getElementById("activity-feed");
const connectionStatusEl = document.getElementById("connection-status");
const caseCountEl = document.getElementById("case-count");
const filterBtns = document.querySelectorAll(".filter-btn");

// ── API ──────────────────────────────────────────────

async function fetchCases(statusFilter = "") {
    const url = statusFilter
        ? `${API_BASE}/api/cases?status=${statusFilter}`
        : `${API_BASE}/api/cases`;
    const res = await fetch(url);
    const data = await res.json();
    cases = data.cases;
    caseCountEl.textContent = `${data.count} cases`;
    renderCaseList();
}

async function fetchCaseDetail(caseId) {
    const res = await fetch(`${API_BASE}/api/cases/${caseId}`);
    const data = await res.json();
    renderCaseDetail(data);
}

// ── Render: Case List ────────────────────────────────

function renderCaseList() {
    if (cases.length === 0) {
        caseListEl.innerHTML = '<div class="empty-state">No cases found</div>';
        return;
    }

    caseListEl.innerHTML = cases.map(c => `
        <div class="case-card ${c.case_id === selectedCaseId ? 'selected' : ''}"
             onclick="selectCase('${c.case_id}')">
            <div class="case-card-header">
                <span class="case-id">${c.case_id}</span>
                <span class="priority-badge priority-${c.priority}">${c.priority}</span>
            </div>
            <div class="case-summary">${c.summary}</div>
            <div class="case-meta">
                <span class="status-tag status-${c.status}">${c.status}</span>
                <span>${formatTime(c.created_at)}</span>
            </div>
        </div>
    `).join("");
}

// ── Render: Case Detail ──────────────────────────────

function renderCaseDetail(c) {
    const coordsHtml = c.coordinates
        ? `<div class="detail-coords">📍 ${c.coordinates.latitude}, ${c.coordinates.longitude}</div>`
        : "";

    const interactionsHtml = c.interactions.length > 0
        ? c.interactions.map(i => `
            <div class="interaction-item">
                <div class="interaction-agent">${i.agent_name}</div>
                <div class="interaction-time">${formatTime(i.timestamp)}</div>
                <div class="interaction-message">${escapeHtml(i.message)}</div>
            </div>
        `).join("")
        : '<div class="empty-state">No interactions yet</div>';

    caseDetailEl.innerHTML = `
        <div class="detail-header">
            <h3>${c.case_id}</h3>
            <div class="detail-meta">
                <span class="status-tag status-${c.status}">${c.status}</span>
                <span class="priority-badge priority-${c.priority}">${c.priority}</span>
                <span>Created: ${formatTime(c.created_at)}</span>
            </div>
        </div>
        <div class="detail-summary">
            ${escapeHtml(c.summary)}
            ${coordsHtml}
        </div>
        <h2>Interaction Timeline</h2>
        <div class="interaction-timeline">
            ${interactionsHtml}
        </div>
    `;
}

// ── Select Case ──────────────────────────────────────

function selectCase(caseId) {
    selectedCaseId = caseId;
    renderCaseList();
    fetchCaseDetail(caseId);
}

// ── Filter ───────────────────────────────────────────

filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        filterBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activeFilter = btn.dataset.filter;
        fetchCases(activeFilter);
    });
});

// ── SSE: Live Updates ────────────────────────────────

function connectSSE() {
    const source = new EventSource(`${API_BASE}/api/stream`);

    source.addEventListener("connected", () => {
        connectionStatusEl.textContent = "CONNECTED";
        connectionStatusEl.className = "status-badge status-connected";
    });

    source.addEventListener("new_case", (e) => {
        const data = JSON.parse(e.data);
        addActivityItem("📋 New case", data.case_id, data.summary, data.created_at);
        fetchCases(activeFilter);
    });

    source.addEventListener("new_interaction", (e) => {
        const data = JSON.parse(e.data);
        addActivityItem(
            data.agent_name,
            data.case_id,
            data.message.substring(0, 120),
            data.timestamp
        );
        // Refresh detail if viewing this case
        if (data.case_id === selectedCaseId) {
            fetchCaseDetail(selectedCaseId);
        }
        fetchCases(activeFilter);
    });

    source.addEventListener("case_update", (e) => {
        const data = JSON.parse(e.data);
        addActivityItem("🔄 Case updated", data.case_id, `Status: ${data.status}`, new Date().toISOString());
        fetchCases(activeFilter);
    });

    source.onerror = () => {
        connectionStatusEl.textContent = "DISCONNECTED";
        connectionStatusEl.className = "status-badge status-disconnected";
        source.close();
        sendMetric("sse_reconnect");
        // Reconnect after 3 seconds
        setTimeout(connectSSE, 3000);
    };
}

// ── Activity Feed ────────────────────────────────────

function addActivityItem(agent, caseId, message, timestamp) {
    const emptyState = activityFeedEl.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    const item = document.createElement("div");
    item.className = "activity-item";
    item.innerHTML = `
        <div class="activity-time">${formatTime(timestamp)}</div>
        <div class="activity-agent">${escapeHtml(agent)}</div>
        <div class="activity-case">${caseId}</div>
        <div class="activity-msg">${escapeHtml(message)}</div>
    `;

    activityFeedEl.insertBefore(item, activityFeedEl.firstChild);

    // Keep max 50 items
    while (activityFeedEl.children.length > 50) {
        activityFeedEl.removeChild(activityFeedEl.lastChild);
    }
}

// ── Utils ────────────────────────────────────────────

function formatTime(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ── Init ─────────────────────────────────────────────

fetchCases();
connectSSE();
initTelemetry();


// ── Frontend Telemetry ───────────────────────────────

function sendMetric(event, data = {}) {
    fetch(`${API_BASE}/api/frontend-metrics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event, ...data }),
    }).catch(() => {}); // fire-and-forget
}

function initTelemetry() {
    // Page load timing
    window.addEventListener("load", () => {
        const duration = performance.now();
        sendMetric("page_load", { duration: Math.round(duration) });
    });

    // Global JS error tracking
    window.addEventListener("error", (e) => {
        sendMetric("error", {
            type: "js_error",
            message: e.message,
            source: e.filename,
            line: e.lineno,
        });
    });

    // Unhandled promise rejection tracking
    window.addEventListener("unhandledrejection", (e) => {
        sendMetric("error", {
            type: "promise_rejection",
            message: String(e.reason),
        });
    });
}
