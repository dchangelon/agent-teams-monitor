// ── Event Handlers ───────────────────────────────────────────────────────────

async function handlePermission(action, agentName, requestId, toolUseId) {
    const name = state.currentTeam;
    if (!name) return;

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

async function handleBatchApproveAll() {
    const name = state.currentTeam;
    if (!name) return;

    const btn = $('approve-all-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Approving...';
    }

    const actions = (state.currentActionQueue || [])
        .filter(item => item.category === 'permission' && item.permission_data)
        .map(item => ({
            agent_name: item.agent_name,
            request_id: item.permission_data.request_id,
            tool_use_id: item.permission_data.tool_use_id,
            action: 'approve',
        }));

    if (actions.length === 0) {
        showToast('No permissions to approve', 'info');
        return;
    }

    const result = await api.batchPermissions(name, actions);
    if (result) {
        showToast(`${result.succeeded} permission${result.succeeded !== 1 ? 's' : ''} approved`, 'success');
    }
    poll();
}

async function handleRemoveMember(agentName) {
    const name = state.currentTeam;
    if (!name) return;

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

    const result = await api.sendMessage(state.currentTeam, agent, text);
    if (result) {
        showToast(`Message sent to ${agent}`, 'success');
    }
    textInput.value = '';
    poll();
}
