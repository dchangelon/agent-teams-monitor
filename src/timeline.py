from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TimelineEvent:
    timestamp: str        # ISO 8601
    team_name: str
    task_id: str
    task_subject: str
    old_status: str       # "" for first observation
    new_status: str
    owner: Optional[str] = None


class TimelineTracker:
    def __init__(self, max_events: int = 10000):
        self._previous_states: dict[str, dict[str, str]] = {}  # team -> {task_id: status}
        self._events: list[TimelineEvent] = []
        self._max_events = max(1, max_events)

    def poll(self, team_name: str, tasks: list) -> list[TimelineEvent]:
        """Compare current task states to previous snapshot, emit events for changes.

        Called from the tasks endpoint handler on each request.
        Returns list of new events detected in this poll cycle.
        """
        current_states = {t.id: t.status for t in tasks}
        previous = self._previous_states.get(team_name, {})
        new_events = []

        for task in tasks:
            old_status = previous.get(task.id, "")
            if old_status != task.status:
                event = TimelineEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    team_name=team_name,
                    task_id=task.id,
                    task_subject=task.subject,
                    old_status=old_status,
                    new_status=task.status,
                    owner=task.owner,
                )
                new_events.append(event)
                self._events.append(event)
                if len(self._events) > self._max_events:
                    self._events = self._events[-self._max_events:]

        self._previous_states[team_name] = current_states
        return new_events

    def get_events(self, team_name: str, limit: int = 50) -> list[TimelineEvent]:
        """Return events for a team, newest first."""
        team_events = [e for e in self._events if e.team_name == team_name]
        return sorted(team_events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def clear(self, team_name: str = None):
        """Clear events. If team_name provided, clear only that team."""
        if team_name:
            self._events = [e for e in self._events if e.team_name != team_name]
            self._previous_states.pop(team_name, None)
        else:
            self._events.clear()
            self._previous_states.clear()

    def get_status_duration(self, team_name: str, task_id: str) -> Optional[int]:
        """Return seconds since the most recent status change for a task.

        Returns None if no events recorded for this task.
        """
        task_events = [
            e for e in self._events
            if e.team_name == team_name and e.task_id == task_id
        ]
        if not task_events:
            return None
        latest = max(task_events, key=lambda e: e.timestamp)
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(latest.timestamp)
        return int(delta.total_seconds())

    def get_last_activity_time(self, team_name: str, agent_name: str) -> Optional[str]:
        """Return ISO timestamp of most recent event involving this agent (by owner)."""
        agent_events = [
            e for e in self._events
            if e.team_name == team_name and e.owner == agent_name
        ]
        if not agent_events:
            return None
        return max(e.timestamp for e in agent_events)
