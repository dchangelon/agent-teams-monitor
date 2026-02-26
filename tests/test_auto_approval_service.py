"""Tests for the Auto-Approval Service."""

import json
from pathlib import Path

from src.message_writer import InboxWriter
from src.models import PermissionAlertResponse
from src.services.auto_approval_service import AutoApprovalService
from src.services.settings_service import SettingsService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_permission(
    request_id="perm-1",
    agent="agent-1",
    tool_name="Read",
    description="Read a file",
    timestamp="2026-02-14T19:00:00.000Z",
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


def _setup(tmp_path, enabled=True, tools=None):
    """Create settings service, writer, and auto-approval service for testing."""
    settings_path = tmp_path / "settings.json"
    teams_dir = tmp_path / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)

    svc = SettingsService(settings_path=settings_path)
    if tools is not None:
        svc.update(auto_approve_enabled=enabled, auto_approve_tools=tools)
    elif not enabled:
        svc.update(auto_approve_enabled=False)

    writer = InboxWriter(teams_base=teams_dir)

    # Create inbox for agent
    inbox_dir = teams_dir / "test-team" / "inboxes"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    (inbox_dir / "agent-1.json").write_text("[]", encoding="utf-8")

    auto = AutoApprovalService(settings_service=svc, writer=writer)
    return auto, svc, writer, teams_dir


def _read_inbox(teams_dir, team="test-team", agent="agent-1"):
    inbox_path = teams_dir / team / "inboxes" / f"{agent}.json"
    return json.loads(inbox_path.read_text(encoding="utf-8"))


class TestAutoApprovalMatching:
    def test_auto_approves_low_risk_tool(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path)
        perm = _make_permission(tool_name="Read")
        results = auto.process_permissions("test-team", [perm])

        assert len(results) == 1
        assert results[0].tool_name == "Read"
        assert results[0].request_id == "perm-1"

        # Verify inbox was written
        msgs = _read_inbox(teams_dir)
        assert len(msgs) == 1
        payload = json.loads(msgs[0]["text"])
        assert payload["type"] == "permission_response"
        assert payload["approved"] is True
        assert payload["request_id"] == "perm-1"

    def test_approves_multiple_low_risk(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path)
        perms = [
            _make_permission(request_id="p1", tool_name="Read"),
            _make_permission(request_id="p2", tool_name="Glob"),
            _make_permission(request_id="p3", tool_name="Grep"),
        ]
        results = auto.process_permissions("test-team", perms)
        assert len(results) == 3

    def test_does_not_approve_medium_risk(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path)
        perm = _make_permission(tool_name="Bash")
        results = auto.process_permissions("test-team", [perm])

        assert len(results) == 0
        msgs = _read_inbox(teams_dir)
        assert len(msgs) == 0

    def test_mixed_risk_levels(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path)
        perms = [
            _make_permission(request_id="p1", tool_name="Read"),
            _make_permission(request_id="p2", tool_name="Bash"),
            _make_permission(request_id="p3", tool_name="Glob"),
        ]
        results = auto.process_permissions("test-team", perms)
        assert len(results) == 2
        approved_tools = {r.tool_name for r in results}
        assert approved_tools == {"Read", "Glob"}


class TestAutoApprovalDisabled:
    def test_returns_empty_when_disabled(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path, enabled=False)
        perm = _make_permission(tool_name="Read")
        results = auto.process_permissions("test-team", [perm])
        assert len(results) == 0

    def test_no_inbox_writes_when_disabled(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path, enabled=False)
        perm = _make_permission(tool_name="Read")
        auto.process_permissions("test-team", [perm])
        msgs = _read_inbox(teams_dir)
        assert len(msgs) == 0


class TestAutoApprovalDedup:
    def test_same_request_only_processed_once(self, tmp_path):
        auto, _, _, teams_dir = _setup(tmp_path)
        perm = _make_permission(request_id="perm-dup")

        results1 = auto.process_permissions("test-team", [perm])
        results2 = auto.process_permissions("test-team", [perm])

        assert len(results1) == 1
        assert len(results2) == 0

        msgs = _read_inbox(teams_dir)
        assert len(msgs) == 1

    def test_different_requests_both_processed(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)

        results1 = auto.process_permissions(
            "test-team", [_make_permission(request_id="p1")]
        )
        results2 = auto.process_permissions(
            "test-team", [_make_permission(request_id="p2")]
        )

        assert len(results1) == 1
        assert len(results2) == 1


class TestAutoApprovalCustomTools:
    def test_custom_tool_list_respected(self, tmp_path):
        auto, _, _, teams_dir = _setup(
            tmp_path, tools=["Bash", "Write"]
        )

        perms = [
            _make_permission(request_id="p1", tool_name="Bash"),
            _make_permission(request_id="p2", tool_name="Read"),
        ]
        results = auto.process_permissions("test-team", perms)

        assert len(results) == 1
        assert results[0].tool_name == "Bash"

    def test_empty_tool_list_approves_nothing(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path, tools=[])
        perm = _make_permission(tool_name="Read")
        results = auto.process_permissions("test-team", [perm])
        assert len(results) == 0


class TestAutoApprovalLog:
    def test_log_populated(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        auto.process_permissions(
            "test-team", [_make_permission(request_id="p1")]
        )
        auto.process_permissions(
            "test-team", [_make_permission(request_id="p2")]
        )

        log = auto.get_log()
        assert len(log) == 2
        # Newest first
        assert log[0].request_id == "p2"
        assert log[1].request_id == "p1"

    def test_log_limit(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        for i in range(10):
            auto.process_permissions(
                "test-team",
                [_make_permission(request_id=f"p{i}")],
            )
        log = auto.get_log(limit=3)
        assert len(log) == 3

    def test_log_entry_fields(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        auto.process_permissions(
            "test-team",
            [_make_permission(
                request_id="p1", agent="agent-1",
                tool_name="Read", tool_use_id="toolu_01",
            )],
        )
        entry = auto.get_log()[0]
        assert entry.request_id == "p1"
        assert entry.agent_name == "agent-1"
        assert entry.tool_name == "Read"
        assert entry.tool_use_id == "toolu_01"
        assert entry.team_name == "test-team"
        assert entry.timestamp  # non-empty

    def test_get_recent_filters_by_time(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        auto.process_permissions(
            "test-team", [_make_permission(request_id="p1")]
        )
        # Recent entries should be returned (just created)
        recent = auto.get_recent(max_age_seconds=60)
        assert len(recent) >= 1

    def test_get_recent_respects_limit(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        for i in range(5):
            auto.process_permissions(
                "test-team",
                [_make_permission(request_id=f"p{i}")],
            )
        recent = auto.get_recent(max_age_seconds=300, limit=2)
        assert len(recent) == 2


class TestAutoApprovalSkipsEmptyRequestId:
    def test_skips_permission_with_empty_request_id(self, tmp_path):
        auto, _, _, _ = _setup(tmp_path)
        perm = _make_permission(request_id="")
        results = auto.process_permissions("test-team", [perm])
        assert len(results) == 0
