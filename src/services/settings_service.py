"""Settings Service — file-backed auto-approval configuration.

Stores settings at CLAUDE_HOME / "agent-monitor-settings.json".
Thread-safe reads/writes via threading.Lock.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import SETTINGS_PATH

logger = logging.getLogger(__name__)

DEFAULT_AUTO_APPROVE_TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]


@dataclass
class AutoApprovalSettings:
    auto_approve_enabled: bool = True
    auto_approve_tools: list[str] = field(
        default_factory=lambda: list(DEFAULT_AUTO_APPROVE_TOOLS)
    )


class SettingsService:
    """File-backed settings persistence.

    Parameters
    ----------
    settings_path : optional override for testing (default: SETTINGS_PATH)
    """

    def __init__(self, settings_path: Optional[Path] = None):
        self._path = settings_path or SETTINGS_PATH
        self._lock = threading.Lock()
        self._settings: AutoApprovalSettings = self._load()

    def get(self) -> AutoApprovalSettings:
        """Return current settings."""
        with self._lock:
            return AutoApprovalSettings(
                auto_approve_enabled=self._settings.auto_approve_enabled,
                auto_approve_tools=list(self._settings.auto_approve_tools),
            )

    def update(
        self,
        auto_approve_enabled: Optional[bool] = None,
        auto_approve_tools: Optional[list[str]] = None,
    ) -> AutoApprovalSettings:
        """Update settings and persist to disk. Returns updated settings."""
        with self._lock:
            if auto_approve_enabled is not None:
                self._settings.auto_approve_enabled = auto_approve_enabled
            if auto_approve_tools is not None:
                self._settings.auto_approve_tools = list(auto_approve_tools)
            self._save()
            return AutoApprovalSettings(
                auto_approve_enabled=self._settings.auto_approve_enabled,
                auto_approve_tools=list(self._settings.auto_approve_tools),
            )

    def _load(self) -> AutoApprovalSettings:
        """Load from disk or return defaults if file missing/corrupt."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                return AutoApprovalSettings(
                    auto_approve_enabled=data.get("auto_approve_enabled", True),
                    auto_approve_tools=data.get(
                        "auto_approve_tools", list(DEFAULT_AUTO_APPROVE_TOOLS)
                    ),
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load settings from %s: %s", self._path, e)
        return AutoApprovalSettings()

    def _save(self) -> None:
        """Write current settings to disk as JSON."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "auto_approve_enabled": self._settings.auto_approve_enabled,
                "auto_approve_tools": self._settings.auto_approve_tools,
            }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            logger.error("Failed to save settings to %s: %s", self._path, e)
