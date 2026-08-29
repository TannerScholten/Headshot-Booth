// --- Global State & Elements ---
let activeAttendeeId = null;
let searchDebounceTimer = null;

const searchInput = document.getElementById("search-input");
const attendeeList = document.getElementById("attendee-list");
const activeCard = document.getElementById("active-card");
const walkinModal = document.getElementById("walkin-modal");
const queueList = document.getElementById("queue-list");
const btnSync = document.getElementById("btn-sync-google");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    setupKeyboardShortcuts();
    setupSearchInput();
    refreshOutbox();

    if (btnSync) {
        btnSync.addEventListener("click", syncGoogle);
    }

    // Live update loop every 4 seconds
    setInterval(pollStatus, 4000);
});

// --- Keyboard Shortcuts ---
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
        }

        // Enter in search -> Select first result
        if (e.key === "Enter" && document.activeElement === searchInput) {
            const firstItem = attendeeList.querySelector(".attendee-item");
            if (firstItem) {
                firstItem.click();
            }
        }
    });
}

// --- Live Search ---
function setupSearchInput() {
    searchInput.addEventListener("input", () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            fetchSearch(searchInput.value);
        }, 200);
    });
}

async function fetchSearch(query) {
    try {
        const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
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
        return;
    }

    attendeeList.innerHTML = attendees.map(a => `
        <div class="attendee-item ${activeAttendeeId === a.id ? 'selected' : ''}" onclick="selectAttendee(${a.id})">
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

function renderActiveCard(attendee) {
    if (!attendee) {
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
                ${attendee.zenfolio_gallery_url ? `<a href="${attendee.zenfolio_gallery_url}" target="_blank" class="active-gallery-link">🔗 Private Gallery</a>` : ''}
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
        let badgeClass = "badge-info";
        if (d.status === "SENT") badgeClass = "badge-success";
        if (d.status === "FAILED") badgeClass = "badge-danger";
        if (d.status === "HELD" || d.status === "QUEUED") badgeClass = "badge-warning";

        return `
            <div class="queue-item">
                <div class="queue-header">
                    <span>${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}</span>
                    <span class="badge ${badgeClass}">${d.status}</span>
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
