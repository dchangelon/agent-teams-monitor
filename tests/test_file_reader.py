import json

from src.file_reader import TeamFileReader


class TestListTeams:
    def test_returns_team_names(self, reader):
        teams = reader.list_teams()
        assert "test-team" in teams

    def test_includes_team_with_no_config(self, reader):
        teams = reader.list_teams()
        assert "broken-team" in teams

    def test_empty_dir_returns_empty(self, tmp_path):
        r = TeamFileReader(teams_base=tmp_path / "nonexistent", tasks_base=tmp_path)
        assert r.list_teams() == []


class TestGetTeamConfig:
    def test_parses_all_fields(self, reader):
        config = reader.get_team_config("test-team")
        assert config is not None
        assert config.name == "test-team"
        assert config.description == "Test team for unit tests"
        assert config.created_at == 1771096651149
        assert config.lead_agent_id == "team-lead@test-team"
        assert config.lead_session_id == "session-test-123"

    def test_parses_members(self, reader):
        config = reader.get_team_config("test-team")
        assert len(config.members) == 3
        lead = config.members[0]
        assert lead.agent_id == "team-lead@test-team"
        assert lead.name == "team-lead"
        assert lead.agent_type == "team-lead"
        assert lead.model == "claude-opus-4-6"
        assert lead.joined_at == 1771096651149
        assert lead.color is None
        assert lead.prompt is not None
        assert lead.backend_type == "in-process"

    def test_parses_member_with_color(self, reader):
        config = reader.get_team_config("test-team")
        agent_1 = config.members[1]
        assert agent_1.name == "agent-1"
        assert agent_1.color == "blue"
        assert agent_1.model == "opus"

    def test_returns_none_for_missing_team(self, reader):
        assert reader.get_team_config("nonexistent") is None

    def test_returns_none_for_team_without_config(self, reader):
        assert reader.get_team_config("broken-team") is None


class TestGetTasks:
    def test_parses_all_tasks(self, reader):
        tasks = reader.get_tasks("test-team")
        assert len(tasks) == 3

    def test_skips_lock_file(self, reader):
        tasks = reader.get_tasks("test-team")
        task_ids = [t.id for t in tasks]
        assert ".lock" not in task_ids

    def test_parses_task_fields(self, reader):
        tasks = reader.get_tasks("test-team")
        pending = next(t for t in tasks if t.id == "1")
        assert pending.subject == "setup-config"
        assert pending.status == "pending"
        assert pending.blocks == ["2"]
        assert pending.blocked_by == []
        assert pending.owner == "agent-1"

    def test_parses_blocked_by(self, reader):
        tasks = reader.get_tasks("test-team")
        in_progress = next(t for t in tasks if t.id == "2")
        assert in_progress.blocked_by == ["1"]
        assert in_progress.metadata == {"_internal": True}

    def test_empty_tasks_dir(self, reader):
        tasks = reader.get_tasks("empty-team")
        assert tasks == []

    def test_missing_team_returns_empty(self, reader):
        tasks = reader.get_tasks("nonexistent")
        assert tasks == []


class TestGetInbox:
    def test_parses_permission_request(self, reader):
        messages = reader.get_inbox("test-team", "agent-1")
        perm = next(m for m in messages if m.message_type == "permission_request")
        assert perm.from_agent == "agent-1"
        assert perm.color == "blue"
        assert perm.read is False
        assert perm.parsed_content is not None
        assert perm.parsed_content["tool_name"] == "Bash"
        assert perm.parsed_content["request_id"] == "perm-123-abc"

    def test_parses_shutdown_request(self, reader):
        messages = reader.get_inbox("test-team", "agent-1")
        shutdown = next(m for m in messages if m.message_type == "shutdown_request")
        assert shutdown.from_agent == "team-lead"
        assert shutdown.parsed_content["reason"] == "All tasks completed"

    def test_parses_plain_message(self, reader):
        messages = reader.get_inbox("test-team", "agent-1")
        plain = next(m for m in messages if m.message_type == "plain")
        assert plain.text == "Please focus on the unit tests first"
        assert plain.read is True
        assert plain.parsed_content is None

    def test_sets_target_agent(self, reader):
        messages = reader.get_inbox("test-team", "agent-1")
        assert all(m.target_agent == "agent-1" for m in messages)

    def test_empty_inbox(self, reader):
        messages = reader.get_inbox("test-team", "team-lead")
        assert messages == []

    def test_missing_inbox(self, reader):
        messages = reader.get_inbox("test-team", "nonexistent-agent")
        assert messages == []


class TestGetAllMessages:
    def test_aggregates_all_inboxes(self, reader):
        messages = reader.get_all_messages("test-team")
        assert len(messages) == 3  # agent-1 has 3 messages, team-lead has 0

    def test_sorted_by_timestamp(self, reader):
        messages = reader.get_all_messages("test-team")
        timestamps = [m.timestamp for m in messages]
        assert timestamps == sorted(timestamps)

    def test_target_agent_from_inbox_filename(self, reader):
        messages = reader.get_all_messages("test-team")
        assert all(m.target_agent == "agent-1" for m in messages)

    def test_missing_team_returns_empty(self, reader):
        messages = reader.get_all_messages("nonexistent")
        assert messages == []


class TestGetTeamSummary:
    def test_computes_correct_counts(self, reader):
        summary = reader.get_team_summary("test-team")
        assert summary is not None
        assert summary.task_counts["pending"] == 1
        assert summary.task_counts["in_progress"] == 1
        assert summary.task_counts["completed"] == 1
        assert summary.total_tasks == 3

    def test_member_count(self, reader):
        summary = reader.get_team_summary("test-team")
        assert summary.member_count == 3

    def test_has_unread_messages(self, reader):
        summary = reader.get_team_summary("test-team")
        assert summary.has_unread_messages is True

    def test_returns_none_for_team_without_config(self, reader):
        assert reader.get_team_summary("broken-team") is None


class TestParseMessageText:
    def test_permission_request(self, reader):
        text = json.dumps({"type": "permission_request", "request_id": "abc"})
        msg_type, content = reader._parse_message_text(text)
        assert msg_type == "permission_request"
        assert content["request_id"] == "abc"

    def test_shutdown_request(self, reader):
        text = json.dumps({"type": "shutdown_request", "reason": "done"})
        msg_type, content = reader._parse_message_text(text)
        assert msg_type == "shutdown_request"

    def test_plain_text(self, reader):
        msg_type, content = reader._parse_message_text("Hello world")
        assert msg_type == "plain"
        assert content is None

    def test_json_without_type_returns_plain(self, reader):
        text = json.dumps({"foo": "bar"})
        msg_type, content = reader._parse_message_text(text)
        assert msg_type == "plain"
        assert content is None

    def test_malformed_json(self, reader):
        msg_type, content = reader._parse_message_text("{bad json")
        assert msg_type == "plain"
        assert content is None


class TestMalformedData:
    def test_malformed_json_file(self, sample_teams_dir):
        """Malformed JSON in a task file is skipped gracefully."""
        bad_file = sample_teams_dir / "tasks" / "test-team" / "99.json"
        bad_file.write_text("{bad json content", encoding="utf-8")
        r = TeamFileReader(
            teams_base=sample_teams_dir / "teams",
            tasks_base=sample_teams_dir / "tasks",
        )
        tasks = r.get_tasks("test-team")
        # Should still get the 3 valid tasks, skipping the bad one
        assert len(tasks) == 3
        assert all(t.id != "99" for t in tasks)
