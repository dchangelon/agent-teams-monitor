// ── Rendering: Detail — Action Bar (compact) ────────────────────────────────

function renderActionBar(items, recentAutoApprovals) {
    const bar = $('action-bar');
    const content = $('action-bar-content');
    const details = $('action-bar-details');

    recentAutoApprovals = recentAutoApprovals || [];

    if ((!items || items.length === 0) && recentAutoApprovals.length === 0) {
        bar.classList.add('hidden');
        return;
    }

    bar.classList.remove('hidden');

    const perms = items.filter(i => i.category === 'permission' && i.permission_data);
    const stalled = items.filter(i => i.category === 'stalled_agent');
    const blocked = items.filter(i => i.category === 'blocked_task');

    const segments = [];

    // Permission segment — inline approve/deny for 1-2 permissions, "Approve All" for 3+
    if (perms.length === 1) {
        const p = perms[0];
        const pd = p.permission_data;
        const riskHtml = p.risk_level === 'medium'
            ? '<span class="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">Review</span>'
            : p.risk_level === 'low'
                ? '<span class="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">Low risk</span>'
                : '';
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0">\uD83D\uDD10</span>
                ${colorDot(p.agent_color, 'w-2 h-2')}
                <span class="text-sm text-gray-700">${escapeHtml(p.agent_name)}: ${escapeHtml(pd.tool_name)}</span>
                <span class="text-xs text-gray-400 truncate max-w-[200px]">${escapeHtml(truncate(p.detail, 40))}</span>
                ${riskHtml}
                <button onclick="handlePermission('approve', '${escapeHtml(p.agent_name)}', '${escapeHtml(pd.request_id)}', '${escapeHtml(pd.tool_use_id)}')"
                    class="text-xs px-2.5 py-1 bg-green-500 text-white rounded hover:bg-green-600 transition-colors flex-shrink-0">Approve</button>
                <button onclick="handlePermission('deny', '${escapeHtml(p.agent_name)}', '${escapeHtml(pd.request_id)}', '${escapeHtml(pd.tool_use_id)}')"
                    class="text-xs px-2.5 py-1 bg-red-500 text-white rounded hover:bg-red-600 transition-colors flex-shrink-0">Deny</button>
            </div>
        `);
    } else if (perms.length === 2) {
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0">\uD83D\uDD10</span>
                <button onclick="toggleActionBarDetails('permission')"
                    class="text-sm text-gray-700 hover:text-gray-900 font-medium">${perms.length} permissions</button>
                <button onclick="handleBatchApproveAll()"
                    class="text-xs px-2.5 py-1 bg-green-500 text-white rounded hover:bg-green-600 transition-colors flex-shrink-0">Approve All (${perms.length})</button>
            </div>
        `);
    } else if (perms.length > 2) {
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0">\uD83D\uDD10</span>
                <button onclick="toggleActionBarDetails('permission')"
                    class="text-sm text-gray-700 hover:text-gray-900 font-medium">${perms.length} permissions</button>
                <button onclick="handleBatchApproveAll()"
                    class="text-xs px-2.5 py-1 bg-green-500 text-white rounded hover:bg-green-600 transition-colors flex-shrink-0">Approve All (${perms.length})</button>
            </div>
        `);
    }

    // Stalled segment
    if (stalled.length > 0) {
        const label = stalled.length === 1
            ? escapeHtml(stalled[0].agent_name) + ' stalled'
            : stalled.length + ' stalled';
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0">\u23F8\uFE0F</span>
                <button onclick="toggleActionBarDetails('stalled_agent')"
                    class="text-sm text-amber-700 hover:text-amber-900">${label}</button>
            </div>
        `);
    }

    // Blocked segment
    if (blocked.length > 0) {
        const label = blocked.length === 1
            ? 'Task #' + escapeHtml(blocked[0].id.replace('blocked:', '')) + ' blocked'
            : blocked.length + ' blocked tasks';
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0">\uD83D\uDEAB</span>
                <button onclick="toggleActionBarDetails('blocked_task')"
                    class="text-sm text-gray-600 hover:text-gray-800">${label}</button>
            </div>
        `);
    }

    // Auto-approval summary
    if (recentAutoApprovals.length > 0) {
        const toolNames = recentAutoApprovals.map(a => a.tool_name);
        const latest = recentAutoApprovals[0];
        const ago = timeAgo(latest.timestamp);
        segments.push(`
            <div class="flex items-center gap-2">
                <span class="text-sm flex-shrink-0 text-green-500">\u2713</span>
                <span class="text-sm text-green-700">${recentAutoApprovals.length} auto-approved</span>
                <span class="text-xs text-green-500">(${toolNames.join(', ')})</span>
                <span class="text-xs text-gray-400">${ago}</span>
            </div>
        `);
    }

    content.innerHTML = segments.join('<span class="text-gray-300">\u00B7</span>');

    // Re-render details if a category is expanded
    if (state.actionBarExpandedCategory) {
        const expandedItems = items.filter(i => i.category === state.actionBarExpandedCategory);
        if (expandedItems.length > 0) {
            details.classList.remove('hidden');
            details.innerHTML = expandedItems.map(renderActionBarDetailItem).join('');
        } else {
            details.classList.add('hidden');
            state.actionBarExpandedCategory = null;
        }
    }
}

function toggleActionBarDetails(category) {
    const details = $('action-bar-details');
    if (state.actionBarExpandedCategory === category) {
        details.classList.add('hidden');
        state.actionBarExpandedCategory = null;
        return;
    }
    state.actionBarExpandedCategory = category;
    details.classList.remove('hidden');

    const items = (state.currentActionQueue || []).filter(i => i.category === category);
    details.innerHTML = items.map(renderActionBarDetailItem).join('');
}

function renderActionBarDetailItem(item) {
    const duration = item.duration_seconds != null ? formatDuration(item.duration_seconds) : '';

    if (item.category === 'permission' && item.permission_data) {
        const pd = item.permission_data;
        const riskHtml = item.risk_level === 'medium'
            ? '<span class="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">Review</span>'
            : item.risk_level === 'low'
                ? '<span class="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">Low risk</span>'
                : '';
        return `
            <div class="flex items-center justify-between bg-gray-50 rounded border border-gray-200 px-3 py-2">
                <div class="flex items-center gap-2 min-w-0">
                    ${colorDot(item.agent_color, 'w-2 h-2')}
                    <span class="text-sm font-medium text-gray-700">${escapeHtml(item.agent_name)}</span>
                    <span class="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">${escapeHtml(pd.tool_name)}</span>
                    <span class="text-xs text-gray-500 truncate">${escapeHtml(truncate(item.detail, 60))}</span>
                    ${duration ? `<span class="text-xs text-gray-400">${duration}</span>` : ''}
                    ${riskHtml}
                </div>
                <div class="flex gap-2 flex-shrink-0">
                    <button onclick="handlePermission('approve', '${escapeHtml(item.agent_name)}', '${escapeHtml(pd.request_id)}', '${escapeHtml(pd.tool_use_id)}')"
                        class="text-xs px-2.5 py-1 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">Approve</button>
                    <button onclick="handlePermission('deny', '${escapeHtml(item.agent_name)}', '${escapeHtml(pd.request_id)}', '${escapeHtml(pd.tool_use_id)}')"
                        class="text-xs px-2.5 py-1 bg-red-500 text-white rounded hover:bg-red-600 transition-colors">Deny</button>
                </div>
            </div>
        `;
    }

    if (item.category === 'stalled_agent') {
        return `
            <div class="flex items-center justify-between bg-amber-50 rounded border border-amber-200 px-3 py-2">
                <div class="flex items-center gap-2 min-w-0">
                    ${colorDot(item.agent_color, 'w-2 h-2')}
                    <span class="text-sm font-medium text-amber-800">${escapeHtml(item.agent_name)}</span>
                    <span class="text-xs text-amber-600">${escapeHtml(item.detail)}</span>
                    ${duration ? `<span class="text-xs text-amber-500">${duration}</span>` : ''}
                </div>
            </div>
        `;
    }

    if (item.category === 'blocked_task') {
        return `
            <div class="flex items-center bg-gray-50 rounded border border-gray-200 px-3 py-2">
                <div class="flex items-center gap-2 min-w-0">
                    <span class="text-xs text-gray-500 font-medium">#${escapeHtml(item.id.replace('blocked:', ''))}</span>
                    <span class="text-sm text-gray-700">${escapeHtml(item.title)}</span>
                    <span class="text-xs text-gray-400">${escapeHtml(item.detail)}</span>
                </div>
            </div>
        `;
    }

    return '';
}

// ── (renderCompletionBar removed — merged into renderAgentSidebar) ──────────

// ── Rendering: Detail — Health Score Badge ────────────────────────────────────

const HEALTH_COLORS = {
    green: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300', ring: 'ring-green-500' },
    amber: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', ring: 'ring-amber-500' },
    red:   { bg: 'bg-red-100',   text: 'text-red-700',   border: 'border-red-300',   ring: 'ring-red-500' },
};

function renderHealthBadge(health) {
    const container = $('health-badge-container');
    const inlineContainer = $('health-breakdown-inline');

    if (!health || health.overall == null) {
        if (container) container.classList.add('hidden');
        if (inlineContainer) inlineContainer.classList.add('hidden');
        return;
    }

    const hc = HEALTH_COLORS[health.color] || HEALTH_COLORS.green;

    // Compact badge in the header
    if (container) {
        container.classList.remove('hidden');
        container.innerHTML = `
            <span class="inline-flex items-center justify-center w-8 h-8 rounded-full ${hc.bg} ${hc.text} ${hc.border} border text-sm font-bold">
                ${health.overall}
            </span>
            <span class="text-xs ${hc.text} font-medium">${escapeHtml(health.label)}</span>
        `;
    }

    // Inline breakdown section
    if (inlineContainer) {
        const DIM_NAMES = {
            permission_latency: 'Permission Latency',
            stall_ratio: 'Stall Ratio',
            blocked_ratio: 'Blocked Ratio',
            throughput: 'Throughput',
        };

        const dimensionRows = (health.dimensions || []).map(dim => {
            const barWidth = Math.max(0, Math.min(100, dim.score));
            const weightPct = Math.round(dim.weight * 100);
            const barColor = dim.score >= 80 ? 'bg-green-500' : dim.score >= 50 ? 'bg-amber-500' : 'bg-red-500';
            return `
                <div class="flex items-center gap-3 text-xs">
                    <span class="w-32 text-gray-600 font-medium">${escapeHtml(DIM_NAMES[dim.name] || dim.name)}</span>
                    <div class="flex-1 bg-gray-200 rounded-full h-2">
                        <div class="${barColor} h-2 rounded-full transition-all" style="width: ${barWidth}%"></div>
                    </div>
                    <span class="w-8 text-right text-gray-700 font-medium">${dim.score}</span>
                    <span class="w-10 text-gray-400">${weightPct}%</span>
                    <span class="text-gray-500 truncate max-w-[200px]">${escapeHtml(dim.explanation)}</span>
                </div>
            `;
        }).join('');

        inlineContainer.classList.remove('hidden');
        $('health-score-display').className = `inline-flex items-center justify-center w-9 h-9 rounded-full ${hc.bg} ${hc.text} ${hc.border} border text-sm font-bold`;
        $('health-score-display').textContent = health.overall;
        $('health-label-display').textContent = `${health.label} Health`;
        $('health-dimensions').innerHTML = dimensionRows;
    }
}

// ── Rendering: Detail — Agent Sidebar ────────────────────────────────────────

const AGENT_STATUS_CONFIG = {
    active:    { bg: 'bg-green-100', text: 'text-green-700', label: 'Active' },
    idle:      { bg: 'bg-gray-100',  text: 'text-gray-600',  label: 'Idle' },
    completed: { bg: 'bg-blue-100',  text: 'text-blue-700',  label: 'Completed' },
    stalled:   { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Stalled' },
};

function renderAgentSidebar(data, counts) {
    const summary = $('agent-summary');
    const list = $('agent-list');

    const agents = data?.agents || [];
    const completed = counts?.completed || 0;
    const total = counts?.total || 0;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Summary line + progress bar
    const barColor = pct === 100 ? 'bg-green-500' : pct > 0 ? 'bg-blue-500' : 'bg-gray-300';
    summary.innerHTML = `
        <div class="flex items-center justify-between mb-1.5">
            <span class="text-sm font-medium text-gray-700">Agents (${agents.length})</span>
            <span class="text-sm text-gray-500">${completed}/${total} tasks (${pct}%)</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-1.5">
            <div class="h-1.5 rounded-full transition-all duration-500 ${barColor}" style="width: ${pct}%"></div>
        </div>
    `;

    if (agents.length === 0) {
        list.innerHTML = '<p class="text-xs text-gray-400">No agents yet</p>';
        return;
    }

    list.innerHTML = agents.map(agent => {
        const stalledBorder = agent.is_stalled ? 'border-amber-300 bg-amber-50/50' : 'border-gray-100 bg-gray-50/50';
        const totalTasks = agent.tasks_pending + agent.tasks_in_progress + agent.tasks_completed;
        const modelShort = (agent.model || '').replace('claude-', '').split('-')[0] || '';
        const sc = AGENT_STATUS_CONFIG[agent.agent_status] || AGENT_STATUS_CONFIG.active;

        const stallLine = agent.is_stalled
            ? `<div class="text-xs text-amber-600 font-medium mt-1">Stalled ${formatDuration((agent.minutes_since_last_activity || 0) * 60)} (>${state.stallThresholdMinutes}m)</div>`
            : '';

        const showRemove = agent.agent_status === 'completed' || agent.agent_status === 'stalled';
        const removeBtn = showRemove
            ? `<button onclick="handleRemoveMember('${escapeHtml(agent.name)}')"
                 class="text-xs text-red-500 hover:text-red-700 hover:underline">Remove</button>`
            : '';

        return `
            <div class="rounded border ${stalledBorder} px-3 py-2">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5 min-w-0">
                        ${colorDot(agent.color, 'w-2 h-2')}
                        <span class="text-sm font-medium text-gray-800 truncate">${escapeHtml(agent.name)}</span>
                        <span class="text-xs ${sc.bg} ${sc.text} px-1.5 py-0.5 rounded font-medium flex-shrink-0">${sc.label}</span>
                    </div>
                    <div class="flex items-center gap-1.5 flex-shrink-0 ml-2">
                        <span class="text-xs text-gray-500">${agent.tasks_completed}/${totalTasks}</span>
                        ${modelShort ? `<span class="text-xs bg-blue-50 text-blue-600 px-1 py-0.5 rounded">${escapeHtml(modelShort)}</span>` : ''}
                    </div>
                </div>
                ${stallLine}
                ${removeBtn ? `<div class="mt-1">${removeBtn}</div>` : ''}
            </div>
        `;
    }).join('');
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

function renderCompactTasks(tasksData) {
    const list = $('task-list');
    const empty = $('tasks-empty');

    if (!tasksData || !tasksData.tasks || tasksData.tasks.length === 0) {
        if (list) list.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    populateTaskFilters(tasksData.tasks);
    const filteredTasks = applyTaskFilters(tasksData.tasks);
    if (filteredTasks.length === 0) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        empty.textContent = 'No tasks match current filters';
        return;
    }

    empty.classList.add('hidden');
    empty.textContent = 'No tasks yet';

    // Group by status: pending first, then in_progress, then completed
    const groups = { pending: [], in_progress: [], completed: [] };
    filteredTasks.forEach(t => {
        if (groups[t.status]) groups[t.status].push(t);
    });

    const stallSeconds = state.stallThresholdMinutes * 60;

    const STATUS_ICONS = {
        pending: '<span class="inline-block w-2 h-2 rounded-full bg-gray-300 flex-shrink-0"></span>',
        in_progress: '<span class="inline-block w-2 h-2 rounded-full bg-blue-500 flex-shrink-0"></span>',
        completed: '<svg class="w-3 h-3 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>',
    };

    function renderRow(t) {
        const icon = STATUS_ICONS[t.status] || STATUS_ICONS.pending;
        const isStale = t.status_duration_seconds != null && t.status_duration_seconds > stallSeconds && t.status !== 'completed';
        const durationColor = isStale ? 'text-amber-600 font-medium' : 'text-gray-400';
        const durationText = formatDuration(t.status_duration_seconds);

        const ownerDot = t.owner
            ? colorDot((state.teamMembers || []).find(m => m.name === t.owner)?.color, 'w-1.5 h-1.5')
            : '';

        const blockedBadge = t.blocked_by && t.blocked_by.length > 0
            ? `<span class="text-xs text-red-500 flex-shrink-0">blocked</span>`
            : '';

        return `
            <div class="compact-task-row flex items-center gap-2 px-2 py-1.5 rounded">
                ${icon}
                <span class="text-xs text-gray-400 flex-shrink-0">#${escapeHtml(t.id)}</span>
                <span class="text-sm text-gray-700 truncate flex-1">${escapeHtml(truncate(t.subject, 50))}</span>
                ${ownerDot}
                ${blockedBadge}
                <span class="text-xs ${durationColor} flex-shrink-0">${durationText}</span>
            </div>
        `;
    }

    let html = '';

    // Pending tasks
    if (groups.pending.length > 0) {
        html += `<div class="text-xs font-medium text-gray-500 uppercase tracking-wide px-2 pt-1 pb-0.5">Pending (${groups.pending.length})</div>`;
        html += groups.pending.map(renderRow).join('');
    }

    // In-progress tasks
    if (groups.in_progress.length > 0) {
        html += `<div class="text-xs font-medium text-blue-600 uppercase tracking-wide px-2 pt-2 pb-0.5">In Progress (${groups.in_progress.length})</div>`;
        html += groups.in_progress.map(renderRow).join('');
    }

    // Completed tasks — behind toggle
    if (groups.completed.length > 0) {
        if (state.showCompletedTasks) {
            html += `<div class="text-xs font-medium text-green-600 uppercase tracking-wide px-2 pt-2 pb-0.5 flex items-center justify-between">
                <span>Completed (${groups.completed.length})</span>
                <button onclick="toggleCompletedTasks()" class="text-xs text-gray-400 hover:text-gray-600 normal-case tracking-normal font-normal">Hide</button>
            </div>`;
            html += groups.completed.map(renderRow).join('');
        } else {
            html += `<button onclick="toggleCompletedTasks()" class="text-xs text-gray-400 hover:text-gray-600 px-2 pt-2">Show ${groups.completed.length} completed</button>`;
        }
    }

    list.innerHTML = html;
}

function toggleCompletedTasks() {
    state.showCompletedTasks = !state.showCompletedTasks;
    poll();
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
        $('new-messages-indicator')?.classList.add('hidden');
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

    // Save scroll position before re-render
    const prevScrollTop = feed.scrollTop;
    const wasScrolledUp = feed.scrollTop > 10;

    feed.innerHTML = sorted.map(renderMessageCard).join('');
    applySystemMessageVisibility();

    // Restore scroll position if user was scrolled up
    if (wasScrolledUp) {
        feed.scrollTop = prevScrollTop;
    }

    updateNewMessagesIndicator(feed, wasScrolledUp, sorted.length);
}

function isSystemMessage(msg) {
    return SYSTEM_MESSAGE_TYPES.has(msg.message_type);
}

function renderMessageCard(msg) {
    if (isSystemMessage(msg)) {
        return renderSystemMessage(msg);
    }
    return renderContentMessage(msg);
}

function renderContentMessage(msg) {
    const c = getColor(msg.color);
    const bodyHtml = renderMarkdown(msg.text);

    return `
        <div class="bg-white rounded-lg border border-gray-200 p-4 border-l-4 ${c.border}">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-1.5">
                    ${colorDot(msg.color, 'w-2 h-2')}
                    <span class="text-xs font-medium text-gray-600">${escapeHtml(msg.from_agent)}</span>
                    <span class="text-xs text-gray-300">&rarr;</span>
                    <span class="text-xs text-gray-400">${escapeHtml(msg.target_agent || '')}</span>
                </div>
                <span class="text-xs text-gray-400">${timeAgo(msg.timestamp)}</span>
            </div>
            <div class="msg-markdown text-sm text-gray-700">${bodyHtml}</div>
        </div>
    `;
}

function renderSystemMessage(msg) {
    const icon = SYSTEM_MSG_ICONS[msg.message_type] || '\u2022';

    let summary = '';
    if (msg.message_type === 'permission_request' && msg.parsed_content) {
        summary = `${msg.parsed_content.tool_name || 'permission'}: ${truncate(msg.parsed_content.description || '', 60)}`;
    } else if (msg.message_type === 'permission_response' && msg.parsed_content) {
        summary = msg.parsed_content.approved ? 'approved' : 'denied';
    } else if (msg.message_type === 'shutdown_request') {
        summary = 'shutdown requested';
    } else if (msg.message_type === 'shutdown_response') {
        summary = 'shutdown response';
    } else if (msg.message_type === 'idle') {
        summary = 'went idle';
    } else {
        summary = msg.message_type.replace(/_/g, ' ');
    }

    return `
        <div class="system-msg flex items-center gap-2 px-3 py-1 text-xs text-gray-400">
            <span>${icon}</span>
            ${colorDot(msg.color, 'w-1.5 h-1.5')}
            <span class="text-gray-500">${escapeHtml(msg.from_agent)}</span>
            <span>${escapeHtml(summary)}</span>
            <span class="ml-auto">${timeAgo(msg.timestamp)}</span>
        </div>
    `;
}

function applySystemMessageVisibility() {
    const systemMsgs = document.querySelectorAll('#message-feed .system-msg');
    systemMsgs.forEach(el => {
        el.style.display = state.showSystemMessages ? '' : 'none';
    });
}

function updateSystemToggle() {
    const btn = $('toggle-system-msgs');
    if (btn) btn.checked = !!state.showSystemMessages;
}

function updateNewMessagesIndicator(feed, wasScrolledUp, currentCount) {
    const indicator = $('new-messages-indicator');
    if (!indicator) return;

    if (wasScrolledUp && currentCount > state.lastSeenMessageCount) {
        const newCount = currentCount - state.lastSeenMessageCount;
        $('new-messages-count').textContent = newCount;
        indicator.classList.remove('hidden');
    } else if (!wasScrolledUp) {
        indicator.classList.add('hidden');
        state.lastSeenMessageCount = currentCount;
    }
}

function scrollToLatestMessage() {
    const feed = $('message-feed');
    feed.scrollTop = 0;
    $('new-messages-indicator')?.classList.add('hidden');
    state.lastSeenMessageCount = feed.children.length;
}

function renderGroupedMessages(data) {
    const feed = $('message-feed');
    const empty = $('messages-empty');

    if (!data || !data.groups || data.groups.length === 0) {
        feed.innerHTML = '';
        empty.textContent = 'No messages match current filters';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');

    // Collect all messages across groups for filter population
    const allMessages = data.groups.flatMap(g => g.messages);
    populateMessageFilters(allMessages);

    const groupsHtml = data.groups.map(group => {
        const [agentA, agentB] = group.pair;
        const filtered = applyMessageFilters(group.messages);
        if (filtered.length === 0) return '';

        const sorted = [...filtered].reverse();
        const messagesHtml = sorted.map(renderMessageCard).join('');

        return `
            <div class="mb-4">
                <div class="flex items-center gap-2 mb-2 pb-1 border-b border-gray-100">
                    ${colorDot((state.teamMembers || []).find(m => m.name === agentA)?.color, 'w-2.5 h-2.5')}
                    <span class="text-sm font-medium text-gray-700">${escapeHtml(agentA)}</span>
                    <span class="text-xs text-gray-400">&harr;</span>
                    ${colorDot((state.teamMembers || []).find(m => m.name === agentB)?.color, 'w-2.5 h-2.5')}
                    <span class="text-sm font-medium text-gray-700">${escapeHtml(agentB)}</span>
                    <span class="text-xs text-gray-400">(${filtered.length} message${filtered.length !== 1 ? 's' : ''})</span>
                </div>
                <div class="space-y-2 pl-2">
                    ${messagesHtml}
                </div>
            </div>
        `;
    }).filter(Boolean).join('');

    if (groupsHtml === '') {
        feed.innerHTML = '';
        empty.textContent = 'No messages match current filters';
        empty.classList.remove('hidden');
    } else {
        feed.innerHTML = groupsHtml;
        applySystemMessageVisibility();
    }
}

function toggleUnresolved(e) {
    if (e && e.target) {
        state.messagesUnresolved = e.target.checked;
    } else {
        state.messagesUnresolved = !state.messagesUnresolved;
    }
    updateUnresolvedToggle();
    poll();
}

function toggleGroupByPair(e) {
    if (e && e.target) {
        state.messagesGroupByPair = e.target.checked;
    } else {
        state.messagesGroupByPair = !state.messagesGroupByPair;
    }
    updateGroupByToggle();
    poll();
}

function updateUnresolvedToggle() {
    const btn = $('toggle-unresolved');
    if (btn) btn.checked = !!state.messagesUnresolved;
}

function updateGroupByToggle() {
    const btn = $('toggle-group-pair');
    if (btn) btn.checked = !!state.messagesGroupByPair;
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
