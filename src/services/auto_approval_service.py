"""Auto-Approval Service — automatically approves low-risk permission requests.

Runs server-side so agents get unblocked even when the dashboard is closed.
Maintains an in-memory log of auto-approved items (bounded, not persisted).
"""

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from ..message_writer import InboxWriter
from ..models import AutoApprovalLogEntry, PermissionAlertResponse
from .settings_service import SettingsService

logger = logging.getLogger(__name__)

MAX_LOG_ENTRIES = 500


class AutoApprovalService:
    """Processes pending permissions against auto-approval rules.

    Parameters
    ----------
    settings_service : SettingsService for reading current rules
    writer : InboxWriter for writing approval responses to agent inboxes
    """

    def __init__(self, settings_service: SettingsService, writer: InboxWriter):
        self._settings_service = settings_service
        self._writer = writer
        self._processed_ids: set[str] = set()
        self._log: deque[AutoApprovalLogEntry] = deque(maxlen=MAX_LOG_ENTRIES)
        self._lock = threading.Lock()

    def process_permissions(
        self,
        team_name: str,
        pending_permissions: list[PermissionAlertResponse],
    ) -> list[AutoApprovalLogEntry]:
        """Check pending permissions against rules, auto-approve matches.

        Returns list of newly auto-approved items this cycle.
        """
        settings = self._settings_service.get()
        if not settings.auto_approve_enabled:
            return []

        approved_tools = set(settings.auto_approve_tools)
        newly_approved: list[AutoApprovalLogEntry] = []

        for perm in pending_permissions:
            if not perm.request_id:
                continue

            with self._lock:
                if perm.request_id in self._processed_ids:
                    continue

            if perm.tool_name not in approved_tools:
                continue

            success = self._writer.send_permission_response(
                team_name,
                perm.agent_name,
                perm.request_id,
                perm.tool_use_id,
                approved=True,
            )
            if not success:
                logger.warning(
                    "Failed to auto-approve %s for %s/%s",
                    perm.tool_name, team_name, perm.agent_name,
                )
                continue

            entry = AutoApprovalLogEntry(
                request_id=perm.request_id,
                agent_name=perm.agent_name,
                tool_name=perm.tool_name,
                tool_use_id=perm.tool_use_id,
                team_name=team_name,
                timestamp=datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                ),
            )

            with self._lock:
                self._processed_ids.add(perm.request_id)
                self._log.appendleft(entry)

            newly_approved.append(entry)
            logger.info(
                "Auto-approved %s for %s/%s (request %s)",
                perm.tool_name, team_name, perm.agent_name, perm.request_id,
            )

        return newly_approved

    def get_log(self, limit: int = 50) -> list[AutoApprovalLogEntry]:
        """Return recent auto-approval log entries (newest first)."""
        with self._lock:
            return list(self._log)[:limit]

    def get_recent(
        self, max_age_seconds: int = 300, limit: int = 10
    ) -> list[AutoApprovalLogEntry]:
        """Return auto-approvals within the last N seconds."""
        now = datetime.now(timezone.utc)
        result: list[AutoApprovalLogEntry] = []
        with self._lock:
            for entry in self._log:
                try:
                    ts = datetime.fromisoformat(
                        entry.timestamp.replace(".000Z", "+00:00")
                    )
                    if (now - ts).total_seconds() > max_age_seconds:
                        break  # log is newest-first, so we can stop
                except (ValueError, TypeError):
                    continue
                result.append(entry)
                if len(result) >= limit:
                    break
        return result
