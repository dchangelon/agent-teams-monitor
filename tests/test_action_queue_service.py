"""Tests for the Action Queue Service."""

from datetime import datetime, timezone, timedelta

from src.models import (
    ActionQueueItemResponse,
    AgentActivityResponse,
    PermissionAlertResponse,
)
from src.services.action_queue_service import build_action_queue, PERMISSION_CRITICAL_AGE


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_permission(request_id="perm-1", agent="agent-1", tool_name="Bash",
                     description="Run tests", timestamp="2026-02-14T19:00:00+00:00",
                     agent_color="blue", tool_use_id="toolu_01"):
    return PermissionAlertResponse(
        agent_name=agent,
        agent_color=agent_color,
        tool_name=tool_name,
        description=description,
        request_id=request_id,
        tool_use_id=tool_use_id,
        timestamp=timestamp,
    )


def _make_activity(name="agent-1", is_stalled=False, tasks_pending=0,
                   tasks_in_progress=0, tasks_completed=0,
                   minutes_since=5, color="blue",
                   last_message_at="2026-02-14T19:00:00+00:00"):
    return AgentActivityResponse(
        name=name,
        color=color,
        agent_type="implementer",
        model="claude-sonnet-4-6",
        tasks_pending=tasks_pending,
        tasks_in_progress=tasks_in_progress,
        tasks_completed=tasks_completed,
        messages_sent=3,
        messages_received=2,
        last_message_at=last_message_at,
        minutes_since_last_activity=minutes_since,
        is_stalled=is_stalled,
        agent_status="stalled" if is_stalled else "active",
    )


class _FakeTask:
    """Minimal task-like object for testing."""
    def __init__(self, id, subject="Task", status="pending", owner=None,
                 blocked_by=None):
        self.id = id
        self.subject = subject
        self.status = status
        self.owner = owner
        self.blocked_by = blocked_by or []
        self.blocks = []
        self.description = ""
        self.metadata = None


NOW = datetime(2026, 2, 14, 19, 5, 0, tzinfo=timezone.utc)


# ── Tests: Empty inputs ─────────────────────────────────────────────────────

class TestEmptyQueue:
    def test_empty_when_no_issues(self):
        result = build_action_queue([], [], [], now=NOW)
        assert result == []

    def test_empty_when_no_data(self):
        result = build_action_queue([], [], [])
        assert result == []


# ── Tests: Permission items ─────────────────────────────────────────────────

class TestPermissionItems:
    def test_single_permission_becomes_high(self):
        """A recent permission (under 2 min old) gets 'high' priority."""
        perm = _make_permission(timestamp="2026-02-14T19:04:00+00:00")
        result = build_action_queue([perm], [], [], now=NOW)

        assert len(result) == 1
        assert result[0].category == "permission"
        assert result[0].priority == "high"
        assert result[0].id == "perm:perm-1"
        assert result[0].permission_data is not None
        assert result[0].permission_data["request_id"] == "perm-1"

    def test_old_permission_becomes_critical(self):
        """A permission older than 2 minutes gets 'critical' priority."""
        old_ts = (NOW - timedelta(seconds=PERMISSION_CRITICAL_AGE + 30)).isoformat()
        perm = _make_permission(timestamp=old_ts)
        result = build_action_queue([perm], [], [], now=NOW)

        assert len(result) == 1
        assert result[0].priority == "critical"
        assert result[0].duration_seconds >= PERMISSION_CRITICAL_AGE

    def test_multiple_permissions_sorted_by_age(self):
        """Older (critical) permissions appear before newer (high) ones."""
        old = _make_permission(
            request_id="old",
            timestamp=(NOW - timedelta(minutes=5)).isoformat(),
        )
        new = _make_permission(
            request_id="new",
            timestamp=(NOW - timedelta(seconds=30)).isoformat(),
        )
        result = build_action_queue([new, old], [], [], now=NOW)

        assert len(result) == 2
        assert result[0].id == "perm:old"
        assert result[0].priority == "critical"
        assert result[1].id == "perm:new"
        assert result[1].priority == "high"

    def test_permission_carries_agent_info(self):
        perm = _make_permission(agent="researcher", agent_color="green")
        result = build_action_queue([perm], [], [], now=NOW)
        assert result[0].agent_name == "researcher"
        assert result[0].agent_color == "green"


