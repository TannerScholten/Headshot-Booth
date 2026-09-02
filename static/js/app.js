// --- Global State & Elements ---
let activeAttendeeId = null;
let searchDebounceTimer = null;
let highlightedIndex = 0;
let chimeEnabled = localStorage.getItem("chimeEnabled") !== "false";
let currentFilter = "unshot";

const searchInput = document.getElementById("search-input");
const attendeeList = document.getElementById("attendee-list");
const activeCard = document.getElementById("active-card");
const walkinModal = document.getElementById("walkin-modal");
const queueList = document.getElementById("queue-list");
const btnSync = document.getElementById("btn-sync-google");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    updateChimeButtonUI();
    setupKeyboardShortcuts();
    setupSearchInput();
    refreshOutbox();

    if (btnSync) {
        btnSync.addEventListener("click", syncGoogle);
    }

    // Initial poll and live update loop every 4 seconds
    pollStatus();
    setInterval(pollStatus, 4000);
});

// --- Fullscreen Toggle ---
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            console.log("Fullscreen error:", err);
        });
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
}

// --- Roster Filtering ---
function setFilter(filterType) {
    currentFilter = filterType;
    document.querySelectorAll(".filter-pill").forEach(pill => pill.classList.remove("active"));
    const activePill = document.getElementById(`pill-${filterType}`);
    if (activePill) activePill.classList.add("active");
    fetchSearch(searchInput.value);
}

// --- Audio Cue (Web Audio API Synthesizer) ---
function toggleChime() {
    chimeEnabled = !chimeEnabled;
    localStorage.setItem("chimeEnabled", chimeEnabled);
    updateChimeButtonUI();
    showToast(`Audio Chime ${chimeEnabled ? "Enabled" : "Muted"}`, "info");
    if (chimeEnabled) playChime();
}

function updateChimeButtonUI() {
    const icon = document.getElementById("chime-icon");
    const label = document.getElementById("chime-label");
    if (icon && label) {
        icon.textContent = chimeEnabled ? "🔔" : "🔕";
        label.textContent = chimeEnabled ? "Chime: ON" : "Chime: OFF";
    }
}

function playChime() {
    if (!chimeEnabled) return;
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const now = audioCtx.currentTime;
        
        // High tone
        const osc1 = audioCtx.createOscillator();
        const gain1 = audioCtx.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(587.33, now); // D5
        gain1.gain.setValueAtTime(0.15, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc1.connect(gain1);
        gain1.connect(audioCtx.destination);
        osc1.start(now);
        osc1.stop(now + 0.35);

        // Harmonizing higher tone
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(880.00, now + 0.08); // A5
        gain2.gain.setValueAtTime(0.15, now + 0.08);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
        osc2.connect(gain2);
        gain2.connect(audioCtx.destination);
        osc2.start(now + 0.08);
        osc2.stop(now + 0.45);
    } catch (e) {
        // AudioContext may require initial user gesture
    }
}

// --- Keyboard Shortcuts & Arrow Navigation ---
function setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        // Alt+N -> Open Walk-In Modal
        if (e.altKey && (e.key === "n" || e.key === "N")) {
            e.preventDefault();
            openWalkInModal();
            return;
        }

        // "/" -> Focus search input
        if (e.key === "/" && document.activeElement !== searchInput && !walkinModal.classList.contains("active")) {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
            return;
        }

        // Escape -> Close modal or clear search
        if (e.key === "Escape") {
            const qrModal = document.getElementById("qr-modal");
            if (qrModal && qrModal.classList.contains("active")) {
                closeQrModal();
            } else if (walkinModal.classList.contains("active")) {
                closeWalkInModal();
            } else if (searchInput.value) {
                clearSearch();
            }
            return;
        }

        const items = attendeeList.querySelectorAll(".attendee-item");
        if (items.length === 0) return;

        // ArrowDown -> Move down in search results
        if (e.key === "ArrowDown") {
            e.preventDefault();
            highlightedIndex = Math.min(highlightedIndex + 1, items.length - 1);
            updateHighlightedItem(items);
            return;
        }

        // ArrowUp -> Move up in search results
        if (e.key === "ArrowUp") {
            e.preventDefault();
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            updateHighlightedItem(items);
            return;
        }

        // Enter in search -> Select highlighted result
        if (e.key === "Enter" && document.activeElement === searchInput) {
            e.preventDefault();
            if (highlightedIndex >= 0 && highlightedIndex < items.length) {
                items[highlightedIndex].click();
            }
        }
    });
}

