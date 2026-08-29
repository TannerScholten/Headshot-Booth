// --- Global State & Elements ---
let activeAttendeeId = null;
let searchDebounceTimer = null;
let highlightedIndex = 0;
let chimeEnabled = localStorage.getItem("chimeEnabled") !== "false";
let currentFilter = "all";

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

    // Live update loop every 4 seconds
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
            if (walkinModal.classList.contains("active")) {
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

        // Enter in search -> Select highlighted result or first item
        if (e.key === "Enter" && document.activeElement === searchInput) {
            e.preventDefault();
            if (highlightedIndex >= 0 && highlightedIndex < items.length) {
                items[highlightedIndex].click();
            } else if (items.length > 0) {
                items[0].click();
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
        attendeeList.innerHTML = `<div style="padding: 20px; text-align: center; color: #64748b;">No attendees found.</div>`;
        highlightedIndex = -1;
        return;
    }

    // Default highlight first result for instant Enter-key selection
    highlightedIndex = 0;

    attendeeList.innerHTML = attendees.map((a, idx) => `
        <div class="attendee-item ${idx === 0 ? 'highlighted' : ''} ${activeAttendeeId === a.id ? 'selected' : ''}" onclick="selectAttendee(${a.id})">
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
        activeCard.innerHTML = `
            <div class="active-tag">CURRENT ACTIVE SUBJECT</div>
            <div class="active-content empty-state">
                <div class="empty-icon">📷</div>
                <h2 class="active-name text-muted">No Subject Selected</h2>
                <p class="empty-hint">Type a name below or press <strong>Alt+N</strong> for walk-in registration</p>
            </div>
        `;
        return;
    }

    activeCard.classList.add("active-selected");
    activeCard.innerHTML = `
        <div class="active-tag">CURRENT ACTIVE SUBJECT</div>
        <div class="active-content">
            <div class="active-id-badge">ID: ${attendee.id}</div>
            <h2 class="active-name">${escapeHtml(attendee.first_name)} ${escapeHtml(attendee.last_name)}</h2>
            <div class="active-details">
                ${attendee.title ? `<span class="active-title">${escapeHtml(attendee.title)}</span>` : ''}
                ${attendee.organization ? `<span class="active-org"> &bull; ${escapeHtml(attendee.organization)}</span>` : ''}
            </div>
            <div class="active-meta">
                <span class="active-email">✉️ ${escapeHtml(attendee.email)}</span>
                ${attendee.phone ? `<span class="active-phone">📞 ${escapeHtml(attendee.phone)}</span>` : ''}
                ${attendee.zenfolio_gallery_url ? `
                <span class="gallery-link-group">
                    <a href="${attendee.zenfolio_gallery_url}" target="_blank" class="active-gallery-link">🔗 Private Gallery</a>
                    <button class="btn-copy-url" onclick="copyGalleryUrl('${attendee.zenfolio_gallery_url}')" title="Copy gallery link">📋 Copy Link</button>
                </span>` : ''}
            </div>
            <div class="active-actions">
                <button class="btn btn-warning" onclick="newSession(${attendee.id})">
                    👔 Outfit Change / Session #2
                </button>
                <button class="btn btn-outline" onclick="clearActive()">
                    ✕ Clear Subject
                </button>
            </div>
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
        let emailBadgeClass = "badge-info";
        if (d.status === "SENT") emailBadgeClass = "badge-success";
        if (d.status === "FAILED") emailBadgeClass = "badge-danger";
        if (d.status === "HELD" || d.status === "QUEUED") emailBadgeClass = "badge-warning";

        let smsBadge = "";
        if (d.sms_status && d.sms_status !== "DISABLED" && d.sms_status !== "NOT_PROVIDED") {
            let smsBadgeClass = "badge-info";
            if (d.sms_status === "SENT") smsBadgeClass = "badge-success";
            if (d.sms_status === "FAILED") smsBadgeClass = "badge-danger";
            if (d.sms_status === "QUEUED") smsBadgeClass = "badge-warning";
            smsBadge = `<span class="badge ${smsBadgeClass}" title="SMS Delivery Status">💬 SMS: ${d.sms_status}</span>`;
        }

        return `
            <div class="queue-item">
                <div class="queue-header">
                    <span>${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}</span>
                    <div style="display: flex; gap: 4px; align-items: center;">
                        <span class="badge ${emailBadgeClass}" title="Email Status">✉️ ${d.status}</span>
                        ${smsBadge}
                    </div>
                </div>
                <div class="queue-meta">
                    <span>${escapeHtml(d.filename)}</span>
                    <span>${d.delivered_at ? d.delivered_at.substring(11, 16) : ''}</span>
                </div>
            </div>
        `;
    }).join("");
}

// --- Status Poller ---
async function pollStatus() {
    try {
        const resp = await fetch("/api/active");
        const data = await resp.json();
        updateStats(data.stats);
        if (data.active && activeAttendeeId !== data.active.id) {
            activeAttendeeId = data.active.id;
            renderActiveCard(data.active);
        }
        refreshOutbox();
    } catch (e) {
        // silent catch
    }
}

function updateStats(stats) {
    if (!stats) return;
    document.getElementById("stat-total").textContent = stats.total_attendees || 0;
    document.getElementById("stat-sent").textContent = stats.sent_deliveries || 0;
    document.getElementById("stat-pending").textContent = stats.pending_deliveries || 0;
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
