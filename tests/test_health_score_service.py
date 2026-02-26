"""Tests for the Health Score Service."""

from datetime import datetime, timedelta, timezone

from src.models import AgentActivityResponse, PermissionAlertResponse
from src.services.health_score_service import compute_health_score

# ── Helpers ────────────────────────────────────────────────────────────────

NOW = datetime(2026, 2, 14, 19, 5, 0, tzinfo=timezone.utc)


def _make_permission(
    request_id="perm-1",
    agent="agent-1",
    tool_name="Bash",
    description="Run tests",
    timestamp="2026-02-14T19:00:00+00:00",
    agent_color="blue",
    tool_use_id="toolu_01",
):
    return PermissionAlertResponse(
        agent_name=agent,
        agent_color=agent_color,
        tool_name=tool_name,
        description=description,
        request_id=request_id,
        tool_use_id=tool_use_id,
        timestamp=timestamp,
    )


def _make_activity(
    name="agent-1",
    is_stalled=False,
    tasks_pending=0,
    tasks_in_progress=0,
    tasks_completed=0,
    minutes_since=5,
    color="blue",
    last_message_at="2026-02-14T19:00:00+00:00",
):
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
    def __init__(self, id, subject="Task", status="pending", owner=None, blocked_by=None):
        self.id = id
        self.subject = subject
        self.status = status
        self.owner = owner
        self.blocked_by = blocked_by or []
        self.blocks = []
        self.description = ""
        self.metadata = None


# ── Test classes ───────────────────────────────────────────────────────────


class TestPerfectScore:
    def test_score_100_no_issues(self):
        """All tasks completed, no stalls, no permissions = 100."""
        tasks = [_FakeTask(id="1", status="completed")]
        counts = {"pending": 0, "in_progress": 0, "completed": 1}
        activity = [_make_activity(tasks_completed=1)]
        result = compute_health_score([], activity, tasks, counts, now=NOW)
        assert result.overall == 100
        assert result.color == "green"
        assert result.label == "Healthy"

    def test_empty_team_is_healthy(self):
        """0 tasks, 0 agents, 0 permissions = 100."""
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        assert result.overall == 100
        assert result.color == "green"


