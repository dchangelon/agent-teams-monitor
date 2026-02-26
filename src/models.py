from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel


# ── Internal dataclasses (file_reader return types) ──────────────────────────


@dataclass
class TeamMember:
    agent_id: str
    name: str
    agent_type: str
    model: str
    joined_at: int
    cwd: str
    color: Optional[str] = None
    prompt: Optional[str] = None
    tmux_pane_id: Optional[str] = None
    backend_type: Optional[str] = None


@dataclass
class TeamConfig:
    name: str
    description: str
    created_at: int
    lead_agent_id: str
    lead_session_id: str
    members: list[TeamMember] = field(default_factory=list)


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str
    blocks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    owner: Optional[str] = None
    metadata: Optional[dict] = None


@dataclass
class InboxMessage:
    from_agent: str
    text: str
    timestamp: str
    color: Optional[str] = None
    read: bool = False
    message_type: str = "plain"
    parsed_content: Optional[dict] = None
    target_agent: Optional[str] = None


@dataclass
class TeamSummary:
    name: str
    description: str
    created_at: int
    member_count: int
    task_counts: dict = field(default_factory=dict)
    total_tasks: int = 0
    has_unread_messages: bool = False
    members: list[TeamMember] = field(default_factory=list)


# ── Pydantic models (API request/response) ───────────────────────────────────


# --- Request models ---

class SendMessageRequest(BaseModel):
    text: str
    from_name: str = "user"


class PermissionActionRequest(BaseModel):
    request_id: str
    tool_use_id: str


class BatchPermissionAction(BaseModel):
    agent_name: str
    request_id: str
    tool_use_id: str
    action: str  # "approve" | "deny"


class BatchPermissionRequest(BaseModel):
    actions: list[BatchPermissionAction]


# --- Response models ---

class TeamMemberResponse(BaseModel):
    agent_id: str
    name: str
    agent_type: str
    model: str
    joined_at: int
    cwd: str
    color: Optional[str] = None
    prompt: Optional[str] = None


class TeamConfigResponse(BaseModel):
    name: str
    description: str
    created_at: int
    lead_agent_id: str
    members: list[TeamMemberResponse]


class TaskResponse(BaseModel):
    id: str
    subject: str
    description: str
    status: str
    blocks: list[str]
    blocked_by: list[str]
    owner: Optional[str] = None
    is_internal: bool = False
    status_duration_seconds: Optional[int] = None


class InboxMessageResponse(BaseModel):
    from_agent: str
    text: str
    timestamp: str
    color: Optional[str] = None
    read: bool = False
    message_type: str = "plain"
    parsed_content: Optional[dict] = None
    target_agent: Optional[str] = None


class TeamSummaryResponse(BaseModel):
    name: str
    description: str
    created_at: int
    member_count: int
    task_counts: dict
    total_tasks: int
    has_unread_messages: bool
    members: list[TeamMemberResponse]
    health_score: Optional[int] = None
    health_color: Optional[str] = None


class TaskCountsResponse(BaseModel):
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    total: int = 0


# --- Envelope responses ---

class TeamsListResponse(BaseModel):
    success: bool = True
    teams: list[TeamSummaryResponse]


class TeamDetailResponse(BaseModel):
    success: bool = True
    team: TeamConfigResponse


class TasksResponse(BaseModel):
    success: bool = True
    tasks: list[TaskResponse]
    counts: TaskCountsResponse


class MessagesResponse(BaseModel):
    success: bool = True
    messages: list[InboxMessageResponse]


class MessageGroupResponse(BaseModel):
    """A group of messages between a specific agent pair."""
    pair: list[str]
    messages: list[InboxMessageResponse]
    message_count: int


class GroupedMessagesResponse(BaseModel):
    """Messages grouped by conversation pairs."""
    success: bool = True
    groups: list[MessageGroupResponse]


class ActionResponse(BaseModel):
    success: bool = True
    message: str = ""


class BatchPermissionResponse(BaseModel):
    success: bool = True
    total: int
    succeeded: int
    failed: int
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


# --- Timeline + Activity models ---

class TimelineEventResponse(BaseModel):
    timestamp: str
    team_name: str
    task_id: str
    task_subject: str
    old_status: str
    new_status: str
    owner: Optional[str] = None


