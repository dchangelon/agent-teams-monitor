"""Health Score Service — computes a 0-100 workflow health score.

Consumes the same pre-computed data available in the snapshot endpoint
(pending permissions, agent activity, raw tasks, task counts) and
produces a weighted health score with per-dimension breakdowns.
"""

from datetime import datetime, timezone
from typing import Optional

from ..models import (
    AgentActivityResponse,
    DimensionScoreResponse,
    HealthScoreBreakdown,
    PermissionAlertResponse,
)


def compute_health_score(
    pending_permissions: list[PermissionAlertResponse],
    activity: list[AgentActivityResponse],
    tasks: list,
    counts: dict,
    now: Optional[datetime] = None,
) -> HealthScoreBreakdown:
    """Compute a 0-100 health score from four weighted dimensions.

    Parameters
    ----------
    pending_permissions : unresolved permission requests
    activity : per-agent activity summaries (from compute_agent_activity)
    tasks : raw Task dataclass list from file_reader
    counts : {"pending": N, "in_progress": N, "completed": N}
    now : optional datetime override for deterministic testing
    """
    now = now or datetime.now(timezone.utc)

    dimensions = [
        _score_permission_latency(pending_permissions, now),
        _score_stall_ratio(activity),
        _score_blocked_ratio(tasks, counts),
        _score_throughput(counts),
    ]

    weighted_sum = sum(d.score * d.weight for d in dimensions)
    overall = int(round(max(0, min(100, weighted_sum))))

    if overall >= 80:
        color = "green"
        label = "Healthy"
    elif overall >= 50:
        color = "amber"
        label = "Needs Attention"
    else:
        color = "red"
        label = "Critical"

    return HealthScoreBreakdown(
        overall=overall,
        color=color,
        label=label,
        dimensions=dimensions,
    )


# ── Dimension scorers ─────────────────────────────────────────────────────


def _score_permission_latency(
    pending_permissions: list[PermissionAlertResponse],
    now: datetime,
) -> DimensionScoreResponse:
    """30% weight. Penalty = 25 + (wait_seconds / 60) per permission."""
    if len(pending_permissions) == 0:
        return DimensionScoreResponse(
            name="permission_latency",
            score=100,
            weight=0.30,
            explanation="No pending permissions",
        )

    total_penalty = 0.0
    for perm in pending_permissions:
        wait_seconds = _age_seconds(perm.timestamp, now)
        total_penalty += 25 + (wait_seconds / 60)

    raw = max(0, min(100, 100 - total_penalty))
    score = int(round(raw))

    count = len(pending_permissions)
    explanation = (
        f"{count} pending permission{'s' if count != 1 else ''}"
        f" (penalty: {total_penalty:.0f})"
    )
    return DimensionScoreResponse(
        name="permission_latency",
        score=score,
        weight=0.30,
        explanation=explanation,
    )


def _score_stall_ratio(
    activity: list[AgentActivityResponse],
) -> DimensionScoreResponse:
    """25% weight. Score = 100 * (1 - stalled / total)."""
    total_agents = len(activity)
    if total_agents == 0:
        return DimensionScoreResponse(
            name="stall_ratio",
            score=100,
            weight=0.25,
            explanation="No agents",
        )

    stalled_count = sum(1 for a in activity if a.is_stalled)
    raw = 100 * (1 - stalled_count / total_agents)
    score = int(round(raw))

    explanation = (
        f"{stalled_count} of {total_agents}"
        f" agent{'s' if total_agents != 1 else ''} stalled"
    )
    return DimensionScoreResponse(
        name="stall_ratio",
        score=score,
        weight=0.25,
        explanation=explanation,
    )


def _score_blocked_ratio(
    tasks: list,
    counts: dict,
) -> DimensionScoreResponse:
    """25% weight. Score = 100 * (1 - blocked / total).

    A task is "blocked" if it's not completed, has blocked_by entries,
    and at least one blocker is not yet completed.
    """
    total = counts.get("pending", 0) + counts.get("in_progress", 0) + counts.get("completed", 0)
    if total == 0:
        return DimensionScoreResponse(
            name="blocked_ratio",
            score=100,
            weight=0.25,
            explanation="No tasks",
        )

    completed_ids = {t.id for t in tasks if t.status == "completed"}
    blocked_count = 0
    for task in tasks:
        if task.status == "completed":
            continue
        if not task.blocked_by:
            continue
        unresolved = [b for b in task.blocked_by if b not in completed_ids]
        if unresolved:
            blocked_count += 1

    raw = 100 * (1 - blocked_count / total)
    score = int(round(raw))

    explanation = f"{blocked_count} of {total} task{'s' if total != 1 else ''} blocked"
    return DimensionScoreResponse(
        name="blocked_ratio",
        score=score,
        weight=0.25,
        explanation=explanation,
    )


def _score_throughput(
    counts: dict,
) -> DimensionScoreResponse:
    """20% weight. Score = 100 * (completed / total)."""
    total = counts.get("pending", 0) + counts.get("in_progress", 0) + counts.get("completed", 0)
    if total == 0:
        return DimensionScoreResponse(
            name="throughput",
            score=100,
            weight=0.20,
            explanation="No tasks",
        )

    completed = counts.get("completed", 0)
    raw = 100 * (completed / total)
    score = int(round(raw))

    explanation = f"{completed} of {total} task{'s' if total != 1 else ''} completed"
    return DimensionScoreResponse(
        name="throughput",
        score=score,
        weight=0.20,
        explanation=explanation,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _age_seconds(iso_timestamp: Optional[str], now: datetime) -> int:
    """Calculate seconds between an ISO timestamp and now."""
    if not iso_timestamp:
        return 0
    try:
        ts = datetime.fromisoformat(iso_timestamp)
        return max(0, int((now - ts).total_seconds()))
    except (ValueError, TypeError):
        return 0
