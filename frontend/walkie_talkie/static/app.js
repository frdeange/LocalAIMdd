/**
 * BMS COMMS — Walkie-Talkie Field Operator
 * =========================================
 * Push-to-talk voice interface. Records audio on hold,
 * sends to backend for STT → agent workflow → TTS.
 */

const API_BASE = window.location.origin;

// ── State ────────────────────────────────────────────
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let recordingStart = 0;
let timerInterval = null;

// ── DOM ──────────────────────────────────────────────
const pttBtn = document.getElementById("ptt-btn");
const pttLabel = document.getElementById("ptt-label");
const pttTimer = document.getElementById("ptt-timer");
const responseArea = document.getElementById("response-area");
const convLog = document.getElementById("conv-log");
const statusText = document.getElementById("status-text");
const connectionDot = document.getElementById("connection-dot");
const activeCaseEl = document.getElementById("active-case");

// ── Init: Request microphone ─────────────────────────

async function initMicrophone() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        setupRecorder(stream);
        setStatus("connected", "Listo");
    } catch (err) {
        setStatus("error", "Sin acceso al micrófono");
        pttBtn.disabled = true;
        console.error("Mic access denied:", err);
    }
}

function setupRecorder(stream) {
    mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm",
    });

    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
        audioChunks = [];
        handleRecordingComplete(blob);
    };
}

// ── PTT: Press and hold ──────────────────────────────

function startRecording() {
    if (!mediaRecorder || isRecording) return;

    isRecording = true;
    audioChunks = [];
    mediaRecorder.start();

    pttBtn.classList.add("recording");
    pttLabel.textContent = "TRANSMITIENDO...";

    recordingStart = Date.now();
    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - recordingStart) / 1000).toFixed(1);
        pttTimer.textContent = `${elapsed}s`;
    }, 100);
}

function stopRecording() {
    if (!mediaRecorder || !isRecording) return;

    isRecording = false;
    mediaRecorder.stop();

    clearInterval(timerInterval);
    pttTimer.textContent = "";
    pttBtn.classList.remove("recording");
    pttBtn.classList.add("processing");
    pttLabel.textContent = "PROCESANDO...";
}

// ── PTT Events (mouse + touch) ──────────────────────

pttBtn.addEventListener("mousedown", (e) => { e.preventDefault(); startRecording(); });
pttBtn.addEventListener("mouseup", stopRecording);
pttBtn.addEventListener("mouseleave", () => { if (isRecording) stopRecording(); });

pttBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
pttBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });
pttBtn.addEventListener("touchcancel", stopRecording);

// ── Handle recorded audio ────────────────────────────

async function handleRecordingComplete(audioBlob) {
    showProcessing("Enviando audio...");

    try {
        // 1. Send audio to /api/voice
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");

        const response = await fetch(`${API_BASE}/api/voice`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const err = await response.text();
            throw new Error(`Server error: ${response.status} — ${err}`);
        }

        // 2. Get response (could be JSON with audio, or WAV directly)
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("audio/")) {
            // Direct audio response
            const audioData = await response.arrayBuffer();
            const operatorText = decodeURIComponent(response.headers.get("X-Operator-Text") || "(audio sent)");
            const agentText = decodeURIComponent(response.headers.get("X-Agent-Text") || "(agent responded)");
            const caseId = response.headers.get("X-Case-Id") || "";

            addLogEntry("operator", operatorText);
            showResponse(agentText);
            addLogEntry("agent", agentText);
            if (caseId) activeCaseEl.textContent = caseId;

            // Play audio
            playAudio(audioData);
        } else {
            // JSON response (fallback for text-only mode)
            const data = await response.json();
            addLogEntry("operator", data.operator_text || "(audio sent)");
            showResponse(data.agent_text || data.response || "Sin respuesta");
            addLogEntry("agent", data.agent_text || data.response);
            if (data.case_id) activeCaseEl.textContent = data.case_id;

            // If there's audio URL, play it
            if (data.audio_url) {
                const audioResp = await fetch(data.audio_url);
                playAudio(await audioResp.arrayBuffer());
            }
        }

    } catch (err) {
        showResponse(`Error: ${err.message}`);
        console.error("Voice pipeline error:", err);
        sendMetric("error", { type: "voice_pipeline", message: err.message });
    } finally {
        pttBtn.classList.remove("processing");
        pttLabel.textContent = "PULSAR PARA HABLAR";
    }
}

// ── Audio playback ───────────────────────────────────

function playAudio(arrayBuffer) {
    const blob = new Blob([arrayBuffer], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.play().catch(err => console.warn("Audio playback failed:", err));
}

// ── UI Helpers ───────────────────────────────────────

function showProcessing(msg) {
    responseArea.innerHTML = `
        <div class="processing-indicator">
            <div class="spinner"></div>
            <span>${msg}</span>
        </div>
    `;
}

function showResponse(text) {
    responseArea.innerHTML = `<div class="response-text">${escapeHtml(text)}</div>`;
}

function addLogEntry(role, text) {
    const entry = document.createElement("div");
    entry.className = `log-entry ${role}`;
    const time = new Date().toLocaleTimeString("es-ES", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    entry.innerHTML = `
        <div class="log-role">${role === "operator" ? "OPERADOR" : "AGENTE"}</div>
        <div class="log-text">${escapeHtml(text)}</div>
        <div class="log-time">${time}</div>
    `;
    convLog.insertBefore(entry, convLog.firstChild);
    // Keep max 20 entries
    while (convLog.children.length > 20) convLog.removeChild(convLog.lastChild);
}

function setStatus(state, text) {
    statusText.textContent = text;
    connectionDot.className = `dot dot-${state}`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ── Telemetry ────────────────────────────────────────

function sendMetric(event, data = {}) {
    fetch(`${API_BASE}/api/frontend-metrics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event, ...data }),
    }).catch(() => {});
}

window.addEventListener("load", () => {
    sendMetric("page_load", { duration: Math.round(performance.now()), page: "walkie_talkie" });
});

window.addEventListener("error", (e) => {
    sendMetric("error", { type: "js_error", message: e.message, page: "walkie_talkie" });
});

// ── Init ─────────────────────────────────────────────

initMicrophone();
