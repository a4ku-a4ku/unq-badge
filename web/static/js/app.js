/**
 * A4KU Discord 7K Badge Engine - Client Controller
 * Pure monochrome minimalist UX aligned with quest 2.0 design language.
 */

// State
let currentSessionId = localStorage.getItem("a4ku_badge_sid");
if (!currentSessionId) {
  currentSessionId = "sess_" + Math.random().toString(36).substring(2, 12) + "_" + Date.now();
  localStorage.setItem("a4ku_badge_sid", currentSessionId);
}

let sessionStartTime = 0;
let sessionTimerInterval = null;
let pollInterval = null;
let statusInterval = null;
let logCount = 0;
let lastClaimedCount = -1;

// DOM Elements
const views = {
  input: document.getElementById("view-input"),
  queue: document.getElementById("view-queue"),
  dashboard: document.getElementById("view-dashboard"),
  victory: document.getElementById("view-victory"),
};

const tokenInput = document.getElementById("token-input");
const cookieInput = document.getElementById("cookie-input");
const keyInput = document.getElementById("key-input");
const toggleTokenBtn = document.getElementById("toggle-token-btn");
const tokenForm = document.getElementById("token-form");
const startBtn = document.getElementById("start-btn");
const errorBox = document.getElementById("error-box");
const slotsText = document.getElementById("slots-text");
const globalStatusPill = document.getElementById("global-status-pill");
const queuePositionText = document.getElementById("queue-position-text");
const leaveQueueBtn = document.getElementById("leave-queue-btn");
const abortSessionBtn = document.getElementById("abort-session-btn");
const restartBtn = document.getElementById("restart-btn");

const userAvatar = document.getElementById("user-avatar");
const userDisplayName = document.getElementById("user-display-name");
const userTag = document.getElementById("user-tag");
const sessionTimer = document.getElementById("session-timer");

const statTarget = document.getElementById("stat-target");
const statCompleted = document.getElementById("stat-completed");
const statStatus = document.getElementById("stat-status");
const questsContainer = document.getElementById("quests-container");
const terminalLogs = document.getElementById("terminal-logs");
const logCountEl = document.getElementById("log-count");

const slotsModal = document.getElementById("slots-modal");
const slotsModalClose = document.getElementById("slots-modal-close");
const slotsModalGrid = document.getElementById("slots-modal-grid");

// ── View Switching ──────────────────────────────────────────────────────────
function switchView(target) {
  Object.keys(views).forEach(k => {
    if (views[k]) {
      views[k].style.display = (k === target) ? "flex" : "none";
    }
  });
}

// ── Logger ──────────────────────────────────────────────────────────────────
function addLog(msg, type = "info") {
  logCount++;
  if (logCountEl) logCountEl.textContent = `${logCount} events`;

  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString();
  entry.textContent = `[${time}] ${msg}`;
  if (terminalLogs) {
    terminalLogs.appendChild(entry);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
  }
}

