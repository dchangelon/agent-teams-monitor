// ── State ────────────────────────────────────────────────────────────────────

const state = {
    currentView: 'overview',
    currentTeam: null,
    polling: true,
    pollInterval: 2000,
    pollTimer: null,
    actionBarExpandedCategory: null,
    teamMembers: [],
    stallThresholdMinutes: 10,
    tasksSearch: '',
    tasksOwnerFilter: 'all',
    tasksStatusFilter: 'all',
    messagesSearch: '',
    messagesAgentFilter: 'all',
    messagesTypeFilter: 'all',
    messagesUnresolved: false,
    messagesGroupByPair: false,
    showSystemMessages: false,
    showCompletedTasks: false,
    lastSeenMessageCount: 0,
    expandedTaskDescriptions: {},
    currentActionQueue: [],
    knownPermissionIds: new Set(),
    notificationsEnabled: localStorage.getItem('agent_monitor_notifications') === 'true',
    soundEnabled: localStorage.getItem('agent_monitor_sound') === 'true',
    timelineExpanded: true,
};

// ── Color Mapping ────────────────────────────────────────────────────────────

const COLOR_MAP = {
    blue:   { bg: 'bg-blue-500',   border: 'border-blue-500',   text: 'text-blue-600',   hex: '#3b82f6' },
    green:  { bg: 'bg-green-500',  border: 'border-green-500',  text: 'text-green-600',  hex: '#22c55e' },
    purple: { bg: 'bg-purple-500', border: 'border-purple-500', text: 'text-purple-600', hex: '#a855f7' },
    orange: { bg: 'bg-orange-500', border: 'border-orange-500', text: 'text-orange-600', hex: '#f97316' },
    pink:   { bg: 'bg-pink-500',   border: 'border-pink-500',   text: 'text-pink-600',   hex: '#ec4899' },
    cyan:   { bg: 'bg-cyan-500',   border: 'border-cyan-500',   text: 'text-cyan-600',   hex: '#06b6d4' },
    red:    { bg: 'bg-red-500',    border: 'border-red-500',    text: 'text-red-600',    hex: '#ef4444' },
    yellow: { bg: 'bg-yellow-500', border: 'border-yellow-500', text: 'text-yellow-600', hex: '#eab308' },
};

const DEFAULT_COLOR = { bg: 'bg-gray-400', border: 'border-gray-400', text: 'text-gray-600', hex: '#9ca3af' };

function getColor(name) {
    return COLOR_MAP[name] || DEFAULT_COLOR;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.slice(0, len) + '...' : str;
}

function timeAgo(isoTimestamp) {
    if (!isoTimestamp) return '';
    const now = Date.now();
    const then = new Date(isoTimestamp).getTime();
    const seconds = Math.floor((now - then) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function formatDuration(seconds) {
    if (seconds == null) return '\u2014';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remMin = minutes % 60;
    if (hours < 24) return remMin > 0 ? `${hours}h ${remMin}m` : `${hours}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
}

function colorDot(color, size = 'w-2.5 h-2.5') {
    const c = getColor(color);
    return `<span class="inline-block ${size} rounded-full ${c.bg}"></span>`;
}

function $(id) {
    return document.getElementById(id);
}

// ── Markdown Rendering ──────────────────────────────────────────────────────

const markdownCache = new Map();
const MARKDOWN_CACHE_MAX = 500;

function renderMarkdown(text) {
    if (!text) return '';
    if (markdownCache.has(text)) return markdownCache.get(text);

    const raw = marked.parse(text, { breaks: true, gfm: true });
    const clean = DOMPurify.sanitize(raw);

    if (markdownCache.size >= MARKDOWN_CACHE_MAX) {
        const firstKey = markdownCache.keys().next().value;
        markdownCache.delete(firstKey);
    }
    markdownCache.set(text, clean);
    return clean;
}

// ── System Message Classification ───────────────────────────────────────────

const SYSTEM_MESSAGE_TYPES = new Set([
    'permission_request', 'permission_response',
    'shutdown_request', 'shutdown_response',
    'plan_approval_request', 'plan_approval_response',
    'idle',
]);

const SYSTEM_MSG_ICONS = {
    permission_request: '\uD83D\uDD10',
    permission_response: '\uD83D\uDD13',
    shutdown_request: '\u23FB',
    shutdown_response: '\u23FB',
    plan_approval_request: '\uD83D\uDCCB',
    plan_approval_response: '\uD83D\uDCCB',
    idle: '\u23F8',
};

// ── Toast Notifications ──────────────────────────────────────────────────────

function showToast(message, type = 'error') {
    const container = $('toast-container');
    if (!container) return;

    const colors = {
        error: 'bg-red-500',
        success: 'bg-green-500',
        info: 'bg-blue-500',
    };

    const toast = document.createElement('div');
    toast.className = `${colors[type] || colors.info} text-white text-sm px-4 py-2.5 rounded-lg shadow-lg transition-all duration-300 opacity-0 translate-y-2`;
    toast.textContent = message;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('opacity-0', 'translate-y-2');
        toast.classList.add('opacity-100', 'translate-y-0');
    });

    // Auto-remove after 3s
    setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Browser Notifications ────────────────────────────────────────────────────

function playNotificationBeep() {
    if (!state.soundEnabled) return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        osc.type = 'sine';
        gain.gain.value = 0.3;
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
        // AudioContext not available — silently skip
    }
}

function notifyNewPermissions(pendingPermissions) {
    if (!state.notificationsEnabled) return;
    if (!pendingPermissions || pendingPermissions.length === 0) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;

    const newPerms = pendingPermissions.filter(p => !state.knownPermissionIds.has(p.request_id));
    if (newPerms.length === 0) {
        // Still update known set for existing permissions
        for (const p of pendingPermissions) {
            state.knownPermissionIds.add(p.request_id);
        }
        return;
    }

    if (newPerms.length === 1) {
        const p = newPerms[0];
        new Notification('Permission Request', {
            body: `${p.agent_name} wants to use ${p.tool_name}`,
            tag: `perm-${p.request_id}`,
        });
    } else {
        new Notification('Permission Requests', {
            body: `${newPerms.length} new permission requests need attention`,
            tag: 'perm-batch',
        });
    }

    playNotificationBeep();

    for (const p of pendingPermissions) {
        state.knownPermissionIds.add(p.request_id);
    }
}