function updateHighlightedItem(items) {
    items.forEach((item, idx) => {
        if (idx === highlightedIndex) {
            item.classList.add("highlighted");
            item.scrollIntoView({ block: "nearest" });
        } else {
            item.classList.remove("highlighted");
        }
    });
}

// --- Live Search & Barcode Parsing ---
function setupSearchInput() {
    searchInput.addEventListener("input", () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            let val = searchInput.value.trim();
            // Clean common QR/badge scanner prefixes (e.g. ID:1001 or URL?id=1001)
            const idMatch = val.match(/(?:id[=:]\s*|\bid\s*)(\d{4})/i);
            if (idMatch) {
                val = idMatch[1];
                searchInput.value = val;
            }
            fetchSearch(val);
        }, 150);
    });
}

async function fetchSearch(query) {
    try {
        const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}&filter_type=${encodeURIComponent(currentFilter)}`);
        const data = await resp.json();
        renderAttendeeList(data.results);
    } catch (e) {
        console.error("Search error:", e);
    }
}

function clearSearch() {
    searchInput.value = "";
    fetchSearch("");
    searchInput.focus();
}

function renderAttendeeList(attendees) {
    if (!attendees || attendees.length === 0) {
        attendeeList.innerHTML = `
            <div style="padding: 24px; text-align: center; color: #64748b;">
                <p style="margin: 0 0 12px 0;">No matching attendees found.</p>
                <div style="display: flex; gap: 8px; justify-content: center;">
                    <button class="btn btn-secondary btn-sm" onclick="syncGoogle()">🔄 Sync Form Now</button>
                    <button class="btn btn-primary btn-sm" onclick="openWalkInModal()">⚡ Quick Walk-In (Alt+N)</button>
                </div>
            </div>`;
        highlightedIndex = -1;
        return;
    }

    // Auto-highlight first item only when user has typed an active search query
    const hasQuery = searchInput.value.trim().length > 0;
    highlightedIndex = hasQuery ? 0 : -1;

    attendeeList.innerHTML = attendees.map((a, idx) => `
        <div class="attendee-item ${idx === highlightedIndex ? 'highlighted' : ''} ${activeAttendeeId === a.id ? 'selected' : ''}" onclick="selectAttendee(${a.id})">
            <div class="item-left">
                <span class="item-id">#${a.id}</span>
                <div class="item-info">
                    <span class="item-name">${escapeHtml(a.first_name)} ${escapeHtml(a.last_name)}</span>
                    <span class="item-sub">
                        ${a.title ? escapeHtml(a.title) : ''}
                        ${a.organization ? ` &bull; ${escapeHtml(a.organization)}` : ''}
                    </span>
                </div>
            </div>
            <div class="item-right">
                <span class="item-email">${escapeHtml(a.email)}</span>
                ${a.photo_count > 0 ? `<span class="badge badge-success">${a.photo_count} photos</span>` : ''}
            </div>
        </div>
    `).join("");
}

// --- Active Subject Selection ---
async function selectAttendee(id) {
    try {
        const resp = await fetch(`/api/active/${id}`, { method: "POST" });
        const data = await resp.json();
        if (data.status === "success") {
            activeAttendeeId = id;
            renderActiveCard(data.active);
            fetchSearch(searchInput.value);
            playChime();
            showToast(`Active: ${data.active.first_name} ${data.active.last_name}`, "info");
        }
    } catch (e) {
        showToast("Error setting active attendee", "error");
    }
}

async function clearActive() {
    try {
        const resp = await fetch("/api/active/clear", { method: "POST" });
        const data = await resp.json();
        activeAttendeeId = null;
        renderActiveCard(null);
        fetchSearch(searchInput.value);
        showToast("Active subject cleared", "info");
    } catch (e) {
        showToast("Error clearing active subject", "error");
    }
}

async function newSession(id) {
    try {
        const resp = await fetch(`/api/session/new/${id}`, { method: "POST" });
        const data = await resp.json();
        showToast(`Created Outfit Session #${data.session_number}!`, "success");
        renderActiveCard(data.active);
    } catch (e) {
        showToast("Error creating new session", "error");
    }
}