class TimelineResponse(BaseModel):
    success: bool = True
    events: list[TimelineEventResponse]


class AgentActivityResponse(BaseModel):
    name: str
    color: Optional[str] = None
    agent_type: str
    model: str
    tasks_pending: int = 0
    tasks_in_progress: int = 0
    tasks_completed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    last_message_at: Optional[str] = None
    minutes_since_last_activity: Optional[int] = None
    is_stalled: bool = False
    agent_status: str = "active"


class ActivityResponse(BaseModel):
    success: bool = True
    agents: list[AgentActivityResponse]


class PermissionAlertResponse(BaseModel):
    agent_name: str
    agent_color: Optional[str] = None
    tool_name: str
    description: str
    request_id: str
    tool_use_id: str
    timestamp: str


class AlertsResponse(BaseModel):
    success: bool = True
    pending_permissions: list[PermissionAlertResponse]
    stalled_agents: list[str]


# --- Action Queue models ---

class ActionQueueItemResponse(BaseModel):
    id: str
    category: str  # "permission" | "blocked_task" | "stalled_agent"
    priority: str  # "critical" | "high" | "normal"
    title: str
    detail: str
    agent_name: Optional[str] = None
    agent_color: Optional[str] = None
    target_link: Optional[str] = None
    created_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    permission_data: Optional[dict] = None
    risk_level: Optional[str] = None  # "low" | "medium" | None


class ActionQueueResponse(BaseModel):
    success: bool = True
    items: list[ActionQueueItemResponse]
    total: int = 0


# --- Health Score models ---


class DimensionScoreResponse(BaseModel):
    name: str       # "permission_latency" | "stall_ratio" | "blocked_ratio" | "throughput"
    score: int      # 0-100
    weight: float   # 0.20-0.30
    explanation: str


class HealthScoreBreakdown(BaseModel):
    overall: int    # 0-100
    color: str      # "green" | "amber" | "red"
    label: str      # "Healthy" | "Needs Attention" | "Critical"
    dimensions: list[DimensionScoreResponse]


class HealthScoreResponse(BaseModel):
    success: bool = True
    health: HealthScoreBreakdown


# --- Consolidated detail snapshot model ---

class MonitorConfigResponse(BaseModel):
    stall_threshold_minutes: int


class DetailSnapshotResponse(BaseModel):
    success: bool = True
    team: TeamConfigResponse
    counts: TaskCountsResponse
    pending_permissions: list[PermissionAlertResponse]
    stalled_agents: list[str]
    activity: list[AgentActivityResponse]
    monitor_config: MonitorConfigResponse
    action_queue: list[ActionQueueItemResponse] = []
    health_score: Optional[int] = None
    health_color: Optional[str] = None
    health: Optional[HealthScoreBreakdown] = None
    auto_approve_enabled: bool = True
    recent_auto_approvals: list["AutoApprovalLogEntry"] = []


# --- Agent Swim Lane Timeline models ---

class AgentLifecycleEvent(BaseModel):
    timestamp: str
    event_type: str
    description: str
    related_agent: Optional[str] = None


class AgentTimelineEntry(BaseModel):
    name: str
    agent_type: str
    color: Optional[str] = None
    joined_at: str
    shutdown_at: Optional[str] = None
    events: list[AgentLifecycleEvent]


class AgentTimelineResponse(BaseModel):
    success: bool = True
    team_name: str
    created_at: str
    agents: list[AgentTimelineEntry]


# --- Auto-Approval models ---


class UpdateAutoApprovalRequest(BaseModel):
    auto_approve_enabled: Optional[bool] = None
    auto_approve_tools: Optional[list[str]] = None


class AutoApprovalSettingsResponse(BaseModel):
    success: bool = True
    auto_approve_enabled: bool
    auto_approve_tools: list[str]


class AutoApprovalLogEntry(BaseModel):
    request_id: str
    agent_name: str
    tool_name: str
    tool_use_id: str
    team_name: str
    timestamp: str


class AutoApprovalLogResponse(BaseModel):
    success: bool = True
    entries: list[AutoApprovalLogEntry]
