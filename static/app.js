// ── State ────────────────────────────────────────────────────────────────────

const state = {
    currentView: 'overview',
    currentTeam: null,
    currentTab: 'timeline',
    polling: true,
    pollInterval: 2000,
    pollTimer: null,
    alertExpanded: false,
    alertTouched: false,
    teamMembers: [],
    stallThresholdMinutes: 10,
    tasksSearch: '',
    tasksOwnerFilter: 'all',
    tasksStatusFilter: 'all',
    messagesSearch: '',
    messagesAgentFilter: 'all',
    messagesTypeFilter: 'all',
    expandedTaskDescriptions: {},
    writeApiKey: localStorage.getItem('agent_monitor_write_api_key') || '',
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

// ── API Layer ────────────────────────────────────────────────────────────────

const api = {
    _jsonHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (state.writeApiKey) {
            headers['X-API-Key'] = state.writeApiKey;
        }
        return headers;
    },
    async _fetch(url, options, silent = false) {
        try {
            const resp = await fetch(url, options);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } catch (err) {
            console.error(`API error: ${url}`, err);
            if (!silent) showToast(`API error: ${err.message}`, 'error');
            return null;
        }
    },

    getTeams() {
        return this._fetch('/api/teams', undefined, true);
    },
    getTeam(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}`, undefined, true);
    },
    getTasks(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/tasks`, undefined, true);
    },
    getMessages(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/messages`, undefined, true);
    },
    getTimeline(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/timeline`, undefined, true);
    },
    getActivity(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/activity`, undefined, true);
    },
    getAgentTimeline(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/agent-timeline`, undefined, true);
    },
    getAlerts(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/alerts`, undefined, true);
    },
    getSnapshot(name) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/snapshot`, undefined, true);
    },
    sendMessage(name, agent, text, fromName = 'user') {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/messages/${encodeURIComponent(agent)}`, {
            method: 'POST',
            headers: this._jsonHeaders(),
            body: JSON.stringify({ text, from_name: fromName }),
        });
    },
    approvePermission(name, agent, requestId, toolUseId) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/permissions/${encodeURIComponent(agent)}/approve`, {
            method: 'POST',
            headers: this._jsonHeaders(),
            body: JSON.stringify({ request_id: requestId, tool_use_id: toolUseId }),
        });
    },
    denyPermission(name, agent, requestId, toolUseId) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/permissions/${encodeURIComponent(agent)}/deny`, {
            method: 'POST',
            headers: this._jsonHeaders(),
            body: JSON.stringify({ request_id: requestId, tool_use_id: toolUseId }),
        });
    },
    removeMember(teamName, agentName) {
        return this._fetch(`/api/teams/${encodeURIComponent(teamName)}/members/${encodeURIComponent(agentName)}/remove`, {
            method: 'POST',
            headers: this._jsonHeaders(),
        });
    },
};

// ── Rendering: Overview ──────────────────────────────────────────────────────

function renderOverview(data) {
    const grid = $('teams-grid');
    const empty = $('overview-empty');
    const loading = $('overview-loading');

    loading.classList.add('hidden');

    if (!data || !data.teams || data.teams.length === 0) {
        grid.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');
    grid.classList.remove('hidden');

    grid.innerHTML = data.teams.map(team => {
        const counts = team.task_counts || {};
        const completed = counts.completed || 0;
        const total = team.total_tasks || 0;
        const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
        const barColor = pct === 100 ? 'bg-green-500' : pct > 0 ? 'bg-blue-500' : 'bg-gray-300';

        const memberDots = (team.members || []).map(m =>
            colorDot(m.color, 'w-3 h-3')
        ).join('');

        const unreadBadge = team.has_unread_messages
            ? '<span class="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></span>'
            : '';

        return `
            <div class="relative bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
                 onclick="navigateToTeam('${escapeHtml(team.name)}')">
                ${unreadBadge}
                <h3 class="font-semibold text-gray-900 mb-1">${escapeHtml(team.name)}</h3>
                <p class="text-sm text-gray-500 mb-3">${escapeHtml(truncate(team.description, 80))}</p>
                <div class="flex items-center gap-1.5 mb-3">
                    ${memberDots}
                    <span class="text-xs text-gray-400 ml-1">${team.member_count} member${team.member_count !== 1 ? 's' : ''}</span>
                </div>
                <div class="mb-2">
                    <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>${completed} of ${total} tasks</span>
                        <span>${pct}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-1.5">
                        <div class="${barColor} h-1.5 rounded-full transition-all" style="width: ${pct}%"></div>
                    </div>
                </div>
                <div class="flex items-center justify-between text-xs text-gray-400">
                    <span>${counts.in_progress || 0} in progress</span>
                    <span>${counts.pending || 0} pending</span>
                </div>
            </div>
        `;
    }).join('');
}

// ── Rendering: Detail — Alert Banner ─────────────────────────────────────────

function renderAlertBanner(data) {
    const banner = $('alert-banner');
    const details = $('alert-details');
    const chevron = $('alert-chevron');

    if (!data || !data.pending_permissions || data.pending_permissions.length === 0) {
        banner.classList.add('hidden');
        state.alertExpanded = false;
        state.alertTouched = false;
        return;
    }

    banner.classList.remove('hidden');
    const count = data.pending_permissions.length;
    if (!state.alertTouched) {
        state.alertExpanded = true;
    }
    $('alert-count').textContent = `${count} pending permission request${count !== 1 ? 's' : ''}`;

    details.innerHTML = data.pending_permissions.map(perm => `
        <div class="flex items-center justify-between bg-white rounded-lg border border-amber-100 px-3 py-2"
             data-request-id="${escapeHtml(perm.request_id)}">
            <div class="flex items-center gap-2">
                ${colorDot(perm.agent_color)}
                <span class="text-sm font-medium text-gray-700">${escapeHtml(perm.agent_name)}</span>
                <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">${escapeHtml(perm.tool_name)}</span>
                <span class="text-xs text-gray-500">${escapeHtml(truncate(perm.description, 60))}</span>
            </div>
            <div class="flex gap-2 perm-actions">
                <button onclick="handlePermission('approve', '${escapeHtml(perm.agent_name)}', '${escapeHtml(perm.request_id)}', '${escapeHtml(perm.tool_use_id)}')"
                    class="text-xs px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">
                    Approve
                </button>
                <button onclick="handlePermission('deny', '${escapeHtml(perm.agent_name)}', '${escapeHtml(perm.request_id)}', '${escapeHtml(perm.tool_use_id)}')"
                    class="text-xs px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 transition-colors">
                    Deny
                </button>
            </div>
        </div>
    `).join('');

    if (state.alertExpanded) {
        details.classList.remove('hidden');
        chevron.classList.add('rotate-180');
    } else {
        details.classList.add('hidden');
        chevron.classList.remove('rotate-180');
    }
}

// ── Rendering: Detail — Completion Bar ───────────────────────────────────────

function renderCompletionBar(counts) {
    if (!counts) return;

    const completed = counts.completed || 0;
    const total = counts.total || 0;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

    $('completion-text').textContent = `${completed} of ${total} tasks complete`;
    $('completion-pct').textContent = `${pct}%`;

    const fill = $('completion-fill');
    fill.style.width = `${pct}%`;

    if (pct === 100) {
        fill.className = 'h-2.5 rounded-full transition-all duration-500 bg-green-500';
    } else if (pct > 0) {
        fill.className = 'h-2.5 rounded-full transition-all duration-500 bg-blue-500';
    } else {
        fill.className = 'h-2.5 rounded-full transition-all duration-500 bg-gray-300';
    }
}

// ── Rendering: Detail — Activity Cards ───────────────────────────────────────

function renderActivityCards(data) {
    const container = $('activity-cards');
    if (!data || !data.agents || data.agents.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-400">No agent activity</p>';
        return;
    }

    const STATUS_CONFIG = {
        active:    { bg: 'bg-green-100', text: 'text-green-700', label: 'Active' },
        idle:      { bg: 'bg-gray-100',  text: 'text-gray-600',  label: 'Idle' },
        completed: { bg: 'bg-blue-100',  text: 'text-blue-700',  label: 'Completed' },
        stalled:   { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Stalled' },
    };

    container.innerHTML = data.agents.map(agent => {
        const c = getColor(agent.color);
        const stalledClass = agent.is_stalled ? `border-amber-400 ring-1 ring-amber-200` : 'border-gray-200';
        const totalTasks = agent.tasks_pending + agent.tasks_in_progress + agent.tasks_completed;

        const modelShort = (agent.model || '').replace('claude-', '').split('-')[0] || '';

        const sc = STATUS_CONFIG[agent.agent_status] || STATUS_CONFIG.active;
        const statusBadge = `<span class="text-xs ${sc.bg} ${sc.text} px-1.5 py-0.5 rounded font-medium">${sc.label}</span>`;

        const stallBadge = agent.is_stalled
            ? `<span class="text-xs text-amber-600 font-medium">stalled ${formatDuration((agent.minutes_since_last_activity || 0) * 60)} (>${state.stallThresholdMinutes}m)</span>`
            : '';

        const showRemove = agent.agent_status === 'completed' || agent.agent_status === 'stalled';
        const removeBtn = showRemove
            ? `<button onclick="handleRemoveMember('${escapeHtml(agent.name)}')"
                 class="text-xs text-red-500 hover:text-red-700 hover:underline mt-1">Remove</button>`
            : '';

        return `
            <div class="flex-shrink-0 bg-white rounded-lg border ${stalledClass} p-3 min-w-[180px]">
                <div class="flex items-center gap-2 mb-2">
                    ${colorDot(agent.color, 'w-2 h-2')}
                    <span class="text-sm font-medium text-gray-800">${escapeHtml(agent.name)}</span>
                    ${statusBadge}
                </div>
                <div class="flex items-center gap-1.5 mb-2">
                    <span class="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">${escapeHtml(agent.agent_type)}</span>
                    ${modelShort ? `<span class="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">${escapeHtml(modelShort)}</span>` : ''}
                </div>
                <div class="text-xs text-gray-500 space-y-1">
                    <div class="flex items-center gap-2">
                        <span>${agent.tasks_completed}/${totalTasks} tasks</span>
                        <span class="text-gray-300">|</span>
                        <span>${agent.messages_sent + agent.messages_received} msgs</span>
                    </div>
                    ${stallBadge}
                    ${removeBtn}
                </div>
            </div>
        `;
    }).join('');
}

// ── Rendering: Timeline Tab — Swim Lanes ─────────────────────────────────────

function renderSwimLanes(data) {
    const container = $('swim-lanes-container');
    const empty = $('timeline-empty');

    if (!data || !data.agents || data.agents.length === 0) {
        container.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');

    // Calculate time range
    const allTimestamps = [];
    data.agents.forEach(agent => {
        allTimestamps.push(new Date(agent.joined_at).getTime());
        if (agent.shutdown_at) allTimestamps.push(new Date(agent.shutdown_at).getTime());
        agent.events.forEach(e => allTimestamps.push(new Date(e.timestamp).getTime()));
    });

    const rangeStart = Math.min(...allTimestamps);
    const rangeEnd = Math.max(Date.now(), ...allTimestamps);
    const rangeDuration = rangeEnd - rangeStart || 1;
    const rangeStartIso = new Date(rangeStart).toISOString();
    const rangeEndIso = new Date(rangeEnd).toISOString();

    function pct(isoTs) {
        const t = new Date(isoTs).getTime();
        return ((t - rangeStart) / rangeDuration) * 100;
    }

    // Time axis labels
    const timeLabels = [];
    const labelCount = 5;
    for (let i = 0; i <= labelCount; i++) {
        const t = rangeStart + (rangeDuration * i / labelCount);
        const label = new Date(t).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        });
        const leftPct = (i / labelCount) * 100;
        timeLabels.push(`<span class="time-label" style="left: ${leftPct}%">${label}</span>`);
    }

    // Event marker pill config
    function markerConfig(eventType) {
        const configs = {
            task_started:       { label: 'START',   bg: 'bg-blue-100',   text: 'text-blue-700',   border: 'border-blue-300' },
            task_completed:     { label: 'DONE',    bg: 'bg-green-100',  text: 'text-green-700',  border: 'border-green-300' },
            shutdown_requested: { label: 'STOP',    bg: 'bg-red-100',    text: 'text-red-700',    border: 'border-red-300' },
            message_sent:       { label: 'MSG \u2192', bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200' },
            message_received:   { label: '\u2190 MSG', bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
        };
        return configs[eventType] || { label: '\u25cf', bg: 'bg-gray-100', text: 'text-gray-600', border: 'border-gray-200' };
    }

    const MARKER_DISPLAY_NAMES = {
        task_started: 'task started',
        task_completed: 'task completed',
        shutdown_requested: 'shutdown',
        message_sent: 'message sent',
        message_received: 'message received',
    };

    // Build lanes
    const lanes = data.agents.map(agent => {
        const c = getColor(agent.color);
        const barStart = pct(agent.joined_at);
        const barEnd = agent.shutdown_at ? pct(agent.shutdown_at) : 100;
        const barWidth = Math.max(barEnd - barStart, 0.5);

        // Build markers with vertical stagger when events overlap
        const visibleEvents = agent.events.filter(e => e.event_type !== 'joined');
        const sortedEvents = [...visibleEvents].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        let staggerIndex = 0;
        const markers = sortedEvents.map((e, i) => {
            const left = pct(e.timestamp);
            const mc = markerConfig(e.event_type);
            // Stagger vertically when pills are within 3% of each other
            if (i > 0) {
                const prevLeft = pct(sortedEvents[i - 1].timestamp);
                if (Math.abs(left - prevLeft) < 3) {
                    staggerIndex++;
                } else {
                    staggerIndex = 0;
                }
            }
            const yOffset = staggerIndex % 2 === 0 ? '35%' : '65%';
            return `
                <div class="event-marker-pill ${mc.bg} ${mc.text} border ${mc.border}" style="left: ${left}%; top: ${yOffset}"
                     data-event-type="${e.event_type}"
                     data-related-agent="${e.related_agent || ''}">
                    <span class="event-marker-label">${mc.label}</span>
                    <div class="marker-tooltip">${escapeHtml(e.description)} · ${escapeHtml(new Date(e.timestamp).toLocaleString())}</div>
                </div>
            `;
        }).join('');

        return `
            <div class="swim-lane-label">
                ${colorDot(agent.color, 'w-2.5 h-2.5')}
                <div class="min-w-0">
                    <div class="text-sm font-medium text-gray-800 truncate">${escapeHtml(agent.name)}</div>
                    <div class="text-xs text-gray-400 truncate">${escapeHtml(agent.agent_type)}</div>
                </div>
            </div>
            <div class="swim-lane-bar-container">
                <div class="swim-lane-bar" style="left: ${barStart}%; width: ${barWidth}%; background: ${c.hex}"></div>
                ${markers}
            </div>
        `;
    }).join('');

    // Legend bar
    const legendTypes = ['task_started', 'task_completed', 'shutdown_requested', 'message_sent', 'message_received'];
    const legend = `
        <div class="flex items-center gap-4 mb-3 pb-3 border-b border-gray-100 flex-wrap">
            <span class="text-xs text-gray-400 font-medium uppercase tracking-wide">Legend</span>
            ${legendTypes.map(type => {
                const mc = markerConfig(type);
                return `<span class="inline-flex items-center gap-1.5 text-xs">
                    <span class="${mc.bg} ${mc.text} border ${mc.border} px-1.5 py-0.5 rounded text-[10px] font-semibold">${mc.label}</span>
                    <span class="text-gray-500">${MARKER_DISPLAY_NAMES[type]}</span>
                </span>`;
            }).join('')}
        </div>
    `;

    // Build message pairs for SVG connectors
    const laneHeight = 56;
    const laneMap = {};
    data.agents.forEach((agent, i) => { laneMap[agent.name] = i; });

    const messagePairs = [];
    data.agents.forEach((agent, laneIndex) => {
        agent.events.forEach(e => {
            if (e.event_type === 'message_sent' && e.related_agent) {
                const toLane = laneMap[e.related_agent];
                if (toLane !== undefined) {
                    messagePairs.push({
                        fromLane: laneIndex,
                        toLane: toLane,
                        timestamp: e.timestamp,
                        fromAgent: agent.name,
                        toAgent: e.related_agent,
                        description: e.description,
                        color: getColor(agent.color).hex,
                    });
                }
            }
        });
    });

    // Offset clustered messages so lines fan out
    const sortedPairs = [...messagePairs].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const clusterThreshold = 1.5; // % of timeline range
    let clusterStart = 0;
    for (let i = 1; i <= sortedPairs.length; i++) {
        const prevPct = pct(sortedPairs[i - 1].timestamp);
        const currPct = i < sortedPairs.length ? pct(sortedPairs[i].timestamp) : Infinity;
        if (currPct - prevPct > clusterThreshold || i === sortedPairs.length) {
            const clusterSize = i - clusterStart;
            if (clusterSize > 1) {
                const spread = Math.min(clusterSize * 5, 20);
                for (let j = clusterStart; j < i; j++) {
                    sortedPairs[j]._xOffset = ((j - clusterStart) - (clusterSize - 1) / 2) * (spread / clusterSize);
                }
            }
            clusterStart = i;
        }
    }

    // Render SVG message connectors
    let connectorSvg = '';
    if (sortedPairs.length > 0) {
        const svgWidth = 1000;
        const totalHeight = data.agents.length * laneHeight;

        const paths = sortedPairs.map(pair => {
            const xNorm = pct(pair.timestamp) * (svgWidth / 100) + (pair._xOffset || 0);
            const y1 = (pair.fromLane * laneHeight) + (laneHeight / 2);
            const y2 = (pair.toLane * laneHeight) + (laneHeight / 2);

            const verticalDist = Math.abs(y2 - y1);
            const cpXOffset = Math.min(verticalDist * 0.3, 30);
            const direction = y2 > y1 ? 1 : -1;
            const cpX = xNorm + (cpXOffset * direction);
            const cpY = (y1 + y2) / 2;

            return `<path
                d="M ${xNorm} ${y1} Q ${cpX} ${cpY} ${xNorm} ${y2}"
                stroke="${pair.color}"
                stroke-width="1.5"
                fill="none"
                opacity="0.55"
                stroke-dasharray="4 2"
            ><title>${escapeHtml(pair.fromAgent)} \u2192 ${escapeHtml(pair.toAgent)}</title></path>
            <circle cx="${xNorm}" cy="${y1}" r="3" fill="${pair.color}" opacity="0.6"/>
            <circle cx="${xNorm}" cy="${y2}" r="3" fill="${pair.color}" opacity="0.6"/>`;
        }).join('');

        connectorSvg = `<svg class="message-connector-svg"
             viewBox="0 0 ${svgWidth} ${totalHeight}"
             preserveAspectRatio="none"
             style="height: ${totalHeight}px; width: 100%;">
            ${paths}
        </svg>`;
    }

    container.innerHTML = `
        <div class="bg-white rounded-lg border border-gray-200 p-4 overflow-x-auto">
            ${legend}
            <div class="mb-2 text-xs text-gray-500">
                <span>${escapeHtml(new Date(rangeStartIso).toLocaleString())}</span>
                <span class="mx-1 text-gray-300">&rarr;</span>
                <span>${escapeHtml(new Date(rangeEndIso).toLocaleString())}</span>
            </div>
            <div class="swim-lane-time-axis">
                <div></div>
                <div class="swim-lane-time-labels">${timeLabels.join('')}</div>
            </div>
            <div class="swim-lane-chart-wrapper">
                <div class="swim-lane-chart">
                    ${lanes}
                </div>
                ${connectorSvg}
            </div>
        </div>
    `;
}

// ── Rendering: Tasks Tab — Kanban ────────────────────────────────────────────

function applyTaskFilters(tasks) {
    const query = state.tasksSearch.trim().toLowerCase();
    return (tasks || []).filter(task => {
        const ownerOk = state.tasksOwnerFilter === 'all' || (task.owner || '') === state.tasksOwnerFilter;
        const statusOk = state.tasksStatusFilter === 'all' || task.status === state.tasksStatusFilter;
        const textHaystack = `${task.subject || ''} ${task.description || ''}`.toLowerCase();
        const queryOk = !query || textHaystack.includes(query);
        return ownerOk && statusOk && queryOk;
    });
}

function populateTaskFilters(tasks) {
    const ownerSelect = $('tasks-owner-filter');
    if (!ownerSelect) return;
    const owners = [...new Set((tasks || []).map(t => t.owner).filter(Boolean))].sort();
    const prev = state.tasksOwnerFilter;
    ownerSelect.innerHTML = '<option value="all">All owners</option>' +
        owners.map(owner => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`).join('');
    ownerSelect.value = owners.includes(prev) ? prev : 'all';
    state.tasksOwnerFilter = ownerSelect.value;
}