async function resendEmail(id) {
    try {
        showToast("Sending gallery email...", "info");
        const resp = await fetch(`/api/attendee/${id}/resend-email`, { method: "POST" });
        const data = await resp.json();
        if (resp.ok) {
            showToast(data.message, "success");
        } else {
            showToast(data.detail || "Failed to send email", "error");
        }
    } catch (e) {
        showToast("Network error resending email", "error");
    }
}

function copyGalleryUrl(url) {
    if (!url) return;
    navigator.clipboard.writeText(url).then(() => {
        showToast("Gallery link copied to clipboard! 📋", "success");
    }).catch(() => {
        prompt("Copy gallery URL:", url);
    });
}

async function retryFailedDeliveries() {
    try {
        showToast("Retrying failed deliveries...", "info");
        const resp = await fetch("/api/outbox/retry-failed", { method: "POST" });
        const data = await resp.json();
        showToast(data.message, data.status === "success" ? "success" : "info");
        refreshOutbox();
        pollStatus();
    } catch (e) {
        showToast("Failed to retry outbox", "error");
    }
}

function renderActiveCard(attendee) {
    if (!attendee) {
        activeCard.classList.remove("active-selected");
        activeCard.style.display = "flex";
        activeCard.style.justifyContent = "space-between";
        activeCard.style.alignItems = "center";
        activeCard.style.padding = "10px 18px";
        activeCard.style.minHeight = "80px";
        activeCard.style.gap = "16px";
        activeCard.innerHTML = `
            <div class="active-left-col empty-state-compact" style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 4px;">
                <div class="active-header-row">
                    <span class="active-tag" style="font-size: 10px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;">CURRENT ACTIVE SUBJECT</span>
                </div>
                <div class="active-name-row" style="display: flex; align-items: baseline; gap: 12px;">
                    <h2 class="active-name text-muted" style="font-size: 26px; font-weight: 800; line-height: 1.1; margin: 0;">No Subject Selected</h2>
                    <span class="empty-hint" style="font-size: 13px; color: #94a3b8;">Type a name below or press <strong>Alt+N</strong> for walk-in registration</span>
                </div>
            </div>
            <div class="active-qr-box" onclick="openQrModal()" title="Click to enlarge Walk-Up Registration QR Code" style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 8px; padding: 6px 8px; cursor: pointer; flex-shrink: 0; width: 124px;">
                <img src="/static/img/registration_qr.png" alt="Register QR" class="active-qr-img" style="width: 110px; height: 110px; max-width: 110px; max-height: 110px; background: #ffffff; border-radius: 6px; padding: 3px; display: block;">
                <span class="active-qr-label" style="font-size: 10px; font-weight: 700; color: #38bdf8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;">📱 Scan to Register</span>
            </div>
        `;
        return;
    }

    activeCard.classList.add("active-selected");
    activeCard.style.display = "flex";
    activeCard.style.justifyContent = "space-between";
    activeCard.style.alignItems = "center";
    activeCard.style.padding = "10px 18px";
    activeCard.style.minHeight = "80px";
    activeCard.style.gap = "16px";
    activeCard.innerHTML = `
        <div class="active-left-col" style="flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0;">
            <div class="active-header-row" style="display: flex; align-items: center; gap: 10px;">
                <span class="active-tag" style="font-size: 10px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;">CURRENT ACTIVE SUBJECT</span>
                <span class="active-id-badge" style="padding: 1px 7px; font-size: 11px;">ID: ${attendee.id}</span>
            </div>
            <div class="active-name-row" style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">
                <h2 class="active-name" style="font-size: 26px; font-weight: 800; color: #ffffff; line-height: 1.1; margin: 0;">${escapeHtml(attendee.first_name)} ${escapeHtml(attendee.last_name)}</h2>
                <div class="active-details" style="font-size: 14px; color: #cbd5e1; margin: 0;">
                    ${attendee.title ? `<span class="active-title">${escapeHtml(attendee.title)}</span>` : ''}
                    ${attendee.organization ? `<span class="active-org">&bull; ${escapeHtml(attendee.organization)}</span>` : ''}
                </div>
            </div>
            <div class="active-meta-row" style="display: flex; align-items: center; gap: 14px; font-size: 12px; color: #94a3b8; flex-wrap: wrap;">
                <span class="active-email">✉️ ${escapeHtml(attendee.email)}</span>
                ${attendee.phone ? `<span class="active-phone">📞 ${escapeHtml(attendee.phone)}</span>` : ''}
                ${attendee.zenfolio_gallery_url ? `
                <span class="gallery-link-group" style="display: inline-flex; align-items: center; gap: 4px;">
                    <a href="${attendee.zenfolio_gallery_url}" target="_blank" class="active-gallery-link">🔗 Gallery</a>
                    <button class="btn-copy-url" onclick="copyGalleryUrl('${attendee.zenfolio_gallery_url}')" title="Copy gallery link">📋 Copy</button>
                </span>` : ''}
                <div class="active-actions-inline" style="display: inline-flex; align-items: center; gap: 6px; margin-left: auto;">
                    ${attendee.zenfolio_gallery_url ? `
                    <button class="btn btn-xs btn-secondary" onclick="resendEmail(${attendee.id})" title="Manually re-send gallery notice email">
                        ✉️ Resend
                    </button>` : ''}
                    <button class="btn btn-xs btn-warning" onclick="newSession(${attendee.id})" title="Outfit change / session 2">
                        👔 Outfit #2
                    </button>
                    <button class="btn btn-xs btn-outline" onclick="clearActive()" title="Clear active subject">
                        ✕ Clear
                    </button>
                </div>
            </div>
        </div>
        <div class="active-qr-box" onclick="openQrModal()" title="Click to enlarge Walk-Up Registration QR Code" style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 8px; padding: 6px 8px; cursor: pointer; flex-shrink: 0; width: 124px;">
            <img src="/static/img/registration_qr.png" alt="Register QR" class="active-qr-img" style="width: 110px; height: 110px; max-width: 110px; max-height: 110px; background: #ffffff; border-radius: 6px; padding: 3px; display: block;">
            <span class="active-qr-label" style="font-size: 10px; font-weight: 700; color: #38bdf8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;">📱 Scan to Register</span>
        </div>
    `;
}

