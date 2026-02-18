import time

from src.models import Task
from src.timeline import TimelineTracker


def _make_task(id, status, owner=None, subject=None):
    return Task(
        id=id,
        subject=subject or f"task-{id}",
        description="",
        status=status,
        owner=owner,
    )


class TestPoll:
    def test_first_poll_emits_events_for_all_tasks(self, tracker):
        tasks = [
            _make_task("1", "pending", owner="agent-1"),
            _make_task("2", "in_progress", owner="agent-2"),
        ]
        events = tracker.poll("team-a", tasks)
        assert len(events) == 2
        assert all(e.old_status == "" for e in events)
        assert events[0].new_status == "pending"
        assert events[1].new_status == "in_progress"

    def test_status_change_emits_event(self, tracker):
        tasks_v1 = [_make_task("1", "pending", owner="agent-1")]
        tracker.poll("team-a", tasks_v1)

        tasks_v2 = [_make_task("1", "in_progress", owner="agent-1")]
        events = tracker.poll("team-a", tasks_v2)
        assert len(events) == 1
        assert events[0].old_status == "pending"
        assert events[0].new_status == "in_progress"

    def test_no_change_emits_nothing(self, tracker):
        tasks = [_make_task("1", "pending")]
        tracker.poll("team-a", tasks)
        events = tracker.poll("team-a", tasks)
        assert events == []

    def test_multi_team_isolation(self, tracker):
        tasks_a = [_make_task("1", "pending")]
        tasks_b = [_make_task("1", "completed")]
        tracker.poll("team-a", tasks_a)
        tracker.poll("team-b", tasks_b)

        events_a = tracker.get_events("team-a")
        events_b = tracker.get_events("team-b")
        assert all(e.team_name == "team-a" for e in events_a)
        assert all(e.team_name == "team-b" for e in events_b)

    def test_preserves_owner(self, tracker):
        tasks = [_make_task("1", "pending", owner="agent-1")]
        events = tracker.poll("team-a", tasks)
        assert events[0].owner == "agent-1"


class TestGetEvents:
    def test_newest_first(self, tracker):
        tasks_v1 = [_make_task("1", "pending")]
        tracker.poll("team-a", tasks_v1)
        time.sleep(0.01)
        tasks_v2 = [_make_task("1", "in_progress")]
        tracker.poll("team-a", tasks_v2)

        events = tracker.get_events("team-a")
        assert len(events) == 2
        assert events[0].new_status == "in_progress"
        assert events[1].new_status == "pending"

    def test_respects_limit(self, tracker):
        for i in range(10):
            tracker.poll("team-a", [_make_task("1", f"status-{i}")])
            time.sleep(0.01)
        events = tracker.get_events("team-a", limit=3)
        assert len(events) == 3


class TestGetStatusDuration:
    def test_returns_seconds_since_last_change(self, tracker):
        tasks = [_make_task("1", "pending")]
        tracker.poll("team-a", tasks)
        time.sleep(0.05)
        duration = tracker.get_status_duration("team-a", "1")
        assert duration is not None
        assert duration >= 0

    def test_returns_none_for_unknown_task(self, tracker):
        assert tracker.get_status_duration("team-a", "999") is None


class TestGetLastActivityTime:
    def test_returns_most_recent_for_agent(self, tracker):
        tasks_v1 = [_make_task("1", "pending", owner="agent-1")]
        tracker.poll("team-a", tasks_v1)
        time.sleep(0.01)
        tasks_v2 = [_make_task("1", "in_progress", owner="agent-1")]
        tracker.poll("team-a", tasks_v2)

        last = tracker.get_last_activity_time("team-a", "agent-1")
        assert last is not None
        events = tracker.get_events("team-a")
        assert last == events[0].timestamp  # newest event

    def test_returns_none_for_unknown_agent(self, tracker):
        assert tracker.get_last_activity_time("team-a", "nobody") is None


class TestClear:
    def test_clear_specific_team(self, tracker):
        tracker.poll("team-a", [_make_task("1", "pending")])
        tracker.poll("team-b", [_make_task("1", "pending")])
        tracker.clear("team-a")
        assert tracker.get_events("team-a") == []
        assert len(tracker.get_events("team-b")) == 1

    def test_clear_all(self, tracker):
        tracker.poll("team-a", [_make_task("1", "pending")])
        tracker.poll("team-b", [_make_task("1", "pending")])
        tracker.clear()
        assert tracker.get_events("team-a") == []
        assert tracker.get_events("team-b") == []


class TestRetention:
    def test_respects_max_event_cap(self):
        capped = TimelineTracker(max_events=3)
        for i in range(6):
            capped.poll("team-a", [_make_task("1", f"state-{i}")])
        events = capped.get_events("team-a", limit=10)
        assert len(events) == 3