// ── Render Badge Pipeline Cards ─────────────────────────────────────────────
function renderBadgeCards(claimed = 0, total = 7000, isRunning = true) {
  if (!questsContainer) return;
  const pct = Math.min(100, Math.floor((claimed / (total || 7000)) * 100));

  questsContainer.innerHTML = `
    <!-- Card 1: 7,000 Games Played Badge -->
    <div class="quest-card ${claimed >= total ? 'status-done' : ''}">
      <div class="quest-top-row">
        <div class="quest-name-box">
          <span style="font-size: 20px;">🎮</span>
          <div>
            <div class="quest-title-text">7,000 Games Played Badge</div>
            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">
              DISCORD PROFILE HIGHLIGHT • VERIFIED CLIENT SCIENCE
            </div>
          </div>
        </div>
        <div class="task-type-badge">${claimed >= total ? 'UNLOCKED' : (isRunning ? 'FARMING' : 'READY')}</div>
        <div class="quest-status-badge ${claimed >= total ? 'badge-done' : 'badge-running'}">
          ${claimed >= total ? 'COMPLETED' : `${claimed} / ${total}`}
        </div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: ${pct}%;"></div>
      </div>
      <div class="quest-bottom-row">
        <span>Progress: ${pct}%</span>
        <span>${total - claimed} games remaining</span>
      </div>
    </div>

    <!-- Card 2: 7,000 Playtime Hours Badge -->
    <div class="quest-card ${claimed >= total ? 'status-done' : ''}">
      <div class="quest-top-row">
        <div class="quest-name-box">
          <span style="font-size: 20px;">⏳</span>
          <div>
            <div class="quest-title-text">7,000 Playtime Hours Badge</div>
            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">
              1 HOUR (3,600,000 MS) AUTOMATIC PAYLOAD PER GAME
            </div>
          </div>
        </div>
        <div class="task-type-badge">${claimed >= total ? 'UNLOCKED' : (isRunning ? 'FARMING' : 'READY')}</div>
        <div class="quest-status-badge ${claimed >= total ? 'badge-done' : 'badge-running'}">
          ${claimed >= total ? 'COMPLETED' : `${claimed} / ${total} HRS`}
        </div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: ${pct}%;"></div>
      </div>
      <div class="quest-bottom-row">
        <span>Playtime Accumulated: ${claimed} hrs</span>
        <span>Anti-Detection: Validated</span>
      </div>
    </div>

    <!-- Card 3: Desktop Science Telemetry -->
    <div class="quest-card status-done">
      <div class="quest-top-row">
        <div class="quest-name-box">
          <span style="font-size: 20px;">🛡️</span>
          <div>
            <div class="quest-title-text">Discord Anti-Detection Safeguard</div>
            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">
              CLIENT BUILD 594031 • FINGERPRINT AUTHENTICODE VALIDATED
            </div>
          </div>
        </div>
        <div class="task-type-badge">PROTECTION</div>
        <div class="quest-status-badge badge-done">ACTIVE</div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: 100%;"></div>
      </div>
      <div class="quest-bottom-row">
        <span>Randomized Jitter & Super-Properties Emulation</span>
        <span>Memory-Only Isolation</span>
      </div>
    </div>
  `;
}

// ── Timer Helpers ───────────────────────────────────────────────────────────
function startTimer() {
  stopTimer();
  sessionStartTime = Date.now();
  if (sessionTimer) sessionTimer.textContent = "00:00";
  sessionTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const s = String(elapsed % 60).padStart(2, "0");
    if (sessionTimer) sessionTimer.textContent = `${m}:${s}`;
  }, 1000);
}

function stopTimer() {
  if (sessionTimerInterval) {
    clearInterval(sessionTimerInterval);
    sessionTimerInterval = null;
  }
}

// ── Error Banner ────────────────────────────────────────────────────────────
function showError(msg) {
  if (!errorBox) return;
  if (!msg) {
    errorBox.style.display = "none";
    errorBox.textContent = "";
  } else {
    errorBox.style.display = "block";
    errorBox.textContent = msg;
  }
}

// ── Global Status Polling ───────────────────────────────────────────────────
async function fetchGlobalStatus() {
  try {
    const res = await fetch("/api/queue?action=status");
    if (!res.ok) return;
    const data = await res.json();
    if (slotsText) {
      slotsText.textContent = `SLOTS: ${data.activeCount || 0}/${data.maxSlots || 12} ACTIVE`;
    }
  } catch (e) {
    // silently ignore network jitter
  }
}

// ── Form Submission ─────────────────────────────────────────────────────────
async function handleInitialize(e) {
  if (e && e.preventDefault) e.preventDefault();
  if (startBtn && startBtn.disabled) return;
  const token = tokenInput ? tokenInput.value.trim() : "";
  const cookie = cookieInput.value.trim();
  const key = keyInput ? keyInput.value.trim().toUpperCase() : "";

  showError("");

  if (!token) {
    showError("Please enter your Discord user token.");
    tokenInput.focus();
    return;
  }

  if (!cookie) {
    showError("Please enter your Cloudflare cf_clearance cookie.");
    cookieInput.focus();
    return;
  }

  if (!key) {
    showError("Please enter your Access Key (format: XXXX-XXXX-XXXX). Obtain a key from the Admin Portal.");
    if (keyInput) keyInput.focus();
    return;
  }

  startBtn.disabled = true;
  startBtn.innerHTML = `<span>VERIFYING & INITIALIZING...</span>`;

  try {
    const res = await fetch("/api/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "join",
        sessionId: currentSessionId,
        token: token,
        cookie: cookie,
        key: key,
      })
    });

    const data = await res.json();

    if (data.status === "error" || data.error) {
      showError(data.error || "Failed to initialize badge spoofing session.");
      startBtn.disabled = false;
      startBtn.innerHTML = `<span>INITIALIZE 7K BADGES</span><span>→</span>`;
      return;
    }

    if (data.status === "waiting") {
      switchView("queue");
      if (queuePositionText) queuePositionText.textContent = `#${data.position || 1}`;
      startPolling();
      return;
    }

    if (data.status === "active") {
      enterDashboard(data.slot);
    }
  } catch (err) {
    showError("Network connection error. Is the server running?");
    startBtn.disabled = false;
    startBtn.innerHTML = `<span>INITIALIZE 7K BADGES</span><span>→</span>`;
  }
}

