"""Action Queue Service — produces a prioritised "what needs attention now" list.

Consumes the same data already read by the snapshot endpoint (pending
permissions, agent activity, tasks) and ranks items by urgency.
"""

from datetime import datetime, timezone
from typing import Optional

from ..models import (
    ActionQueueItemResponse,
    AgentActivityResponse,
    PermissionAlertResponse,
    Task,
)

# Priority thresholds (seconds)
PERMISSION_CRITICAL_AGE = 120  # 2 minutes → critical
STALL_THRESHOLD_DEFAULT = 600  # 10 minutes (fallback)

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2}

# Tool risk classification for permission safety indicators
LOW_RISK_TOOLS = {"Read", "Glob", "Grep", "WebSearch", "WebFetch"}
MEDIUM_RISK_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit"}


def build_action_queue(
    pending_permissions: list[PermissionAlertResponse],
    activity: list[AgentActivityResponse],
    tasks: list,
    stall_threshold_seconds: int = STALL_THRESHOLD_DEFAULT,
    now: Optional[datetime] = None,
) -> list[ActionQueueItemResponse]:
    """Build a ranked action queue from current team state.

    Parameters
    ----------
    pending_permissions : list of unresolved permission requests
    activity : per-agent activity summaries (from compute_agent_activity)
    tasks : raw Task dataclass list from file_reader
    stall_threshold_seconds : current stall threshold in seconds
    now : optional datetime override for testing
    """
    now = now or datetime.now(timezone.utc)
    items: list[ActionQueueItemResponse] = []

    # ── Permission items ─────────────────────────────────────────────
    for perm in pending_permissions:
        age_seconds = _age_seconds(perm.timestamp, now)
        priority = "critical" if age_seconds >= PERMISSION_CRITICAL_AGE else "high"

        items.append(ActionQueueItemResponse(
            id=f"perm:{perm.request_id}",
            category="permission",
            priority=priority,
            title=f"Permission request: {perm.tool_name}",
            detail=perm.description,
            agent_name=perm.agent_name,
            agent_color=perm.agent_color,
            target_link="action-bar",
            created_at=perm.timestamp,
            duration_seconds=age_seconds,
            # Carry through permission data for inline actions
            permission_data={
                "request_id": perm.request_id,
                "tool_use_id": perm.tool_use_id,
                "tool_name": perm.tool_name,
            },
            risk_level=_tool_risk_level(perm.tool_name),
        ))

    # ── Stalled agent items ──────────────────────────────────────────
    for agent in activity:
        if not agent.is_stalled:
            continue
        has_pending_work = agent.tasks_pending > 0 or agent.tasks_in_progress > 0
        if not has_pending_work:
            continue  # stalled with no pending work = effectively done

        stall_seconds = (agent.minutes_since_last_activity or 0) * 60
        priority = "critical" if stall_seconds >= stall_threshold_seconds * 2 else "high"

        # Build detail with optional last-completed task context
        detail = (f"No activity for {agent.minutes_since_last_activity}m. "
                  f"{agent.tasks_pending} pending, {agent.tasks_in_progress} in progress.")
        last_completed = None
        for t in tasks:
            if t.owner == agent.name and t.status == "completed":
                last_completed = t.subject
        if last_completed:
            detail += f' Last completed: "{last_completed}"'

        items.append(ActionQueueItemResponse(
            id=f"stall:{agent.name}",
            category="stalled_agent",
            priority=priority,
            title=f"{agent.name} is stalled",
            detail=detail,
            agent_name=agent.name,
            agent_color=agent.color,
            target_link="activity-cards",
            created_at=agent.last_message_at,
            duration_seconds=stall_seconds,
        ))

    # ── Blocked task items ───────────────────────────────────────────
    completed_ids = {t.id for t in tasks if t.status == "completed"}
    for task in tasks:
        if task.status == "completed":
            continue
        if not task.blocked_by:
            continue
        # Only flag if ALL blockers are still incomplete
        unresolved_blockers = [b for b in task.blocked_by if b not in completed_ids]
        if not unresolved_blockers:
            continue

        items.append(ActionQueueItemResponse(
            id=f"blocked:{task.id}",
            category="blocked_task",
            priority="normal",
            title=f"Task #{task.id} blocked",
            detail=f'"{task.subject}" blocked by #{", #".join(unresolved_blockers)}',
            agent_name=task.owner,
            agent_color=None,
            target_link="tab-tasks",
            created_at=None,
            duration_seconds=None,
        ))

    # ── Sort: priority asc, then duration desc (oldest first) ────────
    items.sort(key=lambda item: (
        PRIORITY_ORDER.get(item.priority, 99),
        -(item.duration_seconds or 0),
    ))

    return items


def _tool_risk_level(tool_name: str) -> Optional[str]:
    """Classify a tool name into a risk level for safety indicators."""
    if tool_name in LOW_RISK_TOOLS:
        return "low"
    if tool_name in MEDIUM_RISK_TOOLS:
        return "medium"
    return None


def _age_seconds(iso_timestamp: Optional[str], now: datetime) -> int:
    """Calculate seconds between an ISO timestamp and now."""
    if not iso_timestamp:
        return 0
    try:
        ts = datetime.fromisoformat(iso_timestamp)
        return max(0, int((now - ts).total_seconds()))
    except (ValueError, TypeError):
        return 0
