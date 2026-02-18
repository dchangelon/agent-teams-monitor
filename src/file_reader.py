import json
import logging
from pathlib import Path
from typing import Optional

from .config import TEAMS_DIR, TASKS_DIR
from .models import InboxMessage, Task, TeamConfig, TeamMember, TeamSummary

logger = logging.getLogger(__name__)


class TeamFileReader:
    def __init__(self, teams_base: Optional[Path] = None, tasks_base: Optional[Path] = None):
        self.teams_base = teams_base or TEAMS_DIR
        self.tasks_base = tasks_base or TASKS_DIR

    def list_teams(self) -> list[str]:
        """Return team directory names."""
        if not self.teams_base.exists():
            return []
        return [
            d.name for d in sorted(self.teams_base.iterdir())
            if d.is_dir()
        ]

    def get_team_config(self, team_name: str) -> Optional[TeamConfig]:
        """Read and parse config.json for a team."""
        config_path = self.teams_base / team_name / "config.json"
        data = self._read_json(config_path)
        if data is None:
            return None

        members = []
        for m in data.get("members", []):
            members.append(TeamMember(
                agent_id=m.get("agentId", ""),
                name=m.get("name", ""),
                agent_type=m.get("agentType", ""),
                model=m.get("model", ""),
                joined_at=m.get("joinedAt", 0),
                cwd=m.get("cwd", ""),
                color=m.get("color"),
                prompt=m.get("prompt"),
                tmux_pane_id=m.get("tmuxPaneId"),
                backend_type=m.get("backendType"),
            ))

        return TeamConfig(
            name=data.get("name", team_name),
            description=data.get("description", ""),
            created_at=data.get("createdAt", 0),
            lead_agent_id=data.get("leadAgentId", ""),
            lead_session_id=data.get("leadSessionId", ""),
            members=members,
        )

    def get_tasks(self, team_name: str) -> list[Task]:
        """Read all task JSON files for a team, skipping .lock files."""
        tasks_dir = self.tasks_base / team_name
        if not tasks_dir.exists():
            return []

        tasks = []
        for path in sorted(tasks_dir.iterdir()):
            if not path.is_file() or path.suffix != ".json":
                continue
            data = self._read_json(path)
            if data is None:
                continue
            tasks.append(Task(
                id=data.get("id", path.stem),
                subject=data.get("subject", ""),
                description=data.get("description", ""),
                status=data.get("status", "pending"),
                blocks=data.get("blocks", []),
                blocked_by=data.get("blockedBy", []),
                owner=data.get("owner"),
                metadata=data.get("metadata"),
            ))
        return tasks

    def get_inbox(self, team_name: str, agent_name: str) -> list[InboxMessage]:
        """Read and parse an agent's inbox, classifying message types."""
        inbox_path = self.teams_base / team_name / "inboxes" / f"{agent_name}.json"
        data = self._read_json(inbox_path)
        if data is None or not isinstance(data, list):
            return []

        messages = []
        for msg in data:
            text = msg.get("text", "")
            message_type, parsed_content = self._parse_message_text(text)
            messages.append(InboxMessage(
                from_agent=msg.get("from", ""),
                text=text,
                timestamp=msg.get("timestamp", ""),
                color=msg.get("color"),
                read=msg.get("read", False),
                message_type=message_type,
                parsed_content=parsed_content,
                target_agent=agent_name,
            ))
        return messages

    def get_all_messages(self, team_name: str) -> list[InboxMessage]:
        """Aggregate all inboxes for a team, sorted by timestamp."""
        inboxes_dir = self.teams_base / team_name / "inboxes"
        if not inboxes_dir.exists():
            return []

        all_messages = []
        for path in inboxes_dir.iterdir():
            if not path.is_file() or path.suffix != ".json":
                continue
            agent_name = path.stem
            all_messages.extend(self.get_inbox(team_name, agent_name))

        return sorted(all_messages, key=lambda m: m.timestamp)

    def get_team_summary(self, team_name: str) -> Optional[TeamSummary]:
        """Build a summary with member count, task counts, and unread status."""
        config = self.get_team_config(team_name)
        if config is None:
            return None

        tasks = self.get_tasks(team_name)
        task_counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for t in tasks:
            if t.status in task_counts:
                task_counts[t.status] += 1

        all_messages = self.get_all_messages(team_name)
        has_unread = any(not m.read for m in all_messages)

        return TeamSummary(
            name=config.name,
            description=config.description,
            created_at=config.created_at,
            member_count=len(config.members),
            task_counts=task_counts,
            total_tasks=len(tasks),
            has_unread_messages=has_unread,
            members=config.members,
        )

    def _parse_message_text(self, text: str) -> tuple[str, Optional[dict]]:
        """Try to parse text as JSON and classify message type.

        Returns (message_type, parsed_content) or ("plain", None).
        """
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "type" in parsed:
                return (parsed["type"], parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        return ("plain", None)

    def _read_json(self, path: Path) -> Optional[dict | list]:
        """Read and parse a JSON file, returning None on any error."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", path, e)
            return None