function toggleTaskDescription(taskId) {
    state.expandedTaskDescriptions[taskId] = !state.expandedTaskDescriptions[taskId];
    poll();
}

function renderKanban(tasksData) {
    const board = $('kanban-board');
    const empty = $('tasks-empty');

    if (!tasksData || !tasksData.tasks || tasksData.tasks.length === 0) {
        board.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }

    populateTaskFilters(tasksData.tasks);
    const filteredTasks = applyTaskFilters(tasksData.tasks);
    if (filteredTasks.length === 0) {
        board.classList.add('hidden');
        empty.classList.remove('hidden');
        empty.textContent = 'No tasks match current filters';
        return;
    }

    empty.classList.add('hidden');
    empty.textContent = 'No tasks yet';
    board.classList.remove('hidden');

    const columns = {
        pending: { label: 'Pending', color: 'gray', tasks: [] },
        in_progress: { label: 'In Progress', color: 'blue', tasks: [] },
        completed: { label: 'Completed', color: 'green', tasks: [] },
    };

    filteredTasks.forEach(t => {
        if (columns[t.status]) columns[t.status].tasks.push(t);
    });

    const stallSeconds = state.stallThresholdMinutes * 60;

    board.innerHTML = Object.entries(columns).map(([status, col]) => {
        const headerColors = {
            pending: 'bg-gray-100 text-gray-600',
            in_progress: 'bg-blue-50 text-blue-600',
            completed: 'bg-green-50 text-green-600',
        };

        const cards = col.tasks.map(t => {
            const durationText = formatDuration(t.status_duration_seconds);
            const isStale = t.status_duration_seconds != null && t.status_duration_seconds > stallSeconds && t.status !== 'completed';
            const durationColor = isStale ? 'text-amber-600 font-medium' : 'text-gray-400';
            const description = t.description || '';
            const isExpanded = !!state.expandedTaskDescriptions[t.id];
            const showDescription = description.length > 0;
            const descriptionText = isExpanded ? description : truncate(description, 120);
            const descriptionToggle = description.length > 120
                ? `<button onclick="toggleTaskDescription('${escapeHtml(t.id)}')" class="text-xs text-blue-500 hover:text-blue-700 mt-1">${isExpanded ? 'Show less' : 'Show more'}</button>`
                : '';

            const blockedBadge = t.blocked_by && t.blocked_by.length > 0
                ? `<span class="text-xs text-red-500">blocked by #${t.blocked_by.join(', #')}</span>`
                : '';

            return `
                <div class="kanban-card bg-white rounded border border-gray-200 p-3 mb-2">
                    <div class="flex items-start justify-between mb-1">
                        <span class="text-sm font-medium text-gray-800">${escapeHtml(t.subject)}</span>
                        <span class="text-xs text-gray-400 ml-2">#${escapeHtml(t.id)}</span>
                    </div>
                    ${t.owner ? `<div class="text-xs text-gray-500 mb-1">${escapeHtml(t.owner)}</div>` : ''}
                    ${showDescription ? `<div class="text-xs text-gray-500">${escapeHtml(descriptionText)}</div>${descriptionToggle}` : ''}
                    <div class="flex items-center gap-2">
                        <span class="text-xs ${durationColor}">${durationText}</span>
                        ${blockedBadge}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="kanban-column">
                <div class="text-xs font-medium ${headerColors[status]} px-3 py-1.5 rounded-t mb-2 flex items-center justify-between">
                    <span>${col.label}</span>
                    <span>${col.tasks.length}</span>
                </div>
                ${cards || '<p class="text-xs text-gray-300 text-center py-4">None</p>'}
            </div>
        `;
    }).join('');
}

// ── Rendering: Tasks Tab — Task Timeline ─────────────────────────────────────

function renderTaskTimeline(timelineData) {
    const feed = $('task-timeline-feed');
    const empty = $('task-timeline-empty');

    if (!timelineData || !timelineData.events || timelineData.events.length === 0) {
        feed.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');

    feed.innerHTML = timelineData.events.map(e => {
        let transColor = 'bg-gray-200';
        if (e.new_status === 'in_progress') transColor = 'bg-blue-500';
        else if (e.new_status === 'completed') transColor = 'bg-green-500';

        return `
            <div class="flex items-start gap-2 text-xs">
                <div class="w-1.5 h-1.5 rounded-full ${transColor} mt-1.5 flex-shrink-0"></div>
                <div>
                    <span class="text-gray-600">Task #${escapeHtml(e.task_id)}</span>
                    <span class="text-gray-400">${escapeHtml(e.task_subject)}</span>
                    <span class="text-gray-500">${escapeHtml(e.old_status)} &rarr; ${escapeHtml(e.new_status)}</span>
                    ${e.owner ? `<span class="text-gray-400">by ${escapeHtml(e.owner)}</span>` : ''}
                    <span class="text-gray-300 ml-1">${timeAgo(e.timestamp)}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ── Rendering: Messages Tab ──────────────────────────────────────────────────

function populateMessageFilters(messages) {
    const agentSelect = $('messages-agent-filter');
    if (!agentSelect) return;
    const agents = [...new Set(
        (messages || [])
            .flatMap(msg => [msg.from_agent, msg.target_agent])
            .filter(Boolean)
    )].sort();
    const prev = state.messagesAgentFilter;
    agentSelect.innerHTML = '<option value="all">All agents</option>' +
        agents.map(agent => `<option value="${escapeHtml(agent)}">${escapeHtml(agent)}</option>`).join('');
    agentSelect.value = agents.includes(prev) ? prev : 'all';
    state.messagesAgentFilter = agentSelect.value;
}

function applyMessageFilters(messages) {
    const query = state.messagesSearch.trim().toLowerCase();
    return (messages || []).filter(msg => {
        const agentOk = state.messagesAgentFilter === 'all' ||
            msg.from_agent === state.messagesAgentFilter ||
            msg.target_agent === state.messagesAgentFilter;
        const typeOk = state.messagesTypeFilter === 'all' || msg.message_type === state.messagesTypeFilter;
        const textHaystack = `${msg.from_agent || ''} ${msg.target_agent || ''} ${msg.text || ''}`.toLowerCase();
        const queryOk = !query || textHaystack.includes(query);
        return agentOk && typeOk && queryOk;
    });
}

function renderMessages(data) {
    const feed = $('message-feed');
    const empty = $('messages-empty');

    if (!data || !data.messages || data.messages.length === 0) {
        feed.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');

    populateMessageFilters(data.messages);
    const filtered = applyMessageFilters(data.messages);
    if (filtered.length === 0) {
        feed.innerHTML = '';
        empty.textContent = 'No messages match current filters';
        empty.classList.remove('hidden');
        return;
    }
    empty.textContent = 'No messages yet';

    // Newest first
    const sorted = [...filtered].reverse();

    feed.innerHTML = sorted.map(msg => {
        const c = getColor(msg.color);
        let bodyHtml = '';
        let cardBg = 'bg-white';

        if (msg.message_type === 'permission_request' && msg.parsed_content) {
            cardBg = 'bg-yellow-50';
            bodyHtml = `
                <div class="text-xs text-gray-500 mb-1">Permission Request</div>
                <div class="text-sm">
                    <span class="font-medium">${escapeHtml(msg.parsed_content.tool_name || '')}</span>
                    <span class="text-gray-500 ml-1">${escapeHtml(truncate(msg.parsed_content.description || '', 100))}</span>
                </div>
            `;
        } else if (msg.message_type === 'shutdown_request') {
            cardBg = 'bg-gray-50';
            bodyHtml = `
                <div class="text-xs text-gray-500 mb-1">Shutdown Request</div>
                <div class="text-sm text-gray-600">${escapeHtml(msg.text)}</div>
            `;
        } else {
            bodyHtml = `<div class="text-sm text-gray-700">${escapeHtml(msg.text)}</div>`;
        }

        return `
            <div class="${cardBg} rounded-lg border border-gray-200 p-3 border-l-4 ${c.border}">
                <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center gap-1.5">
                        ${colorDot(msg.color, 'w-2 h-2')}
                        <span class="text-xs font-medium text-gray-600">${escapeHtml(msg.from_agent)}</span>
                        <span class="text-xs text-gray-300">&rarr;</span>
                        <span class="text-xs text-gray-400">${escapeHtml(msg.target_agent || '')}</span>
                    </div>
                    <span class="text-xs text-gray-400">${timeAgo(msg.timestamp)}</span>
                </div>
                ${bodyHtml}
            </div>
        `;
    }).join('');
}

function renderSendForm(members) {
    const select = $('msg-agent-select');
    if (!members || members.length === 0) return;

    // Preserve current selection if possible
    const currentVal = select.value;
    const options = '<option value="">Select agent...</option>' +
        members.map(m => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join('');
    select.innerHTML = options;
    if (currentVal) select.value = currentVal;
}

// ── Navigation ───────────────────────────────────────────────────────────────

function navigateToTeam(teamName) {
    state.currentView = 'detail';
    state.currentTeam = teamName;
    state.currentTab = 'timeline';
    state.alertExpanded = false;
    state.alertTouched = false;
    state.expandedTaskDescriptions = {};

    $('overview-view').classList.add('hidden');
    $('detail-view').classList.remove('hidden');
    $('detail-view').classList.add('view-fade-in');
    $('team-name-header').textContent = teamName;

    updateTabUI();
    poll();
}

function navigateToOverview() {
    state.currentView = 'overview';
    state.currentTeam = null;

    $('detail-view').classList.add('hidden');
    $('overview-view').classList.remove('hidden');
    $('overview-view').classList.add('view-fade-in');

    poll();
}

function switchTab(tabName) {
    state.currentTab = tabName;
    updateTabUI();
    poll();
}

function updateTabUI() {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const tab = btn.dataset.tab;
        if (tab === state.currentTab) {
            btn.classList.add('border-blue-500', 'text-blue-600');
            btn.classList.remove('border-transparent', 'text-gray-500');
        } else {
            btn.classList.remove('border-blue-500', 'text-blue-600');
            btn.classList.add('border-transparent', 'text-gray-500');
        }
    });

    // Show/hide tab content
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
    });
    const activeTab = $(`tab-${state.currentTab}`);
    if (activeTab) activeTab.classList.remove('hidden');
}

// ── Polling ──────────────────────────────────────────────────────────────────

async function poll() {
    if (state.currentView === 'overview') {
        const data = await api.getTeams();
        if (data) renderOverview(data);
    } else if (state.currentView === 'detail' && state.currentTeam) {
        const name = state.currentTeam;

        const snapshot = await api.getSnapshot(name);
        if (snapshot) {
            renderAlertBanner({ pending_permissions: snapshot.pending_permissions || [] });
            renderActivityCards({ agents: snapshot.activity || [] });
            renderCompletionBar(snapshot.counts || null);
            state.stallThresholdMinutes = snapshot.monitor_config?.stall_threshold_minutes || 10;
            $('team-description-header').textContent = snapshot.team?.description || '';
            state.teamMembers = snapshot.team?.members || [];
            renderSendForm(state.teamMembers);
        }

        // Tab-specific fetches
        if (state.currentTab === 'timeline') {
            const timelineData = await api.getAgentTimeline(name);
            if (timelineData) renderSwimLanes(timelineData);
        } else if (state.currentTab === 'tasks') {
            const [tasksData, timelineData] = await Promise.all([
                api.getTasks(name),
                api.getTimeline(name),
            ]);
            if (tasksData) {
                renderKanban(tasksData);
                renderCompletionBar(tasksData.counts);
            }
            if (timelineData) renderTaskTimeline(timelineData);
        } else if (state.currentTab === 'messages') {
            const messagesData = await api.getMessages(name);
            if (messagesData) renderMessages(messagesData);
        }
    }
}

function startPolling() {
    stopPolling();
    poll();
    state.pollTimer = setInterval(() => {
        if (state.polling) poll();
    }, state.pollInterval);
}

function stopPolling() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

// ── Event Handlers ───────────────────────────────────────────────────────────

function ensureWriteApiKey() {
    if (state.writeApiKey) return true;
    const key = prompt('Enter monitor write API key (leave empty if write auth is disabled):', '');
    if (key === null) return false;
    state.writeApiKey = key.trim();
    localStorage.setItem('agent_monitor_write_api_key', state.writeApiKey);
    return true;
}

async function handlePermission(action, agentName, requestId, toolUseId) {
    const name = state.currentTeam;
    if (!name) return;
    if (!ensureWriteApiKey()) return;

    const actionLabel = action === 'approve' ? 'Approve' : 'Deny';
    const pendingLabel = action === 'approve' ? 'Approving...' : 'Denying...';

    // Immediate UI feedback: disable buttons and show pending state
    const card = document.querySelector(`[data-request-id="${CSS.escape(requestId)}"]`);
    let originalActionsHtml = '';
    if (card) {
        const actionsDiv = card.querySelector('.perm-actions');
        if (actionsDiv) {
            originalActionsHtml = actionsDiv.innerHTML;
            actionsDiv.innerHTML = `<span class="text-xs text-gray-500 font-medium">${pendingLabel}</span>`;
        }
    }

    let result;
    if (action === 'approve') {
        result = await api.approvePermission(name, agentName, requestId, toolUseId);
    } else {
        result = await api.denyPermission(name, agentName, requestId, toolUseId);
    }

    if (result) {
        if (card) {
            const actionsDiv = card.querySelector('.perm-actions');
            if (actionsDiv) {
                const statusLabel = action === 'approve' ? 'Approved' : 'Denied';
                const statusColor = action === 'approve' ? 'text-green-600' : 'text-red-600';
                actionsDiv.innerHTML = `<span class="text-xs ${statusColor} font-medium">${statusLabel}</span>`;
            }
        }
        showToast(`Permission ${action === 'approve' ? 'approved' : 'denied'} for ${agentName}`, 'success');
    } else if (card) {
        const actionsDiv = card.querySelector('.perm-actions');
        if (actionsDiv && originalActionsHtml) {
            actionsDiv.innerHTML = originalActionsHtml;
        }
        showToast(`${actionLabel} failed for ${agentName}. Try again.`, 'error');
    }
    poll();
}

async function handleRemoveMember(agentName) {
    const name = state.currentTeam;
    if (!name) return;
    if (!ensureWriteApiKey()) return;

    if (!confirm(`Remove "${agentName}" from team config? This allows TeamDelete to proceed.`)) {
        return;
    }

    const result = await api.removeMember(name, agentName);
    if (result) {
        showToast(`${agentName} removed from team config`, 'success');
    }
    poll();
}

async function handleSendMessage() {
    const agentSelect = $('msg-agent-select');
    const textInput = $('msg-text-input');
    const agent = agentSelect.value;
    const text = textInput.value.trim();

    if (!agent || !text || !state.currentTeam) return;
    if (!ensureWriteApiKey()) return;

    const result = await api.sendMessage(state.currentTeam, agent, text);
    if (result) {
        showToast(`Message sent to ${agent}`, 'success');
    }
    textInput.value = '';
    poll();
}

// ── Initialization ───────────────────────────────────────────────────────────

function init() {
    // Back button
    $('back-btn').addEventListener('click', navigateToOverview);

    // Pause/Resume
    $('pause-btn').addEventListener('click', () => {
        state.polling = !state.polling;
        const btn = $('pause-btn');
        const indicator = $('live-indicator');

        if (state.polling) {
            btn.textContent = 'Pause';
            indicator.innerHTML = `
                <span class="relative flex h-2.5 w-2.5">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                </span>
                <span class="text-green-600 font-medium">Live</span>
            `;
            poll();
        } else {
            btn.textContent = 'Resume';
            indicator.innerHTML = `
                <span class="inline-flex rounded-full h-2.5 w-2.5 bg-gray-400"></span>
                <span class="text-gray-500 font-medium">Paused</span>
            `;
        }
    });

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Alert expand/collapse
    $('alert-toggle').addEventListener('click', () => {
        state.alertTouched = true;
        state.alertExpanded = !state.alertExpanded;
        const details = $('alert-details');
        const chevron = $('alert-chevron');
        if (state.alertExpanded) {
            details.classList.remove('hidden');
            chevron.classList.add('rotate-180');
        } else {
            details.classList.add('hidden');
            chevron.classList.remove('rotate-180');
        }
    });

    // Send message form
    $('msg-send-btn').addEventListener('click', handleSendMessage);
    $('msg-text-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSendMessage();
    });

    // Enable/disable send button based on inputs
    function updateSendButton() {
        const agent = $('msg-agent-select').value;
        const text = $('msg-text-input').value.trim();
        $('msg-send-btn').disabled = !agent || !text;
    }
    $('msg-agent-select').addEventListener('change', updateSendButton);
    $('msg-text-input').addEventListener('input', updateSendButton);

    // Tasks filters
    $('tasks-search-input').addEventListener('input', (e) => {
        state.tasksSearch = e.target.value || '';
        poll();
    });
    $('tasks-owner-filter').addEventListener('change', (e) => {
        state.tasksOwnerFilter = e.target.value || 'all';
        poll();
    });
    $('tasks-status-filter').addEventListener('change', (e) => {
        state.tasksStatusFilter = e.target.value || 'all';
        poll();
    });

    // Messages filters
    $('messages-search-input').addEventListener('input', (e) => {
        state.messagesSearch = e.target.value || '';
        poll();
    });
    $('messages-agent-filter').addEventListener('change', (e) => {
        state.messagesAgentFilter = e.target.value || 'all';
        poll();
    });
    $('messages-type-filter').addEventListener('change', (e) => {
        state.messagesTypeFilter = e.target.value || 'all';
        poll();
    });

    // Initialize tab UI
    updateTabUI();

    // Start polling
    startPolling();
}

// Boot
document.addEventListener('DOMContentLoaded', init);
