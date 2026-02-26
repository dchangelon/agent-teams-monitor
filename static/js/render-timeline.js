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
