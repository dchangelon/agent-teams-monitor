// ── Navigation ───────────────────────────────────────────────────────────────

function navigateToTeam(teamName) {
    state.currentView = 'detail';
    state.currentTeam = teamName;
    state.actionBarExpandedCategory = null;
    state.expandedTaskDescriptions = {};
    state.knownPermissionIds = new Set();

    $('overview-view').classList.add('hidden');
    $('detail-view').classList.remove('hidden');
    $('detail-view').classList.add('view-fade-in');
    $('team-name-header').textContent = teamName;

    poll();
}

function navigateToOverview() {
    state.currentView = 'overview';
    state.currentTeam = null;
    state.knownPermissionIds = new Set();

    $('detail-view').classList.add('hidden');
    $('overview-view').classList.remove('hidden');
    $('overview-view').classList.add('view-fade-in');

    poll();
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
            state.currentActionQueue = snapshot.action_queue || [];
            renderActionBar(state.currentActionQueue, snapshot.recent_auto_approvals || []);
            renderAgentSidebar({ agents: snapshot.activity || [] }, snapshot.counts || null);
            state.stallThresholdMinutes = snapshot.monitor_config?.stall_threshold_minutes || 10;
            $('team-description-header').textContent = snapshot.team?.description || '';
            state.teamMembers = snapshot.team?.members || [];
            renderSendForm(state.teamMembers);
            notifyNewPermissions(snapshot.pending_permissions || []);
            renderHealthBadge(snapshot.health || null);
        }

        // Fetch all section data in parallel (single-page layout)
        // Skip agent-timeline API call when timeline is collapsed
        const [tasksData, taskTimelineData, agentTimelineData, messagesData] = await Promise.all([
            api.getTasks(name),
            api.getTimeline(name),
            state.timelineExpanded ? api.getAgentTimeline(name) : Promise.resolve(null),
            api.getMessages(name, {
                unresolved: state.messagesUnresolved,
                groupBy: state.messagesGroupByPair ? 'pair' : null,
            }),
        ]);

        if (tasksData) {
            renderCompactTasks(tasksData);
        }
        if (taskTimelineData) renderTaskTimeline(taskTimelineData);
        if (agentTimelineData) renderSwimLanes(agentTimelineData);
        if (messagesData) {
            if (state.messagesGroupByPair && messagesData.groups) {
                renderGroupedMessages(messagesData);
            } else {
                renderMessages(messagesData);
            }
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

    // Timeline collapse/expand
    $('timeline-toggle').addEventListener('click', () => {
        state.timelineExpanded = !state.timelineExpanded;
        const content = $('timeline-content');
        const chevron = $('timeline-chevron');
        if (state.timelineExpanded) {
            content.classList.remove('hidden');
            chevron.classList.add('rotate-180');
            poll(); // Fetch timeline data when expanding
        } else {
            content.classList.add('hidden');
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

    // Message toggle buttons
    $('toggle-unresolved').addEventListener('change', toggleUnresolved);
    $('toggle-group-pair').addEventListener('change', toggleGroupByPair);
    $('toggle-system-msgs').addEventListener('change', (e) => {
        state.showSystemMessages = e.target.checked;
        updateSystemToggle();
        applySystemMessageVisibility();
    });

    // Smart polling: pause when tab is hidden, resume when visible
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopPolling();
        } else if (state.polling) {
            startPolling();
        }
    });

    // Settings dropdown toggle
    $('settings-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        $('settings-dropdown').classList.toggle('hidden');
    });
    document.addEventListener('click', (e) => {
        if (!$('settings-wrapper').contains(e.target)) {
            $('settings-dropdown').classList.add('hidden');
        }
    });

    // Notification toggle
    const notifToggle = $('toggle-notifications');
    notifToggle.checked = state.notificationsEnabled;
    notifToggle.addEventListener('change', () => {
        state.notificationsEnabled = notifToggle.checked;
        localStorage.setItem('agent_monitor_notifications', notifToggle.checked);
        if (notifToggle.checked && 'Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    });

    // Sound toggle
    const soundToggle = $('toggle-sound');
    soundToggle.checked = state.soundEnabled;
    soundToggle.addEventListener('change', () => {
        state.soundEnabled = soundToggle.checked;
        localStorage.setItem('agent_monitor_sound', soundToggle.checked);
    });

    // Auto-approval settings — load from server
    loadAutoApprovalSettings();

    $('toggle-auto-approve').addEventListener('change', () => {
        saveAutoApprovalSettings();
    });

    document.querySelectorAll('.auto-approve-tool').forEach(cb => {
        cb.addEventListener('change', () => {
            saveAutoApprovalSettings();
        });
    });

    // Start polling
    startPolling();
}

// ── Auto-Approval Settings ──────────────────────────────────────────────────

async function loadAutoApprovalSettings() {
    const data = await api.getSettings();
    if (!data) return;

    $('toggle-auto-approve').checked = data.auto_approve_enabled;
    const enabledTools = new Set(data.auto_approve_tools || []);

    document.querySelectorAll('.auto-approve-tool').forEach(cb => {
        cb.checked = enabledTools.has(cb.value);
    });
}

async function saveAutoApprovalSettings() {
    const enabled = $('toggle-auto-approve').checked;
    const tools = [];
    document.querySelectorAll('.auto-approve-tool').forEach(cb => {
        if (cb.checked) tools.push(cb.value);
    });

    const result = await api.updateSettings({
        auto_approve_enabled: enabled,
        auto_approve_tools: tools,
    });

    if (result) {
        showToast('Auto-approval settings saved', 'success');
    }
}

// Boot
document.addEventListener('DOMContentLoaded', init);