# ── Tests: Stalled agent items ──────────────────────────────────────────────

class TestStalledAgentItems:
    def test_stalled_agent_with_pending_work(self):
        agent = _make_activity(
            name="slow-agent", is_stalled=True,
            tasks_pending=2, minutes_since=15,
        )
        result = build_action_queue([], [agent], [], now=NOW)

        assert len(result) == 1
        assert result[0].category == "stalled_agent"
        assert result[0].priority == "high"
        assert "slow-agent" in result[0].title

    def test_stalled_agent_without_pending_work_excluded(self):
        """Stalled agent with no pending tasks is effectively done — excluded."""
        agent = _make_activity(
            name="done-agent", is_stalled=True,
            tasks_pending=0, tasks_in_progress=0, tasks_completed=3,
        )
        result = build_action_queue([], [agent], [], now=NOW)
        assert len(result) == 0

    def test_active_agent_excluded(self):
        agent = _make_activity(name="busy-agent", is_stalled=False)
        result = build_action_queue([], [agent], [], now=NOW)
        assert len(result) == 0

    def test_very_stalled_agent_becomes_critical(self):
        """Agent stalled for 2x threshold becomes critical."""
        agent = _make_activity(
            name="very-stalled", is_stalled=True,
            tasks_in_progress=1, minutes_since=25,
        )
        # threshold 10 min = 600s, agent is at 25 min = 1500s, > 2*600=1200
        result = build_action_queue(
            [], [agent], [],
            stall_threshold_seconds=600, now=NOW,
        )
        assert result[0].priority == "critical"


# ── Tests: Blocked task items ───────────────────────────────────────────────

class TestBlockedTaskItems:
    def test_blocked_task_appears(self):
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
        ]
        result = build_action_queue([], [], tasks, now=NOW)

        assert len(result) == 1
        assert result[0].category == "blocked_task"
        assert result[0].priority == "normal"
        assert "#1" in result[0].title

    def test_blocked_by_completed_task_excluded(self):
        """If the blocker is done, the task is no longer blocked."""
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="completed"),
        ]
        result = build_action_queue([], [], tasks, now=NOW)
        assert len(result) == 0

    def test_completed_task_not_flagged(self):
        tasks = [
            _FakeTask(id="1", status="completed", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
        ]
        result = build_action_queue([], [], tasks, now=NOW)
        assert len(result) == 0


# ── Tests: Priority sorting ─────────────────────────────────────────────────

class TestPrioritySorting:
    def test_critical_before_high_before_normal(self):
        old_perm = _make_permission(
            request_id="old-perm",
            timestamp=(NOW - timedelta(minutes=5)).isoformat(),
        )
        new_perm = _make_permission(
            request_id="new-perm",
            timestamp=(NOW - timedelta(seconds=30)).isoformat(),
        )
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
        ]

        result = build_action_queue([old_perm, new_perm], [], tasks, now=NOW)

        priorities = [item.priority for item in result]
        assert priorities == ["critical", "high", "normal"]

    def test_within_same_priority_older_first(self):
        perm1 = _make_permission(
            request_id="older",
            timestamp=(NOW - timedelta(seconds=90)).isoformat(),
        )
        perm2 = _make_permission(
            request_id="newer",
            timestamp=(NOW - timedelta(seconds=30)).isoformat(),
        )

        result = build_action_queue([perm2, perm1], [], [], now=NOW)
        assert result[0].id == "perm:older"
        assert result[1].id == "perm:newer"


# ── Tests: Mixed scenario ───────────────────────────────────────────────────

