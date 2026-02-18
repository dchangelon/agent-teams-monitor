import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import TEAMS_DIR

logger = logging.getLogger(__name__)


class InboxWriter:
    def __init__(self, teams_base: Optional[Path] = None):
        self.teams_base = teams_base or TEAMS_DIR
        self._lock = threading.Lock()

    def send_message(
        self,
        team_name: str,
        agent_name: str,
        from_name: str,
        text: str,
        color: Optional[str] = None,
    ) -> bool:
        """Append a message to an agent's inbox file.

        Creates the inbox file (and parent dirs) if missing.
        Returns True on success, False on error.
        """
        inbox_path = self.teams_base / team_name / "inboxes" / f"{agent_name}.json"

        message = {
            "from": from_name,
            "text": text,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "read": False,
        }
        if color is not None:
            message["color"] = color

        with self._lock:
            try:
                inbox_path.parent.mkdir(parents=True, exist_ok=True)

                if inbox_path.exists():
                    messages = json.loads(inbox_path.read_text(encoding="utf-8"))
                    if not isinstance(messages, list):
                        messages = []
                else:
                    messages = []

                messages.append(message)
                inbox_path.write_text(
                    json.dumps(messages, indent=2),
                    encoding="utf-8",
                )
                return True
            except (OSError, json.JSONDecodeError) as e:
                logger.error("Failed to write to inbox %s: %s", inbox_path, e)
                return False

    def send_permission_response(
        self,
        team_name: str,
        agent_name: str,
        request_id: str,
        tool_use_id: str,
        approved: bool,
    ) -> bool:
        """Write a permission approval/denial to an agent's inbox."""
        response_payload = json.dumps({
            "type": "permission_response",
            "request_id": request_id,
            "tool_use_id": tool_use_id,
            "approved": approved,
        })
        return self.send_message(team_name, agent_name, "user", response_payload)


class ConfigWriter:
    """Read-modify-write operations on team config.json files."""

    def __init__(self, teams_base: Optional[Path] = None):
        self.teams_base = teams_base or TEAMS_DIR
        self._lock = threading.Lock()

    def remove_member(self, team_name: str, agent_name: str) -> bool:
        """Remove a member from config.json by name.

        Returns True on success, False if member not found or write error.
        """
        config_path = self.teams_base / team_name / "config.json"

        with self._lock:
            try:
                if not config_path.exists():
                    return False

                data = json.loads(config_path.read_text(encoding="utf-8"))
                members = data.get("members", [])

                original_count = len(members)
                members = [m for m in members if m.get("name") != agent_name]

                if len(members) == original_count:
                    return False  # Member not found

                data["members"] = members
                config_path.write_text(
                    json.dumps(data, indent=2),
                    encoding="utf-8",
                )
                return True
            except (OSError, json.JSONDecodeError) as e:
                logger.error("Failed to update config %s: %s", config_path, e)
                return False
