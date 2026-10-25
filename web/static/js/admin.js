/**
 * A4KU Discord 7K Badge Engine - Admin Portal Controller
 * Advanced Security & Key Tracking System
 */

(function () {
  let adminToken = sessionStorage.getItem("a4ku_admin_token") || "";
  let currentKeys = [];
  let currentSlots = [];
  let currentFilter = "all";
  let searchQuery = "";
  let pollTimer = null;

  // DOM Elements
  const viewLogin = document.getElementById("admin-view-login");
  const viewDashboard = document.getElementById("admin-view-dashboard");
  const adminLoginForm = document.getElementById("admin-login-form");
  const adminPasswordInput = document.getElementById("admin-password-input");
  const toggleAdminPassBtn = document.getElementById("toggle-admin-pass-btn");
  const adminLoginSubmitBtn = document.getElementById("admin-login-submit-btn");
  const adminLoginError = document.getElementById("admin-login-error");
  const adminLogoutBtn = document.getElementById("admin-logout-btn");
  const adminToast = document.getElementById("admin-toast");

  // Metrics
  const mKeysStat = document.getElementById("m-keys-stat");
  const mRedeemedStat = document.getElementById("m-redeemed-stat");
  const mSlotsStat = document.getElementById("m-slots-stat");
  const mQueueStat = document.getElementById("m-queue-stat");
  const mRevokedStat = document.getElementById("m-revoked-stat");

  // Key Gen
  const keyGenForm = document.getElementById("key-gen-form");
  const genCountSelect = document.getElementById("gen-count");
  const genUsesInput = document.getElementById("gen-uses");
  const genNoteInput = document.getElementById("gen-note");
  const genSubmitBtn = document.getElementById("gen-submit-btn");
  const genOutputBox = document.getElementById("gen-output-box");
  const genOutputList = document.getElementById("gen-output-list");
  const copyAllGenBtn = document.getElementById("copy-all-gen-btn");

  // Tracking Table
  const tableSearchInput = document.getElementById("table-search-input");
  const keysTableBody = document.getElementById("keys-table-body");
  const refreshOverviewBtn = document.getElementById("refresh-overview-btn");
  const filterPills = document.querySelectorAll(".filter-pill");

  const countAll = document.getElementById("count-all");
  const countActive = document.getElementById("count-active");
  const countUsed = document.getElementById("count-used");
  const countRevoked = document.getElementById("count-revoked");

  // Slots
  const adminSlotsGrid = document.getElementById("admin-slots-grid");

  // Edit Key Uses Modal
  let currentEditingKey = "";
  const editUsesModal = document.getElementById("edit-uses-modal");
  const modalEditKeyCode = document.getElementById("modal-edit-key-code");
  const modalEditUsesInput = document.getElementById("modal-edit-uses-input");
  const editUsesClose = document.getElementById("edit-uses-close");
  const modalCancelEditBtn = document.getElementById("modal-cancel-edit-btn");
  const modalSaveUsesBtn = document.getElementById("modal-save-uses-btn");

  // ── Toast Utility ──────────────────────────────────────────────────────────
  function showToast(message, isError = false) {
    if (!adminToast) return;
    adminToast.textContent = message;
    adminToast.className = `admin-toast ${isError ? 'toast-error' : 'toast-success'} visible`;
    setTimeout(() => {
      adminToast.className = "admin-toast";
    }, 2500);
  }

  // ── View Switching ──────────────────────────────────────────────────────────
  function setAuthenticatedView(isAuth) {
    if (isAuth) {
      if (viewLogin) viewLogin.style.display = "none";
      if (viewDashboard) viewDashboard.style.display = "block";
      if (adminLogoutBtn) adminLogoutBtn.style.display = "block";
      startAutoPoll();
    } else {
      if (viewLogin) viewLogin.style.display = "flex";
      if (viewDashboard) viewDashboard.style.display = "none";
      if (adminLogoutBtn) adminLogoutBtn.style.display = "none";
      stopAutoPoll();
    }
  }

  // ── Authentication Headers ──────────────────────────────────────────────────
  function getAuthHeaders() {
    return {
      "Content-Type": "application/json",
      "X-Admin-Session": adminToken
    };
  }

  // ── Login Flow ──────────────────────────────────────────────────────────────
  async function handleLogin(e) {
    if (e && e.preventDefault) e.preventDefault();
    const password = adminPasswordInput ? adminPasswordInput.value.trim() : "";
    if (adminLoginError) adminLoginError.textContent = "";

    if (!password) {
      if (adminLoginError) adminLoginError.textContent = "Please enter the Master Security Key.";
      if (adminPasswordInput) adminPasswordInput.focus();
      return;
    }

    if (adminLoginSubmitBtn) {
      adminLoginSubmitBtn.disabled = true;
      adminLoginSubmitBtn.innerHTML = `<span>VERIFYING KEY...</span>`;
    }

    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password })
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        if (adminLoginError) adminLoginError.textContent = data.error || "Authentication failed.";
        if (adminLoginSubmitBtn) {
          adminLoginSubmitBtn.disabled = false;
          adminLoginSubmitBtn.innerHTML = `<span>AUTHENTICATE GATEWAY</span><span>→</span>`;
        }
        return;
      }

      adminToken = data.token;
      sessionStorage.setItem("a4ku_admin_token", adminToken);
      if (adminPasswordInput) adminPasswordInput.value = "";
      setAuthenticatedView(true);
      showToast("✓ Authenticated as Administrator.");
      await loadOverview();
    } catch (err) {
      if (adminLoginError) adminLoginError.textContent = "Connection error. Is the server running?";
    } finally {
      if (adminLoginSubmitBtn) {
        adminLoginSubmitBtn.disabled = false;
        adminLoginSubmitBtn.innerHTML = `<span>AUTHENTICATE GATEWAY</span><span>→</span>`;
      }
    }
  }

  // ── Logout Flow ─────────────────────────────────────────────────────────────
  async function handleLogout() {
    try {
      await fetch("/api/admin/logout", {
        method: "POST",
        headers: getAuthHeaders()
      });
    } catch (e) {}
    adminToken = "";
    sessionStorage.removeItem("a4ku_admin_token");
    setAuthenticatedView(false);
    showToast("Logged out successfully.");
  }

  // ── Load Overview & Real-Time Sync ──────────────────────────────────────────
  async function loadOverview() {
    if (!adminToken) return;

    try {
      const res = await fetch("/api/admin/overview", {
        headers: getAuthHeaders()
      });

      if (res.status === 401) {
        // Session expired or invalid
        adminToken = "";
        sessionStorage.removeItem("a4ku_admin_token");
        setAuthenticatedView(false);
        return;
      }

      if (!res.ok) return;
      const data = await res.json();

      if (data.metrics) {
        if (mKeysStat) mKeysStat.textContent = `${data.metrics.active_keys} / ${data.metrics.total_keys}`;
        if (mRedeemedStat) mRedeemedStat.textContent = `${data.metrics.total_redemptions}`;
        if (mSlotsStat) mSlotsStat.textContent = `${data.metrics.active_slots} / ${data.metrics.max_slots}`;
        if (mQueueStat) mQueueStat.textContent = `Queue: ${data.metrics.queue_length} pending`;
        if (mRevokedStat) mRevokedStat.textContent = `${data.metrics.revoked_keys}`;
      }

      currentKeys = data.keys || [];
      currentSlots = data.slots || [];

      updateFilterCounts();
      renderKeysTable();
      renderSlotsGrid();
    } catch (err) {
      // ignore transient network glitch
    }
  }

  function startAutoPoll() {
    stopAutoPoll();
    pollTimer = setInterval(loadOverview, 2500);
  }

  function stopAutoPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // ── Filter Counts ───────────────────────────────────────────────────────────
  function updateFilterCounts() {
    const all = currentKeys.length;
    const active = currentKeys.filter(k => k.status === "active" && k.uses_count < k.max_uses).length;
    const used = currentKeys.filter(k => k.status === "used" || k.uses_count >= k.max_uses).length;
    const revoked = currentKeys.filter(k => k.status === "revoked").length;

    if (countAll) countAll.textContent = all;
    if (countActive) countActive.textContent = active;
    if (countUsed) countUsed.textContent = used;
    if (countRevoked) countRevoked.textContent = revoked;
  }

  // ── Render Keys Tracking Table ──────────────────────────────────────────────
  function renderKeysTable() {
    if (!keysTableBody) return;

    let filtered = currentKeys.filter(k => {
      // Status filter
      if (currentFilter === "active" && (k.status !== "active" || k.uses_count >= k.max_uses)) return false;
      if (currentFilter === "used" && k.status !== "used" && k.uses_count < k.max_uses) return false;
      if (currentFilter === "revoked" && k.status !== "revoked") return false;

      // Text search query
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const inKey = (k.key || "").toLowerCase().includes(q);
        const inNote = (k.note || "").toLowerCase().includes(q);
        const inRedemptions = (k.redemptions || []).some(r => 
          (r.username || "").toLowerCase().includes(q) || 
          (r.user_id || "").includes(q) ||
          (r.ip || "").includes(q)
        );
        return inKey || inNote || inRedemptions;
      }
      return true;
    });

    if (filtered.length === 0) {
      keysTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 36px;">
            No keys match the current filter or search criteria.
          </td>
        </tr>
      `;
      return;
    }

    keysTableBody.innerHTML = filtered.map(k => {
      const isRevoked = k.status === "revoked";
      const isUsed = k.uses_count >= k.max_uses || k.status === "used";
      let statusBadgeClass = "badge-active";
      let statusText = "ACTIVE";

      if (isRevoked) {
        statusBadgeClass = "badge-revoked";
        statusText = "REVOKED";
      } else if (isUsed) {
        statusBadgeClass = "badge-used";
        statusText = "EXHAUSTED";
      }

      // Latest redemption details
      let userDisplay = '<span style="color: var(--text-muted);">Unused</span>';
      let timeDisplay = '<span style="color: var(--text-muted);">-</span>';
      let ipDisplay = '<span style="color: var(--text-muted);">-</span>';

      if (k.redemptions && k.redemptions.length > 0) {
        const last = k.redemptions[k.redemptions.length - 1];
        userDisplay = `
          <div style="display: flex; flex-direction: column;">
            <strong style="color: #fff;">@${escapeHtml(last.username || 'User')}</strong>
            <span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">ID: ${escapeHtml(last.user_id || '')}</span>
          </div>
        `;
        const dt = new Date(last.timestamp * 1000);
        timeDisplay = `<span style="font-family: var(--font-mono); font-size: 11px;">${dt.toLocaleDateString()} ${dt.toLocaleTimeString()}</span>`;
        ipDisplay = `<span style="font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);">${escapeHtml(last.ip || '-')}</span>`;
      }

      const noteText = k.note ? escapeHtml(k.note) : '<span style="color: var(--text-muted);">—</span>';
      const isUnlimited = k.max_uses >= 999999;
      const maxUsesLabel = isUnlimited ? '∞ (Unlimited)' : k.max_uses;
      const remainingText = isUnlimited ? 'Unlimited' : Math.max(0, k.max_uses - k.uses_count) + ' left';

      return `
        <tr data-key="${k.key}">
          <td>
            <div class="key-cell-wrap">
              <span class="key-code-text">${k.key}</span>
              <button type="button" class="icon-copy-btn" onclick="window.adminCopyKey('${k.key}')" title="Copy Key">
                📋
              </button>
            </div>
          </td>
          <td><span class="status-pill-badge ${statusBadgeClass}">${statusText}</span></td>
          <td>
            <span class="usage-count-text">${k.uses_count} / ${maxUsesLabel}</span>
            <div style="font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); margin-top: 2px;">
              ${remainingText}
            </div>
          </td>
          <td>${userDisplay}</td>
          <td>${timeDisplay}</td>
          <td>${ipDisplay}</td>
          <td>${noteText}</td>
          <td style="text-align: right;">
            <div class="action-btn-row">
              <button type="button" class="btn-table-action btn-edit-uses" onclick="window.adminOpenEditUses('${k.key}', ${k.max_uses})" title="Change allowed uses">
                Edit Uses
              </button>
              ${!isRevoked ? `
                <button type="button" class="btn-table-action btn-revoke" onclick="window.adminRevokeKey('${k.key}')" title="Revoke this key">
                  Revoke
                </button>
              ` : ''}
              <button type="button" class="btn-table-action btn-delete" onclick="window.adminDeleteKey('${k.key}')" title="Delete key record">
                Delete
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  // ── Render 12 Slots Monitor Grid ───────────────────────────────────────────
  function renderSlotsGrid() {
    if (!adminSlotsGrid) return;

    adminSlotsGrid.innerHTML = currentSlots.map(s => {
      const isRunning = s.status === "running";
      const u = s.user;
      const userName = u ? `@${u.username}` : "Unoccupied";
      const userAvatar = u && u.avatar_url ? u.avatar_url : "https://cdn.discordapp.com/embed/avatars/0.png";
      const claimed = s.games_claimed || 0;
      const total = s.total_games || 7000;
      const pct = s.percent || 0;

      return `
        <div class="admin-slot-card ${isRunning ? 'slot-running' : ''}">
          <div class="slot-header-row">
            <span class="slot-id-badge">SLOT #${s.slot_id}</span>
            <span class="slot-status-indicator ${s.status}">${s.status.toUpperCase()}</span>
          </div>

          <div class="slot-user-row">
            <img src="${userAvatar}" alt="Avatar" class="slot-user-avatar" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
            <div class="slot-user-meta">
              <div class="slot-username">${escapeHtml(userName)}</div>
              <div class="slot-sub-info">${isRunning ? `Target: 7,000 Games` : 'Ready'}</div>
            </div>
          </div>

          <div class="slot-progress-wrap">
            <div class="slot-progress-bar">
              <div class="slot-progress-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="slot-progress-labels">
              <span>${claimed.toLocaleString()} / ${total.toLocaleString()}</span>
              <span>${pct}%</span>
            </div>
          </div>

          <div class="slot-log-snippet" title="${escapeHtml(s.last_log || '')}">
            ${escapeHtml(s.last_log || 'Awaiting activity...')}
          </div>

          ${isRunning ? `
            <button type="button" class="btn-stop-slot" onclick="window.adminStopSlot(${s.slot_id})">
              ⛔ EMERGENCY STOP SLOT
            </button>
          ` : `
            <div class="slot-idle-placeholder">Worker Idle</div>
          `}
        </div>
      `;
    }).join("");
  }

  // ── Key Actions ─────────────────────────────────────────────────────────────
  window.adminCopyKey = function (keyStr) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(keyStr).then(() => {
        showToast(`✓ Copied ${keyStr} to clipboard!`);
      });
    } else {
      const el = document.createElement("textarea");
      el.value = keyStr;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      showToast(`✓ Copied ${keyStr} to clipboard!`);
    }
  };

  window.adminRevokeKey = async function (keyStr) {
    if (!confirm(`Are you sure you want to REVOKE access key "${keyStr}"? Users will no longer be able to start farming with it.`)) {
      return;
    }

    try {
      const res = await fetch("/api/admin/keys/revoke", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ key: keyStr })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`✓ Key ${keyStr} revoked.`);
        await loadOverview();
      } else {
        showToast("Failed to revoke key.", true);
      }
    } catch (e) {
      showToast("Error communicating with server.", true);
    }
  };

  window.adminDeleteKey = async function (keyStr) {
    if (!confirm(`Permanently DELETE license key "${keyStr}" and its history? This action cannot be undone.`)) {
      return;
    }

    try {
      const res = await fetch("/api/admin/keys/delete", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ key: keyStr })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`✓ Key ${keyStr} deleted.`);
        await loadOverview();
      } else {
        showToast("Failed to delete key.", true);
      }
    } catch (e) {
      showToast("Error communicating with server.", true);
    }
  };

  window.adminOpenEditUses = function (keyStr, currentMaxUses) {
    currentEditingKey = keyStr;
    if (modalEditKeyCode) modalEditKeyCode.textContent = keyStr;
    if (modalEditUsesInput) modalEditUsesInput.value = currentMaxUses >= 999999 ? 999999 : currentMaxUses;
    if (editUsesModal) editUsesModal.style.display = "flex";
  };

  function closeEditUsesModal() {
    if (editUsesModal) editUsesModal.style.display = "none";
    currentEditingKey = "";
  }

  window.adminStopSlot = async function (slotId) {
    if (!confirm(`Emergency stop worker in Slot #${slotId}? Current spoofing session will be stopped immediately.`)) {
      return;
    }

    try {
      const res = await fetch("/api/admin/slot/stop", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ slot_id: slotId })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`✓ Slot #${slotId} stopped.`);
        await loadOverview();
      } else {
        showToast(data.error || "Failed to stop slot.", true);
      }
    } catch (e) {
      showToast("Error communicating with server.", true);
    }
  };

  // ── Key Generation Form ─────────────────────────────────────────────────────
  async function handleKeyGeneration(e) {
    if (e && e.preventDefault) e.preventDefault();
    const count = parseInt(genCountSelect ? genCountSelect.value : 1, 10) || 1;
    const maxUses = parseInt(genUsesInput ? genUsesInput.value : 1, 10) || 1;
    const note = genNoteInput ? genNoteInput.value.trim() : "";

    if (genSubmitBtn) {
      genSubmitBtn.disabled = true;
      genSubmitBtn.innerHTML = `<span>GENERATING...</span>`;
    }

    try {
      const res = await fetch("/api/admin/keys/create", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ count: count, max_uses: maxUses, note: note })
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        showToast(data.error || "Failed to generate keys.", true);
        return;
      }

      showToast(`✓ Successfully generated ${data.count} new access key(s)!`);

      // Show generated keys in output box
      if (genOutputBox && genOutputList) {
        genOutputBox.style.display = "block";
        genOutputList.innerHTML = data.keys.map(k => `
          <div class="gen-output-item">
            <span class="gen-key-code">${k}</span>
            <button type="button" class="icon-copy-btn" onclick="window.adminCopyKey('${k}')" title="Copy">📋</button>
          </div>
        `).join("");

        if (copyAllGenBtn) {
          copyAllGenBtn.onclick = () => {
            const allText = data.keys.join("\n");
            window.adminCopyKey(allText);
          };
        }
      }

      if (genNoteInput) genNoteInput.value = "";
      await loadOverview();
    } catch (err) {
      showToast("Network error generating keys.", true);
    } finally {
      if (genSubmitBtn) {
        genSubmitBtn.disabled = false;
        genSubmitBtn.innerHTML = `<span>+ GENERATE KEYS</span>`;
      }
    }
  }

  // ── Utility: Escape HTML ────────────────────────────────────────────────────
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ── Event Wireup ────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    // Password reveal button
    if (toggleAdminPassBtn && adminPasswordInput) {
      toggleAdminPassBtn.addEventListener("click", () => {
        const isPass = adminPasswordInput.type === "password";
        adminPasswordInput.type = isPass ? "text" : "password";
        toggleAdminPassBtn.textContent = isPass ? "🔒" : "👁️";
      });
    }

    // Login submit
    if (adminLoginForm) adminLoginForm.addEventListener("submit", handleLogin);
    if (adminLoginSubmitBtn) adminLoginSubmitBtn.addEventListener("click", handleLogin);

    // Logout
    if (adminLogoutBtn) adminLogoutBtn.addEventListener("click", handleLogout);

    // Key Gen Form
    if (keyGenForm) keyGenForm.addEventListener("submit", handleKeyGeneration);
    if (genSubmitBtn) genSubmitBtn.addEventListener("click", handleKeyGeneration);

    // Refresh button
    if (refreshOverviewBtn) refreshOverviewBtn.addEventListener("click", () => {
      loadOverview();
      showToast("Refreshed overview data.");
    });

    // Table Search
    if (tableSearchInput) {
      tableSearchInput.addEventListener("input", () => {
        searchQuery = tableSearchInput.value.trim();
        renderKeysTable();
      });
    }

    // Filter Pills
    filterPills.forEach(btn => {
      btn.addEventListener("click", () => {
        filterPills.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.getAttribute("data-filter") || "all";
        renderKeysTable();
      });
    });

    // Preset buttons in Key Generator Form & Modal
    const presetBtns = document.querySelectorAll(".uses-preset-row .preset-use-btn");
    presetBtns.forEach(btn => {
      btn.addEventListener("click", (e) => {
        if (e && e.preventDefault) e.preventDefault();
        const val = btn.getAttribute("data-val");
        const parentRow = btn.closest(".uses-preset-row");
        if (val && parentRow) {
          const input = parentRow.parentElement ? parentRow.parentElement.querySelector("input") : null;
          if (input) {
            input.value = val;
            parentRow.querySelectorAll(".preset-use-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
          }
        }
      });
    });

    if (genUsesInput) {
      genUsesInput.addEventListener("input", () => {
        const currentVal = genUsesInput.value;
        const parentRow = genUsesInput.parentElement ? genUsesInput.parentElement.querySelector(".uses-preset-row") : null;
        if (parentRow) {
          parentRow.querySelectorAll(".preset-use-btn").forEach(b => {
            if (b.getAttribute("data-val") === currentVal) {
              b.classList.add("active");
            } else {
              b.classList.remove("active");
            }
          });
        }
      });
    }

    // Modal close & save listeners
    if (editUsesClose) editUsesClose.addEventListener("click", closeEditUsesModal);
    if (modalCancelEditBtn) modalCancelEditBtn.addEventListener("click", closeEditUsesModal);
    if (editUsesModal) {
      editUsesModal.addEventListener("click", (e) => {
        if (e.target === editUsesModal) closeEditUsesModal();
      });
    }

    if (modalSaveUsesBtn) {
      modalSaveUsesBtn.addEventListener("click", async () => {
        if (!currentEditingKey) return;
        const newMax = parseInt(modalEditUsesInput ? modalEditUsesInput.value : 1, 10);
        if (isNaN(newMax) || newMax < 1) {
          showToast("Please enter a valid number of uses (minimum 1).", true);
          return;
        }
        modalSaveUsesBtn.disabled = true;
        modalSaveUsesBtn.textContent = "SAVING...";
        try {
          const res = await fetch("/api/admin/keys/update_uses", {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ key: currentEditingKey, max_uses: newMax })
          });
          const data = await res.json();
          if (data.success) {
            showToast(`✓ Limit for ${currentEditingKey} updated to ${newMax >= 999999 ? 'Unlimited' : newMax} uses!`);
            closeEditUsesModal();
            await loadOverview();
          } else {
            showToast(data.error || "Failed to update key limit.", true);
          }
        } catch (e) {
          showToast("Error communicating with server.", true);
        } finally {
          if (modalSaveUsesBtn) {
            modalSaveUsesBtn.disabled = false;
            modalSaveUsesBtn.textContent = "SAVE LIMIT";
          }
        }
      });
    }

    // Check if existing session is stored
    if (adminToken) {
      setAuthenticatedView(true);
      loadOverview();
    } else {
      setAuthenticatedView(false);
    }
  });

})();