// ── Enter Dashboard ─────────────────────────────────────────────────────────
function enterDashboard(slot) {
  switchView("dashboard");
  startTimer();

  // Populate User Info
  if (slot && slot.user) {
    if (userAvatar) userAvatar.src = slot.user.avatar_url || "https://cdn.discordapp.com/embed/avatars/0.png";
    if (userDisplayName) userDisplayName.textContent = slot.user.global_name || slot.user.username || "Discord User";
    if (userTag) userTag.textContent = `@${slot.user.username || "user"}`;
  }

  if (terminalLogs) terminalLogs.innerHTML = "";
  logCount = 0;
  lastClaimedCount = -1;

  addLog("Session initialized with Discord science telemetry engine.", "ok");
  addLog("Targeting 7,000 games and 7,000 playtime hours automatically.", "info");

  renderBadgeCards(slot.games_claimed || 0, slot.total_games || 7000, true);
  startPolling();
}

// ── Polling Loop ────────────────────────────────────────────────────────────
function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(pollSession, 1200);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function pollSession() {
  try {
    const res = await fetch("/api/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "poll",
        sessionId: currentSessionId,
      })
    });

    if (!res.ok) return;
    const data = await res.json();

    if (slotsText && data.activeCount !== undefined) {
      slotsText.textContent = `SLOTS: ${data.activeCount}/${data.maxSlots || 12} ACTIVE`;
    }

    // Still in queue
    if (data.status === "waiting") {
      if (views.queue.style.display !== "flex") switchView("queue");
      if (queuePositionText) queuePositionText.textContent = `#${data.position || 1}`;
      return;
    }

    // Session completed in background while browser was closed
    if (data.status === "completed" && data.slot) {
      stopPolling();
      stopTimer();
      switchView("victory");
      return;
    }

    // Active in slot
    if (data.status === "active" && data.slot) {
      const slot = data.slot;

      if (views.dashboard.style.display !== "flex" && views.victory.style.display !== "flex") {
        enterDashboard(slot);
      }

      const claimed = slot.games_claimed || 0;
      const total = slot.total_games || 7000;

      if (statCompleted) statCompleted.textContent = `${claimed.toLocaleString()} / ${total.toLocaleString()}`;
      if (statStatus) {
        if (slot.status === "running") statStatus.textContent = "Farming...";
        else if (slot.status === "finished") statStatus.textContent = "Completed";
        else if (slot.status === "error") statStatus.textContent = "Error";
      }

      if (claimed !== lastClaimedCount) {
        renderBadgeCards(claimed, total, slot.status === "running");
        if (slot.last_log && slot.last_log !== "Slot cleared") {
          addLog(slot.last_log, claimed >= total ? "ok" : "progress");
        }
        lastClaimedCount = claimed;
      }

      if (slot.status === "finished" || claimed >= total) {
        stopPolling();
        stopTimer();
        setTimeout(() => {
          switchView("victory");
        }, 1000);
      } else if (slot.status === "error") {
        addLog(slot.last_log || "An error occurred during farming.", "warn");
        stopPolling();
      }
    }
  } catch (err) {
    // ignore temporary network dropouts
  }
}

// ── Abort / Cancel ──────────────────────────────────────────────────────────
async function handleAbort(e) {
  if (e && e.preventDefault) e.preventDefault();
  stopPolling();
  stopTimer();

  try {
    await fetch("/api/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "abort",
        sessionId: currentSessionId,
      })
    });
  } catch (e) {}

  switchView("input");
  startBtn.disabled = false;
  startBtn.innerHTML = `<span>INITIALIZE 7K BADGES</span><span>→</span>`;
  fetchGlobalStatus();
}