class TestMixedScenario:
    def test_heavy_permission_load(self):
        """Simulate many concurrent permissions — all appear in queue."""
        perms = [
            _make_permission(
                request_id=f"perm-{i}",
                timestamp=(NOW - timedelta(seconds=30 * i)).isoformat(),
            )
            for i in range(10)
        ]
        result = build_action_queue(perms, [], [], now=NOW)
        assert len(result) == 10
        # First ones should be the oldest (highest duration)
        assert result[0].duration_seconds >= result[-1].duration_seconds

    def test_all_categories_present(self):
        perm = _make_permission(timestamp=(NOW - timedelta(seconds=60)).isoformat())
        stalled = _make_activity(
            name="stalled-agent", is_stalled=True, tasks_pending=1,
        )
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
        ]

        result = build_action_queue([perm], [stalled], tasks, now=NOW)
        categories = {item.category for item in result}
        assert categories == {"permission", "stalled_agent", "blocked_task"}


# ── Tests: Risk level ──────────────────────────────────────────────────────

class TestRiskLevel:
    def test_permission_risk_level_low(self):
        """Read-only tools get 'low' risk level."""
        perm = _make_permission(tool_name="Read")
        result = build_action_queue([perm], [], [], now=NOW)
        assert result[0].risk_level == "low"

    def test_permission_risk_level_low_variants(self):
        """All low-risk tools are classified correctly."""
        for tool in ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]:
            perm = _make_permission(tool_name=tool, request_id=f"perm-{tool}")
            result = build_action_queue([perm], [], [], now=NOW)
            assert result[0].risk_level == "low", f"{tool} should be low risk"

    def test_permission_risk_level_medium(self):
        """Write/execute tools get 'medium' risk level."""
        perm = _make_permission(tool_name="Bash")
        result = build_action_queue([perm], [], [], now=NOW)
        assert result[0].risk_level == "medium"

    def test_permission_risk_level_medium_variants(self):
        """All medium-risk tools are classified correctly."""
        for tool in ["Bash", "Write", "Edit", "NotebookEdit"]:
            perm = _make_permission(tool_name=tool, request_id=f"perm-{tool}")
            result = build_action_queue([perm], [], [], now=NOW)
            assert result[0].risk_level == "medium", f"{tool} should be medium risk"

    def test_permission_risk_level_none(self):
        """Unknown tools get None risk level."""
        perm = _make_permission(tool_name="CustomTool")
        result = build_action_queue([perm], [], [], now=NOW)
        assert result[0].risk_level is None

    def test_risk_level_not_set_for_non_permission(self):
        """Non-permission items should have risk_level=None."""
        agent = _make_activity(
            name="stalled-agent", is_stalled=True, tasks_pending=1,
        )
        result = build_action_queue([], [agent], [], now=NOW)
        assert result[0].risk_level is None


# ── Tests: Stall context ──────────────────────────────────────────────────

class TestStallContext:
    def test_stall_detail_includes_last_completed_task(self):
        """Stalled agent detail should mention the last completed task."""
        agent = _make_activity(
            name="worker", is_stalled=True, tasks_pending=1, minutes_since=15,
        )
        tasks = [
            _FakeTask(id="1", subject="Set up database", status="completed", owner="worker"),
            _FakeTask(id="2", subject="Build API", status="in_progress", owner="worker"),
        ]
        result = build_action_queue([], [agent], tasks, now=NOW)
        assert 'Last completed: "Set up database"' in result[0].detail

    def test_stall_detail_without_completed_tasks(self):
        """Without completed tasks, detail should not mention last completed."""
        agent = _make_activity(
            name="worker", is_stalled=True, tasks_pending=2, minutes_since=15,
        )
        tasks = [
            _FakeTask(id="1", subject="Build API", status="pending", owner="worker"),
        ]
        result = build_action_queue([], [agent], tasks, now=NOW)
        assert "Last completed" not in result[0].detail
        assert "2 pending" in result[0].detail
