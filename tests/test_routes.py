import json

from fastapi.testclient import TestClient

from src.app import create_app
from src.config import STALL_THRESHOLD_MINUTES


class TestListTeams:
    def test_returns_team_summaries(self, client):
        resp = client.get("/api/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Only test-team has a config.json; broken-team is skipped
        assert len(data["teams"]) == 1
        team = data["teams"][0]
        assert team["name"] == "test-team"
        assert team["member_count"] == 3
        assert team["total_tasks"] == 3
        assert team["task_counts"]["pending"] == 1
        assert team["task_counts"]["in_progress"] == 1
        assert team["task_counts"]["completed"] == 1

    def test_skips_teams_without_config(self, client):
        resp = client.get("/api/teams")
        names = [t["name"] for t in resp.json()["teams"]]
        assert "broken-team" not in names


class TestGetTeam:
    def test_returns_config_with_members(self, client):
        resp = client.get("/api/teams/test-team")
        assert resp.status_code == 200
        data = resp.json()
        team = data["team"]
        assert team["name"] == "test-team"
        assert team["lead_agent_id"] == "team-lead@test-team"
        assert len(team["members"]) == 3

    def test_truncates_prompt(self, client):
        resp = client.get("/api/teams/test-team")
        members = resp.json()["team"]["members"]
        for m in members:
            if m["prompt"] is not None:
                assert len(m["prompt"]) <= 200

    def test_404_for_missing_team(self, client):
        resp = client.get("/api/teams/nonexistent")
        assert resp.status_code == 404


class TestGetTasks:
    def test_returns_tasks_with_counts(self, client):
        resp = client.get("/api/teams/test-team/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 3
        assert data["counts"]["pending"] == 1
        assert data["counts"]["in_progress"] == 1
        assert data["counts"]["completed"] == 1
        assert data["counts"]["total"] == 3

    def test_enriches_is_internal(self, client):
        resp = client.get("/api/teams/test-team/tasks")
        tasks = resp.json()["tasks"]
        internal_task = next(t for t in tasks if t["id"] == "2")
        assert internal_task["is_internal"] is True
        non_internal = next(t for t in tasks if t["id"] == "1")
        assert non_internal["is_internal"] is False

    def test_status_duration_populated_on_second_call(self, client):
        # First call seeds the tracker
        client.get("/api/teams/test-team/tasks")
        # Second call — no status change, but duration should be set
        resp = client.get("/api/teams/test-team/tasks")
        tasks = resp.json()["tasks"]
        # All tasks were observed on first poll, so duration should be >= 0
        for t in tasks:
            assert t["status_duration_seconds"] is not None
            assert t["status_duration_seconds"] >= 0

    def test_empty_tasks(self, client):
        resp = client.get("/api/teams/empty-team/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []
        assert resp.json()["counts"]["total"] == 0


class TestGetMessages:
    def test_returns_sorted_messages(self, client):
        resp = client.get("/api/teams/test-team/messages")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 3
        # Verify sorted by timestamp (ascending)
        timestamps = [m["timestamp"] for m in messages]
        assert timestamps == sorted(timestamps)

    def test_message_types(self, client):
        resp = client.get("/api/teams/test-team/messages")
        messages = resp.json()["messages"]
        types = {m["message_type"] for m in messages}
        assert "permission_request" in types
        assert "shutdown_request" in types
        assert "plain" in types

    def test_target_agent_set(self, client):
        resp = client.get("/api/teams/test-team/messages")
        messages = resp.json()["messages"]
        assert all(m["target_agent"] is not None for m in messages)


class TestGetTimeline:
    def test_returns_events_after_tasks_polled(self, client):
        # First, poll tasks to seed timeline
        client.get("/api/teams/test-team/tasks")
        resp = client.get("/api/teams/test-team/timeline")
        assert resp.status_code == 200
        events = resp.json()["events"]
        # 3 tasks observed on first poll → 3 events
        assert len(events) == 3

    def test_events_newest_first(self, client):
        client.get("/api/teams/test-team/tasks")
        resp = client.get("/api/teams/test-team/timeline")
        events = resp.json()["events"]
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_respects_limit(self, client):
        client.get("/api/teams/test-team/tasks")
        resp = client.get("/api/teams/test-team/timeline?limit=1")
        assert len(resp.json()["events"]) == 1

    def test_empty_without_polling(self, client):
        resp = client.get("/api/teams/test-team/timeline")
        assert resp.json()["events"] == []


class TestGetActivity:
    def test_returns_per_agent_activity(self, client):
        resp = client.get("/api/teams/test-team/activity")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert len(agents) == 3  # 3 members in test config
        names = {a["name"] for a in agents}
        assert "team-lead" in names
        assert "agent-1" in names
        assert "agent-2" in names

    def test_task_counts_per_agent(self, client):
        resp = client.get("/api/teams/test-team/activity")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        # agent-1 owns tasks 1 (pending) and 2 (in_progress)
        assert agents["agent-1"]["tasks_pending"] == 1
        assert agents["agent-1"]["tasks_in_progress"] == 1
        # agent-2 owns task 3 (completed)
        assert agents["agent-2"]["tasks_completed"] == 1

    def test_message_counts(self, client):
        resp = client.get("/api/teams/test-team/activity")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        # agent-1's inbox has 3 messages (received), and agent-1 sent 1 (permission_request from agent-1)
        assert agents["agent-1"]["messages_sent"] == 1
        assert agents["agent-1"]["messages_received"] == 3

    def test_includes_model_and_type(self, client):
        resp = client.get("/api/teams/test-team/activity")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        assert agents["team-lead"]["model"] == "claude-opus-4-6"
        assert agents["agent-1"]["agent_type"] == "general-purpose"

    def test_agent_status_field_present(self, client):
        resp = client.get("/api/teams/test-team/activity")
        agents = resp.json()["agents"]
        for agent in agents:
            assert agent["agent_status"] in ("active", "idle", "completed", "stalled")

    def test_agent_with_shutdown_and_pending_work_is_stalled(self, client):
        resp = client.get("/api/teams/test-team/activity")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        # agent-1 has a shutdown_request AND pending/in-progress tasks
        assert agents["agent-1"]["agent_status"] == "stalled"

    def test_agent_with_shutdown_and_no_work_is_completed(self, client, sample_teams_dir):
        # agent-2 has completed tasks and no pending work; add a shutdown to its inbox
        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-2.json"
        import json
        inbox_path.write_text(json.dumps([{
            "from": "team-lead",
            "text": '{"type":"shutdown_request","reason":"done","requestId":"sd-1"}',
            "timestamp": "2026-02-14T21:00:00.000Z",
            "read": False,
        }]), encoding="utf-8")
        resp = client.get("/api/teams/test-team/activity")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        assert agents["agent-2"]["agent_status"] == "completed"


class TestGetAgentTimeline:
    def test_returns_agent_entries(self, client):
        resp = client.get("/api/teams/test-team/agent-timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_name"] == "test-team"
        assert len(data["agents"]) == 3

    def test_agents_sorted_by_joined_at(self, client):
        resp = client.get("/api/teams/test-team/agent-timeline")
        agents = resp.json()["agents"]
        joined_ats = [a["joined_at"] for a in agents]
        assert joined_ats == sorted(joined_ats)

    def test_each_agent_has_joined_event(self, client):
        resp = client.get("/api/teams/test-team/agent-timeline")
        for agent in resp.json()["agents"]:
            event_types = [e["event_type"] for e in agent["events"]]
            assert "joined" in event_types

    def test_shutdown_detected_from_messages(self, client):
        resp = client.get("/api/teams/test-team/agent-timeline")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        # agent-1's inbox has a shutdown_request from team-lead
        agent_1 = agents["agent-1"]
        event_types = [e["event_type"] for e in agent_1["events"]]
        assert "shutdown_requested" in event_types

    def test_404_for_missing_team(self, client):
        resp = client.get("/api/teams/nonexistent/agent-timeline")
        assert resp.status_code == 404


class TestGetAlerts:
    def test_returns_pending_permissions(self, client):
        resp = client.get("/api/teams/test-team/alerts")
        assert resp.status_code == 200
        perms = resp.json()["pending_permissions"]
        assert len(perms) == 1
        assert perms[0]["agent_name"] == "agent-1"
        assert perms[0]["tool_name"] == "Bash"
        assert perms[0]["request_id"] == "perm-123-abc"

    def test_approved_permission_not_returned(self, client):
        """After approving a permission, alerts should not include it."""
        resp = client.get("/api/teams/test-team/alerts")
        assert len(resp.json()["pending_permissions"]) == 1
        perm = resp.json()["pending_permissions"][0]

        client.post(
            f"/api/teams/test-team/permissions/{perm['agent_name']}/approve",
            json={"request_id": perm["request_id"], "tool_use_id": perm["tool_use_id"]},
        )

        resp = client.get("/api/teams/test-team/alerts")
        assert len(resp.json()["pending_permissions"]) == 0

    def test_denied_permission_not_returned(self, client, sample_teams_dir):
        """After denying a permission, alerts should not include it."""
        resp = client.get("/api/teams/test-team/alerts")
        perm = resp.json()["pending_permissions"][0]

        client.post(
            f"/api/teams/test-team/permissions/{perm['agent_name']}/deny",
            json={"request_id": perm["request_id"], "tool_use_id": perm["tool_use_id"]},
        )

        resp = client.get("/api/teams/test-team/alerts")
        assert len(resp.json()["pending_permissions"]) == 0

    def test_stalled_agents_initially_empty_or_present(self, client):
        resp = client.get("/api/teams/test-team/alerts")
        # Stalled agents depend on message timestamps being old enough
        # Our fixture messages are from 2026-02-14, which is in the past
        stalled = resp.json()["stalled_agents"]
        assert isinstance(stalled, list)


class TestGetSnapshot:
    def test_returns_consolidated_detail_payload(self, client):
        resp = client.get("/api/teams/test-team/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["team"]["name"] == "test-team"
        assert "counts" in data
        assert "activity" in data
        assert "pending_permissions" in data
        assert data["monitor_config"]["stall_threshold_minutes"] == STALL_THRESHOLD_MINUTES


class TestSendMessage:
    def test_writes_to_inbox(self, client, sample_teams_dir):
        resp = client.post(
            "/api/teams/test-team/messages/agent-1",
            json={"text": "Hello from test"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert messages[-1]["text"] == "Hello from test"
        assert messages[-1]["from"] == "user"

    def test_custom_from_name(self, client, sample_teams_dir):
        resp = client.post(
            "/api/teams/test-team/messages/agent-1",
            json={"text": "test", "from_name": "admin"},
        )
        assert resp.status_code == 200

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        assert messages[-1]["from"] == "admin"


class TestPermissionEndpoints:
    def test_approve_writes_to_inbox(self, client, sample_teams_dir):
        resp = client.post(
            "/api/teams/test-team/permissions/agent-1/approve",
            json={"request_id": "perm-123", "tool_use_id": "toolu_ABC"},
        )
        assert resp.status_code == 200

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        payload = json.loads(messages[-1]["text"])
        assert payload["type"] == "permission_response"
        assert payload["approved"] is True

    def test_deny_writes_to_inbox(self, client, sample_teams_dir):
        resp = client.post(
            "/api/teams/test-team/permissions/agent-1/deny",
            json={"request_id": "perm-456", "tool_use_id": "toolu_XYZ"},
        )
        assert resp.status_code == 200

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        payload = json.loads(messages[-1]["text"])
        assert payload["approved"] is False


class TestValidation:
    def test_missing_text_returns_422(self, client):
        resp = client.post(
            "/api/teams/test-team/messages/agent-1",
            json={},
        )
        assert resp.status_code == 422

    def test_missing_request_id_returns_422(self, client):
        resp = client.post(
            "/api/teams/test-team/permissions/agent-1/approve",
            json={"tool_use_id": "toolu_ABC"},
        )
        assert resp.status_code == 422

    def test_invalid_team_name_returns_400(self, client):
        resp = client.get("/api/teams/bad.team/tasks")
        assert resp.status_code == 400

    def test_invalid_agent_name_returns_400(self, client):
        resp = client.post(
            "/api/teams/test-team/messages/bad.agent",
            json={"text": "test"},
        )
        assert resp.status_code == 400


class TestWriteAccessControl:
    def test_write_endpoint_requires_api_key_when_configured(self, sample_teams_dir):
        app = create_app(
            teams_dir=sample_teams_dir / "teams",
            tasks_dir=sample_teams_dir / "tasks",
            write_api_key="secret-key",
        )
        client = TestClient(app)
        resp = client.post(
            "/api/teams/test-team/messages/agent-1",
            json={"text": "hi"},
        )
        assert resp.status_code == 401

    def test_write_endpoint_accepts_valid_api_key(self, sample_teams_dir):
        app = create_app(
            teams_dir=sample_teams_dir / "teams",
            tasks_dir=sample_teams_dir / "tasks",
            write_api_key="secret-key",
        )
        client = TestClient(app)
        resp = client.post(
            "/api/teams/test-team/messages/agent-1",
            json={"text": "hi"},
            headers={"X-API-Key": "secret-key"},
        )
        assert resp.status_code == 200


class TestRemoveMember:
    def test_removes_member_from_config(self, client, sample_teams_dir):
        resp = client.post("/api/teams/test-team/members/agent-2/remove")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        config_path = sample_teams_dir / "teams" / "test-team" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        names = [m["name"] for m in config["members"]]
        assert "agent-2" not in names
        assert "team-lead" in names
        assert "agent-1" in names

    def test_404_for_missing_team(self, client):
        resp = client.post("/api/teams/nonexistent/members/agent-1/remove")
        assert resp.status_code == 404

    def test_404_for_missing_member(self, client):
        resp = client.post("/api/teams/test-team/members/nobody/remove")
        assert resp.status_code == 404

    def test_cannot_remove_team_lead(self, client):
        resp = client.post("/api/teams/test-team/members/team-lead/remove")
        assert resp.status_code == 400
        assert "team lead" in resp.json()["detail"].lower()

    def test_activity_reflects_removal(self, client):
        """After removing a member, activity endpoint should not include them."""
        client.post("/api/teams/test-team/members/agent-2/remove")
        resp = client.get("/api/teams/test-team/activity")
        names = [a["name"] for a in resp.json()["agents"]]
        assert "agent-2" not in names


class TestDashboard:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Agent Teams Monitor" in resp.text