// --- Walk-In Modal ---
function openWalkInModal() {
    walkinModal.classList.add("active");
    document.getElementById("w-first").value = "";
    document.getElementById("w-last").value = "";
    document.getElementById("w-email").value = "";
    document.getElementById("w-org").value = "";
    document.getElementById("w-title").value = "";
    document.getElementById("w-phone").value = "";
    setTimeout(() => document.getElementById("w-first").focus(), 100);
}

function closeWalkInModal() {
    walkinModal.classList.remove("active");
    searchInput.focus();
}

function openQrModal() {
    const qrModal = document.getElementById("qr-modal");
    if (qrModal) {
        qrModal.style.display = "flex";
        qrModal.classList.add("active");
    }
}

function closeQrModal() {
    const qrModal = document.getElementById("qr-modal");
    if (qrModal) {
        qrModal.style.display = "none";
        qrModal.classList.remove("active");
    }
}

async function submitWalkIn(event) {
    event.preventDefault();
    const payload = {
        first_name: document.getElementById("w-first").value,
        last_name: document.getElementById("w-last").value,
        email: document.getElementById("w-email").value,
        organization: document.getElementById("w-org").value,
        title: document.getElementById("w-title").value,
        phone: document.getElementById("w-phone").value
    };

    try {
        const resp = await fetch("/api/walkin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.status === "success") {
            closeWalkInModal();
            selectAttendee(data.attendee.id);
            fetchSearch("");
            showToast(`Registered & Active: ${data.attendee.first_name} ${data.attendee.last_name}`, "success");
        }
    } catch (e) {
        showToast("Error saving walk-in attendee", "error");
    }
}

// --- Google Forms Sync ---
async function syncGoogle() {
    btnSync.disabled = true;
    btnSync.innerHTML = `<span class="btn-icon">⏳</span> Syncing...`;
    try {
        const resp = await fetch("/api/sync", { method: "POST" });
        const data = await resp.json();
        showToast(data.message, data.status === "success" ? "success" : "error");
        updateStats(data.stats);
        fetchSearch(searchInput.value);
    } catch (e) {
        showToast("Failed to sync Google Sheet", "error");
    } finally {
        btnSync.disabled = false;
        btnSync.innerHTML = `<span class="btn-icon">🔄</span> Sync Form`;
    }
}

// --- Outbox & Queue ---
async function refreshOutbox() {
    try {
        const resp = await fetch("/api/outbox");
        const data = await resp.json();
        renderQueueList(data.recent);
    } catch (e) {
        console.error(e);
    }
}

