// ── API Layer ────────────────────────────────────────────────────────────────

const api = {
    _jsonHeaders() {
        return { 'Content-Type': 'application/json' };
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
    getMessages(name, { unresolved = false, groupBy = null } = {}) {
        const params = new URLSearchParams();
        if (unresolved) params.set('unresolved', 'true');
        if (groupBy) params.set('group_by', groupBy);
        const qs = params.toString();
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/messages${qs ? '?' + qs : ''}`, undefined, true);
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
    batchPermissions(name, actions) {
        return this._fetch(`/api/teams/${encodeURIComponent(name)}/permissions/batch`, {
            method: 'POST',
            headers: this._jsonHeaders(),
            body: JSON.stringify({ actions }),
        });
    },
    removeMember(teamName, agentName) {
        return this._fetch(`/api/teams/${encodeURIComponent(teamName)}/members/${encodeURIComponent(agentName)}/remove`, {
            method: 'POST',
            headers: this._jsonHeaders(),
        });
    },
    getSettings() {
        return this._fetch('/api/settings', undefined, true);
    },
    updateSettings(data) {
        return this._fetch('/api/settings', {
            method: 'PUT',
            headers: this._jsonHeaders(),
            body: JSON.stringify(data),
        });
    },
};