class TestPermissionLatencyDimension:
    def test_one_permission_at_zero_wait(self):
        """1 permission at 0s wait: penalty=25, dimension score=75."""
        perm = _make_permission(timestamp=NOW.isoformat())
        tasks = [_FakeTask(id="1", status="completed")]
        counts = {"pending": 0, "in_progress": 0, "completed": 1}
        activity = [_make_activity(tasks_completed=1)]
        result = compute_health_score([perm], activity, tasks, counts, now=NOW)
        # permission_latency: 75 * 0.30 = 22.5
        # stall: 100 * 0.25 = 25
        # blocked: 100 * 0.25 = 25
        # throughput: 100 * 0.20 = 20
        # total = 92.5 -> 93 (rounds up)
        assert result.overall == 93 or result.overall == 92  # rounding
        perm_dim = next(d for d in result.dimensions if d.name == "permission_latency")
        assert perm_dim.score == 75

    def test_one_permission_at_5_minutes(self):
        """1 permission at 300s: penalty = 25 + 300/60 = 30, score = 70."""
        ts = (NOW - timedelta(minutes=5)).isoformat()
        perm = _make_permission(timestamp=ts)
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([perm], [], [], counts, now=NOW)
        perm_dim = next(d for d in result.dimensions if d.name == "permission_latency")
        assert perm_dim.score == 70

    def test_two_permissions_at_zero_wait(self):
        """2 permissions at 0s: penalty = 50, dimension score = 50."""
        perms = [
            _make_permission(request_id="p1", timestamp=NOW.isoformat()),
            _make_permission(request_id="p2", timestamp=NOW.isoformat()),
        ]
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score(perms, [], [], counts, now=NOW)
        perm_dim = next(d for d in result.dimensions if d.name == "permission_latency")
        assert perm_dim.score == 50

    def test_four_permissions_clamps_to_zero(self):
        """4 permissions at 0s: penalty = 100, dimension score = 0."""
        perms = [
            _make_permission(request_id=f"p{i}", timestamp=NOW.isoformat())
            for i in range(4)
        ]
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score(perms, [], [], counts, now=NOW)
        perm_dim = next(d for d in result.dimensions if d.name == "permission_latency")
        assert perm_dim.score == 0

    def test_no_permissions_scores_100(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        perm_dim = next(d for d in result.dimensions if d.name == "permission_latency")
        assert perm_dim.score == 100


class TestStallRatioDimension:
    def test_no_stalled_agents(self):
        activity = [_make_activity(name="a1"), _make_activity(name="a2")]
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], activity, [], counts, now=NOW)
        stall_dim = next(d for d in result.dimensions if d.name == "stall_ratio")
        assert stall_dim.score == 100

    def test_one_of_three_stalled(self):
        """1/3 stalled: score = 100*(1 - 1/3) = 67."""
        activity = [
            _make_activity(name="a1", is_stalled=True),
            _make_activity(name="a2"),
            _make_activity(name="a3"),
        ]
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], activity, [], counts, now=NOW)
        stall_dim = next(d for d in result.dimensions if d.name == "stall_ratio")
        assert stall_dim.score == 67

    def test_all_agents_stalled(self):
        activity = [
            _make_activity(name=f"a{i}", is_stalled=True) for i in range(3)
        ]
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], activity, [], counts, now=NOW)
        stall_dim = next(d for d in result.dimensions if d.name == "stall_ratio")
        assert stall_dim.score == 0

    def test_zero_agents_scores_100(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        stall_dim = next(d for d in result.dimensions if d.name == "stall_ratio")
        assert stall_dim.score == 100


class TestBlockedRatioDimension:
    def test_no_blocked_tasks(self):
        tasks = [
            _FakeTask(id="1", status="pending"),
            _FakeTask(id="2", status="in_progress"),
        ]
        counts = {"pending": 1, "in_progress": 1, "completed": 0}
        result = compute_health_score([], [], tasks, counts, now=NOW)
        blocked_dim = next(d for d in result.dimensions if d.name == "blocked_ratio")
        assert blocked_dim.score == 100

    def test_one_blocked_of_three(self):
        """1 blocked of 3: score = 100*(1 - 1/3) = 67."""
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
            _FakeTask(id="3", status="pending"),
        ]
        counts = {"pending": 2, "in_progress": 1, "completed": 0}
        result = compute_health_score([], [], tasks, counts, now=NOW)
        blocked_dim = next(d for d in result.dimensions if d.name == "blocked_ratio")
        assert blocked_dim.score == 67

    def test_blocker_completed_not_blocked(self):
        """If blocker is completed, task is not considered blocked."""
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="completed"),
        ]
        counts = {"pending": 1, "in_progress": 0, "completed": 1}
        result = compute_health_score([], [], tasks, counts, now=NOW)
        blocked_dim = next(d for d in result.dimensions if d.name == "blocked_ratio")
        assert blocked_dim.score == 100

    def test_completed_task_with_blocker_not_counted(self):
        """Completed task is never blocked even if blocked_by is set."""
        tasks = [
            _FakeTask(id="1", status="completed", blocked_by=["2"]),
            _FakeTask(id="2", status="in_progress"),
        ]
        counts = {"pending": 0, "in_progress": 1, "completed": 1}
        result = compute_health_score([], [], tasks, counts, now=NOW)
        blocked_dim = next(d for d in result.dimensions if d.name == "blocked_ratio")
        assert blocked_dim.score == 100

    def test_zero_tasks_scores_100(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        blocked_dim = next(d for d in result.dimensions if d.name == "blocked_ratio")
        assert blocked_dim.score == 100


class TestThroughputDimension:
    def test_all_completed(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 5}
        result = compute_health_score([], [], [], counts, now=NOW)
        tp_dim = next(d for d in result.dimensions if d.name == "throughput")
        assert tp_dim.score == 100

    def test_one_of_three_completed(self):
        """1/3 completed: score = 33."""
        counts = {"pending": 1, "in_progress": 1, "completed": 1}
        result = compute_health_score([], [], [], counts, now=NOW)
        tp_dim = next(d for d in result.dimensions if d.name == "throughput")
        assert tp_dim.score == 33

    def test_none_completed(self):
        counts = {"pending": 2, "in_progress": 1, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        tp_dim = next(d for d in result.dimensions if d.name == "throughput")
        assert tp_dim.score == 0

    def test_zero_tasks_scores_100(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        tp_dim = next(d for d in result.dimensions if d.name == "throughput")
        assert tp_dim.score == 100


class TestOverallScoreAndColor:
    def test_color_green_at_80(self):
        """Score >= 80 is green."""
        tasks = [_FakeTask(id="1", status="completed")]
        counts = {"pending": 0, "in_progress": 0, "completed": 1}
        activity = [_make_activity(tasks_completed=1)]
        result = compute_health_score([], activity, tasks, counts, now=NOW)
        assert result.color == "green"
        assert result.label == "Healthy"

    def test_color_amber_scenario(self):
        """Contrive a scenario that yields an amber score (50-79)."""
        # permission_latency: 75 * 0.30 = 22.5
        # stall: 67 * 0.25 = 16.75
        # blocked: 100 * 0.25 = 25
        # throughput: 0 * 0.20 = 0
        # total = 64.25 -> 64
        perm = _make_permission(timestamp=NOW.isoformat())
        activity = [
            _make_activity(name="a1", is_stalled=True),
            _make_activity(name="a2"),
            _make_activity(name="a3"),
        ]
        tasks = [
            _FakeTask(id="1", status="pending"),
            _FakeTask(id="2", status="in_progress"),
            _FakeTask(id="3", status="pending"),
        ]
        counts = {"pending": 2, "in_progress": 1, "completed": 0}
        result = compute_health_score([perm], activity, tasks, counts, now=NOW)
        assert result.color == "amber"
        assert result.label == "Needs Attention"
        assert 50 <= result.overall <= 79

    def test_color_red_below_50(self):
        """Score < 50 is red."""
        perms = [
            _make_permission(request_id=f"p{i}", timestamp=NOW.isoformat())
            for i in range(3)
        ]
        activity = [
            _make_activity(name=f"a{i}", is_stalled=True) for i in range(3)
        ]
        tasks = [
            _FakeTask(id="1", status="pending", blocked_by=["2"]),
            _FakeTask(id="2", status="pending", blocked_by=["3"]),
            _FakeTask(id="3", status="in_progress"),
        ]
        counts = {"pending": 2, "in_progress": 1, "completed": 0}
        result = compute_health_score(perms, activity, tasks, counts, now=NOW)
        assert result.color == "red"
        assert result.label == "Critical"
        assert result.overall < 50

    def test_overall_clamped_to_zero(self):
        """With extreme penalties, score should not go below 0."""
        perms = [
            _make_permission(
                request_id=f"p{i}",
                timestamp=(NOW - timedelta(minutes=10)).isoformat(),
            )
            for i in range(10)
        ]
        activity = [
            _make_activity(name=f"a{i}", is_stalled=True) for i in range(5)
        ]
        counts = {"pending": 5, "in_progress": 0, "completed": 0}
        result = compute_health_score(perms, activity, [], counts, now=NOW)
        assert result.overall >= 0


class TestDimensionExplanations:
    def test_all_explanations_are_nonempty(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        for dim in result.dimensions:
            assert isinstance(dim.explanation, str)
            assert len(dim.explanation) > 0

    def test_always_four_dimensions(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        assert len(result.dimensions) == 4
        names = {d.name for d in result.dimensions}
        assert names == {"permission_latency", "stall_ratio", "blocked_ratio", "throughput"}

    def test_weights_sum_to_one(self):
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        result = compute_health_score([], [], [], counts, now=NOW)
        total_weight = sum(d.weight for d in result.dimensions)
        assert abs(total_weight - 1.0) < 0.001
