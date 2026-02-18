import json
import threading

from src.message_writer import ConfigWriter, InboxWriter


class TestSendMessage:
    def test_appends_to_existing_inbox(self, writer, sample_teams_dir):
        # agent-1 already has 3 messages in fixture
        result = writer.send_message("test-team", "agent-1", "user", "Hello agent")
        assert result is True

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert len(messages) == 4  # 3 original + 1 new
        assert messages[-1]["from"] == "user"
        assert messages[-1]["text"] == "Hello agent"
        assert messages[-1]["read"] is False

    def test_creates_inbox_if_missing(self, writer, sample_teams_dir):
        result = writer.send_message("test-team", "new-agent", "user", "First message")
        assert result is True

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "new-agent.json"
        assert inbox_path.exists()
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert len(messages) == 1
        assert messages[0]["text"] == "First message"

    def test_includes_iso_timestamp(self, writer, sample_teams_dir):
        writer.send_message("test-team", "agent-1", "user", "test")

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        ts = messages[-1]["timestamp"]
        # Should be ISO 8601 format
        assert "T" in ts
        assert ts.endswith("Z")

    def test_includes_color_when_provided(self, writer, sample_teams_dir):
        writer.send_message("test-team", "agent-1", "user", "test", color="blue")

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert messages[-1]["color"] == "blue"

    def test_omits_color_when_none(self, writer, sample_teams_dir):
        writer.send_message("test-team", "agent-1", "user", "test")

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert "color" not in messages[-1]


class TestSendPermissionResponse:
    def test_writes_permission_response(self, writer, sample_teams_dir):
        result = writer.send_permission_response(
            "test-team", "agent-1", "perm-123", "toolu_ABC", approved=True,
        )
        assert result is True

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        last_msg = messages[-1]
        assert last_msg["from"] == "user"

        payload = json.loads(last_msg["text"])
        assert payload["type"] == "permission_response"
        assert payload["request_id"] == "perm-123"
        assert payload["tool_use_id"] == "toolu_ABC"
        assert payload["approved"] is True

    def test_denial_response(self, writer, sample_teams_dir):
        writer.send_permission_response(
            "test-team", "agent-1", "perm-456", "toolu_XYZ", approved=False,
        )

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        payload = json.loads(messages[-1]["text"])
        assert payload["approved"] is False


class TestConcurrentWrites:
    def test_no_corruption(self, sample_teams_dir):
        writer = InboxWriter(teams_base=sample_teams_dir / "teams")
        errors = []

        def write_message(i):
            try:
                writer.send_message("test-team", "team-lead", "user", f"msg-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_message, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "team-lead.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        # team-lead started with 0 messages, should now have 10
        assert len(messages) == 10


class TestConfigWriter:
    def test_removes_member_by_name(self, sample_teams_dir):
        cw = ConfigWriter(teams_base=sample_teams_dir / "teams")
        result = cw.remove_member("test-team", "agent-2")
        assert result is True

        config_path = sample_teams_dir / "teams" / "test-team" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        names = [m["name"] for m in config["members"]]
        assert "agent-2" not in names
        assert len(config["members"]) == 2

    def test_returns_false_for_nonexistent_member(self, sample_teams_dir):
        cw = ConfigWriter(teams_base=sample_teams_dir / "teams")
        result = cw.remove_member("test-team", "nobody")
        assert result is False

    def test_returns_false_for_missing_team(self, sample_teams_dir):
        cw = ConfigWriter(teams_base=sample_teams_dir / "teams")
        result = cw.remove_member("nonexistent", "agent-1")
        assert result is False

    def test_preserves_other_fields(self, sample_teams_dir):
        cw = ConfigWriter(teams_base=sample_teams_dir / "teams")
        cw.remove_member("test-team", "agent-2")

        config_path = sample_teams_dir / "teams" / "test-team" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["name"] == "test-team"
        assert config["description"] == "Test team for unit tests"
        assert config["leadAgentId"] == "team-lead@test-team"