// ── Slots Modal (Pool Inspector) ────────────────────────────────────────────
async function openSlotsModal() {
  if (!slotsModal) return;
  slotsModal.style.display = "flex";
  try {
    const res = await fetch("/api/slots");
    if (!res.ok) return;
    const data = await res.json();
    if (!slotsModalGrid) return;
    slotsModalGrid.innerHTML = (data.slots || []).map(s => {
      const active = s.status === "running";
      const uName = s.user ? `@${s.user.username}` : "Unoccupied";
      const progress = active ? `${s.games_claimed || 0}/7000 games` : (s.status === "finished" ? "7000/7000 (Done)" : "Idle");
      return `
        <div class="slot-item-mini ${active ? 'active' : ''}">
          <div class="slot-item-top">
            <span style="font-weight: 700;">SLOT #${s.slot_id}</span>
            <span style="color: ${active ? '#fff' : 'var(--text-muted)'}; text-transform: uppercase;">${s.status}</span>
          </div>
          <div class="slot-item-user">${uName}</div>
          <div class="slot-item-progress">${progress}</div>
        </div>
      `;
    }).join("");
  } catch (e) {}
}

function closeSlotsModal() {
  if (slotsModal) slotsModal.style.display = "none";
}

// ── Smooth Cursor Follower & Lighting Effect ────────────────────────────────
(function initCursorGlow() {
  const glow = document.getElementById("cursor-glow");
  if (!glow) return;

  let mouseX = window.innerWidth / 2;
  let mouseY = window.innerHeight / 2;
  let currentX = mouseX;
  let currentY = mouseY;
  let hasMoved = false;

  window.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    if (!hasMoved) {
      glow.style.opacity = "1";
      hasMoved = true;
    }
  }, { passive: true });

  window.addEventListener("mouseleave", () => {
    glow.style.opacity = "0";
    hasMoved = false;
  });

  function animate() {
    currentX += (mouseX - currentX) * 0.12;
    currentY += (mouseY - currentY) * 0.12;
    glow.style.transform = `translate3d(${currentX - 300}px, ${currentY - 300}px, 0)`;
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();

// ── Event Listeners ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Toggle Token Password Visibility
  if (toggleTokenBtn && tokenInput) {
    toggleTokenBtn.addEventListener("click", () => {
      const isPass = tokenInput.type === "password";
      tokenInput.type = isPass ? "text" : "password";
      toggleTokenBtn.textContent = isPass ? "🔒" : "👁️";
    });
  }

  // Auto uppercase Key Input
  if (keyInput) {
    keyInput.addEventListener("input", () => {
      keyInput.value = keyInput.value.toUpperCase();
    });
  }

  // Start Farm
  if (startBtn) startBtn.addEventListener("click", handleInitialize);
  if (tokenForm) tokenForm.addEventListener("submit", handleInitialize);

  // Leave Queue
  if (leaveQueueBtn) leaveQueueBtn.addEventListener("click", handleAbort);

  // Abort Dashboard
  if (abortSessionBtn) abortSessionBtn.addEventListener("click", handleAbort);

  // Restart from Victory
  if (restartBtn) restartBtn.addEventListener("click", () => {
    currentSessionId = "sess_" + Math.random().toString(36).substring(2, 12) + "_" + Date.now();
    localStorage.setItem("a4ku_badge_sid", currentSessionId);
    switchView("input");
    tokenInput.value = "";
    cookieInput.value = "";
    startBtn.disabled = false;
    startBtn.innerHTML = `<span>INITIALIZE 7K BADGES</span><span>→</span>`;
    fetchGlobalStatus();
  });

  // Slots Modal
  if (globalStatusPill) globalStatusPill.addEventListener("click", openSlotsModal);
  if (slotsModalClose) slotsModalClose.addEventListener("click", closeSlotsModal);
  if (slotsModal) {
    slotsModal.addEventListener("click", (e) => {
      if (e.target === slotsModal) closeSlotsModal();
    });
  }

  // Initial Status Check
  fetchGlobalStatus();
  statusInterval = setInterval(fetchGlobalStatus, 5000);

  // Poll existing session if any
  pollSession();
});