function renderQueueList(deliveries) {
    if (!deliveries || deliveries.length === 0) {
        queueList.innerHTML = `<div style="padding: 20px; text-align: center; color: #64748b; font-size: 13px;">No deliveries yet.</div>`;
        return;
    }

    queueList.innerHTML = deliveries.map(d => {
        let statusBadge = `<span class="badge badge-success">✅ ${d.total_photos} photo${d.total_photos > 1 ? 's' : ''}</span>`;
        if (d.failed_count > 0) {
            statusBadge = `<span class="badge badge-danger" title="${d.failed_count} failed delivery attempts">⚠️ ${d.failed_count} Failed</span>`;
        } else if (d.pending_count > 0) {
            statusBadge = `<span class="badge badge-warning">⏳ ${d.pending_count} Pending</span>`;
        }

        // Format timestamp cleanly
        let timeStr = "";
        const ts = d.latest_delivered_at || d.latest_created_at;
        if (ts) {
            try {
                const dt = new Date(ts.replace(" ", "T"));
                timeStr = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                timeStr = ts.substring(11, 16);
            }
        }

        // Build individual photo status chips
        const photoChips = (d.photos || []).map(p => {
            let chipClass = "chip-sent";
            let chipIcon = "✓";
            if (p.status === "FAILED") {
                chipClass = "chip-failed";
                chipIcon = "✕";
            } else if (p.status === "QUEUED" || p.status === "UPLOADED") {
                chipClass = "chip-pending";
                chipIcon = "⏳";
            }
            const fname = p.export_filename || p.raw_filename || "Photo";
            const tooltip = p.error_message ? `title="${escapeHtml(p.error_message)}"` : `title="Status: ${p.status}"`;
            return `<span class="photo-chip ${chipClass}" ${tooltip}>${chipIcon} ${escapeHtml(fname)}</span>`;
        }).join("");

        return `
            <div class="queue-item">
                <div class="queue-header">
                    <div class="queue-name-group">
                        <span class="queue-att-id">#${d.attendee_id}</span>
                        <span class="queue-name">${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}</span>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        ${statusBadge}
                        <span class="queue-time">${timeStr}</span>
                    </div>
                </div>
                
                <div class="queue-photos-row">
                    ${photoChips}
                </div>

                <div class="queue-footer-row">
                    <span class="queue-email" title="${escapeHtml(d.email)}">✉️ ${escapeHtml(d.email)}</span>
                    ${d.zenfolio_gallery_url ? `<a href="${d.zenfolio_gallery_url}" target="_blank" class="queue-gallery-link">🔗 Gallery</a>` : ''}
                    ${d.failed_count > 0 ? `<button class="btn-retry-inline" onclick="resendEmail(${d.attendee_id})">↻ Retry</button>` : ''}
                </div>
            </div>
        `;
    }).join("");
}

let lastTotalAttendees = 0;

// --- Status Poller ---
async function pollStatus() {
    try {
        const resp = await fetch("/api/active");
        const data = await resp.json();
        updateStats(data.stats);

        // If new attendees synced, auto-refresh search roster
        if (data.stats && data.stats.total_attendees !== lastTotalAttendees) {
            lastTotalAttendees = data.stats.total_attendees;
            fetchSearch(searchInput.value);
        }

        if (data.active) {
            if (activeAttendeeId !== data.active.id) {
                activeAttendeeId = data.active.id;
                renderActiveCard(data.active);
            }
        } else {
            if (activeAttendeeId !== null) {
                activeAttendeeId = null;
                renderActiveCard(null);
            }
        }
        refreshOutbox();
    } catch (e) {
        // silent catch
    }
}

function updateStats(stats) {
    if (!stats) return;
    const elTotal = document.getElementById("stat-total");
    const elClients = document.getElementById("stat-clients");
    const elPhotos = document.getElementById("stat-photos");
    
    if (elTotal) elTotal.textContent = stats.total_attendees || 0;
    if (elClients) elClients.textContent = stats.clients_shot !== undefined ? stats.clients_shot : (stats.total_attendees || 0);
    if (elPhotos) elPhotos.textContent = stats.total_photos || stats.sent_deliveries || 0;
}

// --- Toast Alerts ---
function showToast(msg, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text).replace(/[&<>"']/g, function (m) {
        return {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        }[m];
    });
}
