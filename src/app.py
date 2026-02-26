import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Optional, Union

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    SETTINGS_PATH,
    STALL_THRESHOLD_MINUTES,
    STATIC_DIR,
    TEMPLATES_DIR,
    TIMELINE_MAX_EVENTS,
    WRITE_API_KEY,
)
from .file_reader import TeamFileReader
from .message_writer import ConfigWriter, InboxWriter
from .models import (
    ActionQueueResponse,
    ActionResponse,
    ActivityResponse,
    AgentActivityResponse,
    AgentLifecycleEvent,
    AgentTimelineEntry,
    AgentTimelineResponse,
    AlertsResponse,
    AutoApprovalLogEntry,
    AutoApprovalLogResponse,
    AutoApprovalSettingsResponse,
    BatchPermissionRequest,
    BatchPermissionResponse,
    GroupedMessagesResponse,
    HealthScoreResponse,
    InboxMessageResponse,
    MessageGroupResponse,
    MessagesResponse,
    MonitorConfigResponse,
    PermissionActionRequest,
    PermissionAlertResponse,
    SendMessageRequest,
    TaskCountsResponse,
    TaskResponse,
    TasksResponse,
    TeamConfigResponse,
    TeamDetailResponse,
    TeamMemberResponse,
    TeamSummaryResponse,
    TeamsListResponse,
    DetailSnapshotResponse,
    TimelineEventResponse,
    TimelineResponse,
    UpdateAutoApprovalRequest,
)
from .services.action_queue_service import build_action_queue
from .services.auto_approval_service import AutoApprovalService
from .services.health_score_service import compute_health_score
from .services.settings_service import SettingsService
from .timeline import TimelineTracker

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _ms_to_iso(ms: int) -> str:
    """Convert Unix milliseconds timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _member_to_response(member, truncate_prompt: bool = True) -> TeamMemberResponse:
    """Convert internal TeamMember dataclass to API response model."""
    prompt = member.prompt
    if truncate_prompt and prompt and len(prompt) > 200:
        prompt = prompt[:200]
    return TeamMemberResponse(
        agent_id=member.agent_id,
        name=member.name,
        agent_type=member.agent_type,
        model=member.model,
        joined_at=member.joined_at,
        cwd=member.cwd,
        color=member.color,
        prompt=prompt,
    )


def _message_to_response(msg) -> InboxMessageResponse:
    """Convert internal InboxMessage dataclass to API response model."""
    return InboxMessageResponse(
        from_agent=msg.from_agent,
        text=msg.text,
        timestamp=msg.timestamp,
        color=msg.color,
        read=msg.read,
        message_type=msg.message_type,
        parsed_content=msg.parsed_content,
        target_agent=msg.target_agent,
    )


def extract_pending_permissions(messages) -> list[PermissionAlertResponse]:
    """Scan messages for unresolved permission_request types.

    A request is resolved if a permission_response with the same request_id exists.
    """
    # Pass 1: collect request_ids that already have a response
    resolved_ids: set[str] = set()
    for msg in messages:
        if msg.message_type == "permission_response" and msg.parsed_content:
            rid = msg.parsed_content.get("request_id", "")
            if rid:
                resolved_ids.add(rid)

    # Pass 2: only return unresolved requests
    permissions = []
    for msg in messages:
        if msg.message_type == "permission_request" and msg.parsed_content:
            pc = msg.parsed_content
            request_id = pc.get("request_id", "")
            if request_id in resolved_ids:
                continue
            permissions.append(PermissionAlertResponse(
                agent_name=msg.from_agent,
                agent_color=msg.color,
                tool_name=pc.get("tool_name", ""),
                description=pc.get("description", ""),
                request_id=request_id,
                tool_use_id=pc.get("tool_use_id", ""),
                timestamp=msg.timestamp,
            ))
    return permissions


def _filter_unresolved_messages(messages) -> list:
    """Return only unresolved permission_request and shutdown_request messages.

    A permission is resolved if a permission_response with the same request_id
    exists. A shutdown is resolved if a shutdown_response with the same
    requestId/request_id exists.
    """
    # Pass 1: collect resolved permission IDs
    resolved_perm_ids: set[str] = set()
    for msg in messages:
        if msg.message_type == "permission_response" and msg.parsed_content:
            rid = msg.parsed_content.get("request_id", "")
            if rid:
                resolved_perm_ids.add(rid)

    # Pass 1b: collect resolved shutdown IDs
    resolved_shutdown_ids: set[str] = set()
    for msg in messages:
        if msg.message_type == "shutdown_response" and msg.parsed_content:
            rid = (
                msg.parsed_content.get("requestId", "")
                or msg.parsed_content.get("request_id", "")
            )
            if rid:
                resolved_shutdown_ids.add(rid)

    # Pass 2: return unresolved items only
    filtered = []
    for msg in messages:
        if msg.message_type == "permission_request" and msg.parsed_content:
            rid = msg.parsed_content.get("request_id", "")
            if rid not in resolved_perm_ids:
                filtered.append(msg)
        elif msg.message_type == "shutdown_request" and msg.parsed_content:
            rid = (
                msg.parsed_content.get("requestId", "")
                or msg.parsed_content.get("request_id", "")
            )
            if not rid or rid not in resolved_shutdown_ids:
                filtered.append(msg)
    return filtered


def _canonicalize_pair(agent_a: str, agent_b: str) -> tuple:
    """Return a canonical (alphabetically sorted) agent pair."""
    return tuple(sorted([agent_a, agent_b]))


def _validate_identifier(identifier: str, field_name: str) -> str:
    """Validate team/agent route identifiers to prevent malformed file paths."""
    if not identifier or not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}; allowed characters are letters, numbers, '_' and '-'.",
        )
    return identifier


def compute_agent_activity(
    team_name: str,
    reader: TeamFileReader,
    tracker: TimelineTracker,
    config=None,
    tasks=None,
    all_messages=None,
) -> list[AgentActivityResponse]:
    """Compute per-agent activity summary from tasks + messages + tracker."""
    config = config or reader.get_team_config(team_name)
    if not config:
        return []

    tasks = tasks if tasks is not None else reader.get_tasks(team_name)
    all_messages = (
        all_messages if all_messages is not None
        else reader.get_all_messages(team_name)
    )
    now = datetime.now(timezone.utc)

    # Pre-compute agents that received a shutdown_request
    shutdown_agents: set[str] = set()
    for msg in all_messages:
        if msg.message_type == "shutdown_request" and msg.target_agent:
            shutdown_agents.add(msg.target_agent)

    agents = []
    for member in config.members:
        name = member.name

        # Count tasks by status for this owner
        tasks_pending = sum(1 for t in tasks if t.owner == name and t.status == "pending")
        tasks_in_progress = sum(1 for t in tasks if t.owner == name and t.status == "in_progress")
        tasks_completed = sum(1 for t in tasks if t.owner == name and t.status == "completed")

        # Count messages sent/received
        messages_sent = sum(1 for m in all_messages if m.from_agent == name)
        messages_received = sum(1 for m in all_messages if m.target_agent == name)

        # Find last message timestamp (sent or received)
        agent_msg_timestamps = [
            m.timestamp for m in all_messages
            if m.from_agent == name or m.target_agent == name
        ]
        last_message_at = max(agent_msg_timestamps) if agent_msg_timestamps else None

        # Get last task event from tracker
        last_task_activity = tracker.get_last_activity_time(team_name, name)

        # Determine most recent activity overall
        latest_activity: Optional[str] = None
        if last_message_at and last_task_activity:
            latest_activity = max(last_message_at, last_task_activity)
        elif last_message_at:
            latest_activity = last_message_at
        elif last_task_activity:
            latest_activity = last_task_activity

        # Compute minutes since last activity
        minutes_since: Optional[int] = None
        is_stalled = False
        if latest_activity:
            delta = now - datetime.fromisoformat(latest_activity)
            minutes_since = int(delta.total_seconds() / 60)
            is_stalled = minutes_since > STALL_THRESHOLD_MINUTES

        # Derive agent status from signals
        has_pending_work = tasks_pending > 0 or tasks_in_progress > 0
        has_shutdown = name in shutdown_agents
        if has_shutdown and not has_pending_work:
            agent_status = "completed"
        elif has_shutdown and has_pending_work:
            agent_status = "stalled"
        elif is_stalled and not has_pending_work:
            agent_status = "completed"
        elif is_stalled and has_pending_work:
            agent_status = "stalled"
        elif not has_pending_work and tasks_completed > 0:
            agent_status = "idle"
        else:
            agent_status = "active"

        agents.append(AgentActivityResponse(
            name=name,
            color=member.color,
            agent_type=member.agent_type,
            model=member.model,
            tasks_pending=tasks_pending,
            tasks_in_progress=tasks_in_progress,
            tasks_completed=tasks_completed,
            messages_sent=messages_sent,
            messages_received=messages_received,
            last_message_at=last_message_at,
            minutes_since_last_activity=minutes_since,
            is_stalled=is_stalled,
            agent_status=agent_status,
        ))

    return agents


def build_agent_timeline(
    team_name: str,
    reader: TeamFileReader,
    tracker: TimelineTracker,
) -> Optional[AgentTimelineResponse]:
    """Assemble per-agent lifecycle for swim lane chart."""
    config = reader.get_team_config(team_name)
    if not config:
        return None

    all_messages = reader.get_all_messages(team_name)
    timeline_events = tracker.get_events(team_name, limit=500)

    agent_entries = []
    for member in config.members:
        name = member.name
        joined_at_iso = _ms_to_iso(member.joined_at)

        events: list[AgentLifecycleEvent] = []

        # Join event
        events.append(AgentLifecycleEvent(
            timestamp=joined_at_iso,
            event_type="joined",
            description="Joined team",
        ))

        # Message events
        for msg in all_messages:
            if msg.from_agent == name:
                desc = f"Sent message to {msg.target_agent}"
                if msg.message_type == "permission_request" and msg.parsed_content:
                    desc = f"Sent permission request for {msg.parsed_content.get('tool_name', 'unknown')}"
                elif msg.message_type == "shutdown_request":
                    desc = "Sent shutdown request"
                events.append(AgentLifecycleEvent(
                    timestamp=msg.timestamp,
                    event_type="message_sent",
                    description=desc,
                    related_agent=msg.target_agent,
                ))
            elif msg.target_agent == name:
                desc = f"Received message from {msg.from_agent}"
                if msg.message_type == "permission_request" and msg.parsed_content:
                    desc = f"Received permission request for {msg.parsed_content.get('tool_name', 'unknown')}"
                events.append(AgentLifecycleEvent(
                    timestamp=msg.timestamp,
                    event_type="message_received",
                    description=desc,
                    related_agent=msg.from_agent,
                ))

        # Task events from tracker
        for te in timeline_events:
            if te.owner == name:
                if te.new_status == "in_progress":
                    events.append(AgentLifecycleEvent(
                        timestamp=te.timestamp,
                        event_type="task_started",
                        description=f"Started task #{te.task_id} ({te.task_subject})",
                    ))
                elif te.new_status == "completed":
                    events.append(AgentLifecycleEvent(
                        timestamp=te.timestamp,
                        event_type="task_completed",
                        description=f"Completed task #{te.task_id} ({te.task_subject})",
                    ))

        # Detect shutdown from messages
        shutdown_at = None
        for msg in all_messages:
            if msg.message_type == "shutdown_request" and msg.target_agent == name:
                shutdown_at = msg.timestamp
                events.append(AgentLifecycleEvent(
                    timestamp=msg.timestamp,
                    event_type="shutdown_requested",
                    description=f"Shutdown requested by {msg.from_agent}",
                    related_agent=msg.from_agent,
                ))

        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)

        agent_entries.append(AgentTimelineEntry(
            name=name,
            agent_type=member.agent_type,
            color=member.color,
            joined_at=joined_at_iso,
            shutdown_at=shutdown_at,
            events=events,
        ))

    # Sort agents by joined_at
    agent_entries.sort(key=lambda a: a.joined_at)

    return AgentTimelineResponse(
        team_name=config.name,
        created_at=_ms_to_iso(config.created_at),
        agents=agent_entries,
    )


def create_app(
    teams_dir: Optional[Path] = None,
    tasks_dir: Optional[Path] = None,
    write_api_key: Optional[str] = None,
    settings_path: Optional[Path] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Accepts optional path overrides for testing.
    """
    reader = TeamFileReader(teams_base=teams_dir, tasks_base=tasks_dir)
    writer = InboxWriter(teams_base=teams_dir)
    config_writer = ConfigWriter(teams_base=teams_dir)
    tracker = TimelineTracker(max_events=TIMELINE_MAX_EVENTS)
    settings_service = SettingsService(
        settings_path=settings_path or SETTINGS_PATH
    )
    auto_approval = AutoApprovalService(
        settings_service=settings_service,
        writer=writer,
    )

    _logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Start background auto-approval loop on startup, cancel on shutdown."""
        async def _auto_approval_loop():
            while True:
                try:
                    settings = settings_service.get()
                    if settings.auto_approve_enabled:
                        team_names = reader.list_teams()
                        for team_name in team_names:
                            all_messages = reader.get_all_messages(team_name)
                            pending = extract_pending_permissions(all_messages)
                            if pending:
                                auto_approval.process_permissions(
                                    team_name, pending
                                )
                except Exception:
                    _logger.exception("Auto-approval loop error")
                await asyncio.sleep(3)

        task = asyncio.create_task(_auto_approval_loop())
        yield
        task.cancel()

    app = FastAPI(title="Agent Teams Monitor", lifespan=lifespan)
    effective_write_api_key = (
        write_api_key if write_api_key is not None else WRITE_API_KEY
    )

    def require_write_access(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
        if effective_write_api_key and x_api_key != effective_write_api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Mount static files (only if directory exists)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── Dashboard ────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html_path = TEMPLATES_DIR / "dashboard.html"
        if not html_path.exists():
            return HTMLResponse("<h1>Agent Teams Monitor</h1><p>Dashboard coming soon.</p>")
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    # ── Core GET endpoints ───────────────────────────────────────────────

    @app.get("/api/teams", response_model=TeamsListResponse)
    def list_teams():
        team_names = reader.list_teams()
        summaries = []
        for name in team_names:
            config = reader.get_team_config(name)
            if config is None:
                continue

            tasks = reader.get_tasks(name)
            all_messages = reader.get_all_messages(name)
            has_unread = any(not m.read for m in all_messages)

            task_counts = {"pending": 0, "in_progress": 0, "completed": 0}
            for t in tasks:
                if t.status in task_counts:
                    task_counts[t.status] += 1

            tracker.poll(name, tasks)
            activity = compute_agent_activity(
                name, reader, tracker,
                config=config, tasks=tasks, all_messages=all_messages,
            )
            pending_permissions = extract_pending_permissions(all_messages)
            health = compute_health_score(
                pending_permissions=pending_permissions,
                activity=activity,
                tasks=tasks,
                counts=task_counts,
            )

            summaries.append(TeamSummaryResponse(
                name=config.name,
                description=config.description,
                created_at=config.created_at,
                member_count=len(config.members),
                task_counts=task_counts,
                total_tasks=len(tasks),
                has_unread_messages=has_unread,
                members=[_member_to_response(m) for m in config.members],
                health_score=health.overall,
                health_color=health.color,
            ))
        return TeamsListResponse(teams=summaries)

    @app.get("/api/teams/{name}", response_model=TeamDetailResponse)
    def get_team(name: str):
        _validate_identifier(name, "team name")
        config = reader.get_team_config(name)
        if config is None:
            raise HTTPException(status_code=404, detail="Team not found")
        return TeamDetailResponse(
            team=TeamConfigResponse(
                name=config.name,
                description=config.description,
                created_at=config.created_at,
                lead_agent_id=config.lead_agent_id,
                members=[_member_to_response(m) for m in config.members],
            )
        )

    @app.get("/api/teams/{name}/tasks", response_model=TasksResponse)
    def get_tasks(name: str):
        _validate_identifier(name, "team name")
        tasks = reader.get_tasks(name)
        tracker.poll(name, tasks)

        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        task_responses = []
        for t in tasks:
            if t.status in counts:
                counts[t.status] += 1
            is_internal = bool(t.metadata and t.metadata.get("_internal"))
            duration = tracker.get_status_duration(name, t.id)
            task_responses.append(TaskResponse(
                id=t.id,
                subject=t.subject,
                description=t.description,
                status=t.status,
                blocks=t.blocks,
                blocked_by=t.blocked_by,
                owner=t.owner,
                is_internal=is_internal,
                status_duration_seconds=duration,
            ))

        total = counts["pending"] + counts["in_progress"] + counts["completed"]
        return TasksResponse(
            tasks=task_responses,
            counts=TaskCountsResponse(**counts, total=total),
        )

    @app.get(
        "/api/teams/{name}/messages",
        response_model=Union[GroupedMessagesResponse, MessagesResponse],
    )
    def get_messages(
        name: str,
        unresolved: bool = Query(default=False),
        group_by: Optional[str] = Query(default=None, alias="group_by"),
    ):
        _validate_identifier(name, "team name")
        messages = reader.get_all_messages(name)

        # Server-side unresolved filter
        if unresolved:
            messages = _filter_unresolved_messages(messages)

        # Server-side pair grouping
        if group_by == "pair":
            groups: dict[tuple, list] = {}
            for msg in messages:
                from_agent = msg.from_agent or "unknown"
                target_agent = msg.target_agent or "unknown"
                pair_key = _canonicalize_pair(from_agent, target_agent)
                groups.setdefault(pair_key, []).append(msg)

            group_responses = []
            for pair_key in sorted(groups):
                group_msgs = groups[pair_key]
                group_responses.append(MessageGroupResponse(
                    pair=list(pair_key),
                    messages=[_message_to_response(m) for m in group_msgs],
                    message_count=len(group_msgs),
                ))
            return GroupedMessagesResponse(groups=group_responses)

        return MessagesResponse(
            messages=[_message_to_response(m) for m in messages],
        )

    # ── Monitoring GET endpoints ─────────────────────────────────────────

    @app.get("/api/teams/{name}/timeline", response_model=TimelineResponse)
    def get_timeline(name: str, limit: int = 50):
        _validate_identifier(name, "team name")
        events = tracker.get_events(name, limit)
        return TimelineResponse(
            events=[
                TimelineEventResponse(
                    timestamp=e.timestamp,
                    team_name=e.team_name,
                    task_id=e.task_id,
                    task_subject=e.task_subject,
                    old_status=e.old_status,
                    new_status=e.new_status,
                    owner=e.owner,
                )
                for e in events
            ]
        )

    @app.get("/api/teams/{name}/activity", response_model=ActivityResponse)
    def get_activity(name: str):
        _validate_identifier(name, "team name")
        agents = compute_agent_activity(name, reader, tracker)
        return ActivityResponse(agents=agents)

    @app.get("/api/teams/{name}/agent-timeline", response_model=AgentTimelineResponse)
    def get_agent_timeline(name: str):
        _validate_identifier(name, "team name")
        result = build_agent_timeline(name, reader, tracker)
        if result is None:
            raise HTTPException(status_code=404, detail="Team not found")
        return result

    @app.get("/api/teams/{name}/action-queue", response_model=ActionQueueResponse)
    def get_action_queue(name: str):
        """Prioritised list of items needing operator attention."""
        _validate_identifier(name, "team name")
        config = reader.get_team_config(name)
        if config is None:
            raise HTTPException(status_code=404, detail="Team not found")
        tasks = reader.get_tasks(name)
        tracker.poll(name, tasks)
        all_messages = reader.get_all_messages(name)
        activity = compute_agent_activity(
            name, reader, tracker,
            config=config, tasks=tasks, all_messages=all_messages,
        )
        pending_permissions = extract_pending_permissions(all_messages)
        items = build_action_queue(
            pending_permissions=pending_permissions,
            activity=activity,
            tasks=tasks,
            stall_threshold_seconds=STALL_THRESHOLD_MINUTES * 60,
        )
        return ActionQueueResponse(items=items, total=len(items))

    @app.get("/api/teams/{name}/health", response_model=HealthScoreResponse)
    def get_health(name: str):
        """Compute workflow health score for a team."""
        _validate_identifier(name, "team name")
        config = reader.get_team_config(name)
        if config is None:
            raise HTTPException(status_code=404, detail="Team not found")
        tasks = reader.get_tasks(name)
        tracker.poll(name, tasks)
        all_messages = reader.get_all_messages(name)
        activity = compute_agent_activity(
            name, reader, tracker,
            config=config, tasks=tasks, all_messages=all_messages,
        )
        pending_permissions = extract_pending_permissions(all_messages)

        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for task in tasks:
            if task.status in counts:
                counts[task.status] += 1

        health = compute_health_score(
            pending_permissions=pending_permissions,
            activity=activity,
            tasks=tasks,
            counts=counts,
        )
        return HealthScoreResponse(health=health)

    @app.get("/api/teams/{name}/alerts", response_model=AlertsResponse)
    def get_alerts(name: str):
        _validate_identifier(name, "team name")
        all_messages = reader.get_all_messages(name)
        pending_permissions = extract_pending_permissions(all_messages)
        activity = compute_agent_activity(
            name,
            reader,
            tracker,
            all_messages=all_messages,
        )
        stalled_agents = [a.name for a in activity if a.is_stalled]
        return AlertsResponse(
            pending_permissions=pending_permissions,
            stalled_agents=stalled_agents,
        )

    @app.get("/api/teams/{name}/snapshot", response_model=DetailSnapshotResponse)
    def get_snapshot(name: str):
        """Consolidated payload for detail-page polling."""
        _validate_identifier(name, "team name")
        config = reader.get_team_config(name)
        if config is None:
            raise HTTPException(status_code=404, detail="Team not found")

        tasks = reader.get_tasks(name)
        tracker.poll(name, tasks)
        all_messages = reader.get_all_messages(name)
        activity = compute_agent_activity(
            name,
            reader,
            tracker,
            config=config,
            tasks=tasks,
            all_messages=all_messages,
        )
        pending_permissions = extract_pending_permissions(all_messages)

        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for task in tasks:
            if task.status in counts:
                counts[task.status] += 1
        total = counts["pending"] + counts["in_progress"] + counts["completed"]

        action_queue = build_action_queue(
            pending_permissions=pending_permissions,
            activity=activity,
            tasks=tasks,
            stall_threshold_seconds=STALL_THRESHOLD_MINUTES * 60,
        )

        health = compute_health_score(
            pending_permissions=pending_permissions,
            activity=activity,
            tasks=tasks,
            counts=counts,
        )

        current_settings = settings_service.get()
        recent_approvals = auto_approval.get_recent(
            max_age_seconds=300, limit=10
        )

        return DetailSnapshotResponse(
            team=TeamConfigResponse(
                name=config.name,
                description=config.description,
                created_at=config.created_at,
                lead_agent_id=config.lead_agent_id,
                members=[_member_to_response(m) for m in config.members],
            ),
            counts=TaskCountsResponse(**counts, total=total),
            pending_permissions=pending_permissions,
            stalled_agents=[a.name for a in activity if a.is_stalled],
            activity=activity,
            monitor_config=MonitorConfigResponse(
                stall_threshold_minutes=STALL_THRESHOLD_MINUTES,
            ),
            action_queue=action_queue,
            health_score=health.overall,
            health_color=health.color,
            health=health,
            auto_approve_enabled=current_settings.auto_approve_enabled,
            recent_auto_approvals=recent_approvals,
        )

    # ── Settings endpoints ────────────────────────────────────────────────

    @app.get("/api/settings", response_model=AutoApprovalSettingsResponse)
    def get_settings():
        """Return current auto-approval settings."""
        s = settings_service.get()
        return AutoApprovalSettingsResponse(
            auto_approve_enabled=s.auto_approve_enabled,
            auto_approve_tools=s.auto_approve_tools,
        )

    @app.put("/api/settings", response_model=AutoApprovalSettingsResponse)
    def update_settings(body: UpdateAutoApprovalRequest):
        """Update auto-approval settings."""
        s = settings_service.update(
            auto_approve_enabled=body.auto_approve_enabled,
            auto_approve_tools=body.auto_approve_tools,
        )
        return AutoApprovalSettingsResponse(
            auto_approve_enabled=s.auto_approve_enabled,
            auto_approve_tools=s.auto_approve_tools,
        )

    @app.get("/api/auto-approvals", response_model=AutoApprovalLogResponse)
    def get_auto_approvals(limit: int = Query(default=50)):
        """Return recent auto-approval log entries."""
        entries = auto_approval.get_log(limit=limit)
        return AutoApprovalLogResponse(entries=entries)

    # ── Write endpoints ──────────────────────────────────────────────────

    @app.post("/api/teams/{name}/messages/{agent}", response_model=ActionResponse)
    def send_message(
        name: str,
        agent: str,
        body: SendMessageRequest,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        _validate_identifier(name, "team name")
        _validate_identifier(agent, "agent name")
        require_write_access(x_api_key)
        success = writer.send_message(name, agent, body.from_name, body.text)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write message")
        return ActionResponse(message="Message sent")

    @app.post("/api/teams/{name}/permissions/{agent}/approve", response_model=ActionResponse)
    def approve_permission(
        name: str,
        agent: str,
        body: PermissionActionRequest,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        _validate_identifier(name, "team name")
        _validate_identifier(agent, "agent name")
        require_write_access(x_api_key)
        success = writer.send_permission_response(
            name, agent, body.request_id, body.tool_use_id, approved=True,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write approval")
        return ActionResponse(message="Permission approved")

    @app.post("/api/teams/{name}/permissions/{agent}/deny", response_model=ActionResponse)
    def deny_permission(
        name: str,
        agent: str,
        body: PermissionActionRequest,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        _validate_identifier(name, "team name")
        _validate_identifier(agent, "agent name")
        require_write_access(x_api_key)
        success = writer.send_permission_response(
            name, agent, body.request_id, body.tool_use_id, approved=False,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write denial")
        return ActionResponse(message="Permission denied")

    @app.post("/api/teams/{name}/permissions/batch", response_model=BatchPermissionResponse)
    def batch_permissions(
        name: str,
        body: BatchPermissionRequest,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        _validate_identifier(name, "team name")
        require_write_access(x_api_key)

        if not body.actions:
            return BatchPermissionResponse(
                total=0, succeeded=0, failed=0,
                message="No actions provided",
            )

        # Validate all actions before processing any
        for action in body.actions:
            _validate_identifier(action.agent_name, "agent name")
            if action.action not in ("approve", "deny"):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid action '{action.action}'; must be 'approve' or 'deny'",
                )

        succeeded = 0
        failed = 0
        for action in body.actions:
            approved = action.action == "approve"
            ok = writer.send_permission_response(
                name, action.agent_name,
                action.request_id, action.tool_use_id,
                approved=approved,
            )
            if ok:
                succeeded += 1
            else:
                failed += 1

        total = succeeded + failed
        return BatchPermissionResponse(
            total=total,
            succeeded=succeeded,
            failed=failed,
            message=f"{succeeded} of {total} permission actions completed",
        )

    @app.post("/api/teams/{name}/members/{agent}/remove", response_model=ActionResponse)
    def remove_member(
        name: str,
        agent: str,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        _validate_identifier(name, "team name")
        _validate_identifier(agent, "agent name")
        require_write_access(x_api_key)
        config = reader.get_team_config(name)
        if config is None:
            raise HTTPException(status_code=404, detail="Team not found")

        # Prevent removing the team lead
        lead = next(
            (m for m in config.members if m.agent_id == config.lead_agent_id),
            None,
        )
        if lead and lead.name == agent:
            raise HTTPException(status_code=400, detail="Cannot remove team lead")

        success = config_writer.remove_member(name, agent)
        if not success:
            raise HTTPException(status_code=404, detail="Member not found")
        return ActionResponse(message=f"Member '{agent}' removed from team config")

    return app
