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

        const healthBadge = team.health_score != null ? (() => {
            const hColors = {
                green: 'bg-green-100 text-green-700 border-green-300',
                amber: 'bg-amber-100 text-amber-700 border-amber-300',
                red:   'bg-red-100 text-red-700 border-red-300',
            };
            const hc = hColors[team.health_color] || hColors.green;
            return `<span class="absolute top-2 right-2 inline-flex items-center justify-center w-7 h-7 rounded-full ${hc} border text-xs font-bold" title="Health: ${team.health_score}">${team.health_score}</span>`;
        })() : '';

        return `
            <div class="relative bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
                 onclick="navigateToTeam('${escapeHtml(team.name)}')">
                ${unreadBadge}
                ${healthBadge}
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
