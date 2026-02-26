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

    def test_teams_include_health_score(self, client):
        resp = client.get("/api/teams")
        team = resp.json()["teams"][0]
        assert "health_score" in team
        assert "health_color" in team
        assert isinstance(team["health_score"], int)
        assert 0 <= team["health_score"] <= 100
        assert team["health_color"] in ("green", "amber", "red")


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


class TestUnresolvedFilter:
    """Test the ?unresolved=true query parameter on the messages endpoint."""

    @staticmethod
    def _write_rich_inbox(sample_teams_dir):
        """Write inbox with both resolved and unresolved items."""
        inbox_path = (
            sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        )
        inbox_path.write_text(json.dumps([
            # Resolved permission: perm-AAA has a matching response
            {
                "from": "agent-1",
                "text": json.dumps({
                    "type": "permission_request",
                    "request_id": "perm-AAA",
                    "tool_name": "Read",
                    "tool_use_id": "toolu_AAA",
                    "description": "Read config",
                }),
                "timestamp": "2026-02-14T19:00:00.000Z",
                "color": "blue",
                "read": False,
            },
            {
                "from": "team-lead",
                "text": json.dumps({
                    "type": "permission_response",
                    "request_id": "perm-AAA",
                    "approved": True,
                }),
                "timestamp": "2026-02-14T19:01:00.000Z",
                "color": None,
                "read": False,
            },
            # Unresolved permission: perm-BBB has no response
            {
                "from": "agent-1",
                "text": json.dumps({
                    "type": "permission_request",
                    "request_id": "perm-BBB",
                    "tool_name": "Bash",
                    "tool_use_id": "toolu_BBB",
                    "description": "Run tests",
                }),
                "timestamp": "2026-02-14T19:10:00.000Z",
                "color": "blue",
                "read": False,
            },
            # Resolved shutdown: shutdown-CCC has a response
            {
                "from": "team-lead",
                "text": json.dumps({
                    "type": "shutdown_request",
                    "reason": "Phase done",
                    "requestId": "shutdown-CCC",
                }),
                "timestamp": "2026-02-14T19:20:00.000Z",
                "color": None,
                "read": False,
            },
            {
                "from": "agent-1",
                "text": json.dumps({
                    "type": "shutdown_response",
                    "requestId": "shutdown-CCC",
                    "approve": True,
                }),
                "timestamp": "2026-02-14T19:21:00.000Z",
                "color": "blue",
                "read": False,
            },
            # Unresolved shutdown: shutdown-DDD has no response
            {
                "from": "team-lead",
                "text": json.dumps({
                    "type": "shutdown_request",
                    "reason": "Final shutdown",
                    "requestId": "shutdown-DDD",
                }),
                "timestamp": "2026-02-14T19:30:00.000Z",
                "color": None,
                "read": False,
            },
            # Plain message (excluded by unresolved filter)
            {
                "from": "team-lead",
                "text": "Keep up the good work",
                "timestamp": "2026-02-14T19:05:00.000Z",
                "color": None,
                "read": True,
            },
        ]), encoding="utf-8")

    def test_unresolved_returns_only_unresolved_items(self, client, sample_teams_dir):
        self._write_rich_inbox(sample_teams_dir)
        resp = client.get("/api/teams/test-team/messages?unresolved=true")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        types = {m["message_type"] for m in messages}
        assert "permission_request" in types
        assert "shutdown_request" in types

    def test_unresolved_excludes_resolved_permissions(self, client, sample_teams_dir):
        self._write_rich_inbox(sample_teams_dir)
        resp = client.get("/api/teams/test-team/messages?unresolved=true")
        messages = resp.json()["messages"]
        perm_ids = [
            m["parsed_content"]["request_id"]
            for m in messages
            if m["message_type"] == "permission_request"
        ]
        assert "perm-AAA" not in perm_ids
        assert "perm-BBB" in perm_ids

    def test_unresolved_excludes_resolved_shutdowns(self, client, sample_teams_dir):
        self._write_rich_inbox(sample_teams_dir)
        resp = client.get("/api/teams/test-team/messages?unresolved=true")
        messages = resp.json()["messages"]
        shutdown_ids = [
            m["parsed_content"].get("requestId", "")
            for m in messages
            if m["message_type"] == "shutdown_request"
        ]
        assert "shutdown-CCC" not in shutdown_ids
        assert "shutdown-DDD" in shutdown_ids

    def test_unresolved_excludes_plain_messages(self, client, sample_teams_dir):
        self._write_rich_inbox(sample_teams_dir)
        resp = client.get("/api/teams/test-team/messages?unresolved=true")
        messages = resp.json()["messages"]
        plain = [m for m in messages if m["message_type"] == "plain"]
        assert len(plain) == 0

    def test_unresolved_false_returns_all(self, client, sample_teams_dir):
        self._write_rich_inbox(sample_teams_dir)
        resp = client.get("/api/teams/test-team/messages?unresolved=false")
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) == 7

    def test_no_param_returns_all(self, client):
        """Default behavior unchanged — returns all messages."""
        resp = client.get("/api/teams/test-team/messages")
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) == 3


class TestGroupByPair:
    """Test the ?group_by=pair query parameter on the messages endpoint."""

    def test_group_by_pair_returns_grouped_response(self, client):
        resp = client.get("/api/teams/test-team/messages?group_by=pair")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert isinstance(data["groups"], list)

    def test_group_by_pair_groups_are_canonical(self, client):
        resp = client.get("/api/teams/test-team/messages?group_by=pair")
        groups = resp.json()["groups"]
        for group in groups:
            pair = group["pair"]
            assert pair == sorted(pair)

    def test_group_by_pair_has_message_count(self, client):
        resp = client.get("/api/teams/test-team/messages?group_by=pair")
        groups = resp.json()["groups"]
        for group in groups:
            assert group["message_count"] == len(group["messages"])
            assert group["message_count"] > 0

    def test_group_by_pair_total_messages_match(self, client):
        """Sum of grouped messages equals total flat messages."""
        flat_resp = client.get("/api/teams/test-team/messages")
        total_flat = len(flat_resp.json()["messages"])
        grouped_resp = client.get("/api/teams/test-team/messages?group_by=pair")
        total_grouped = sum(
            g["message_count"] for g in grouped_resp.json()["groups"]
        )
        assert total_flat == total_grouped

    def test_group_by_pair_bidirectional_same_group(self, client, sample_teams_dir):
        """Messages from A->B and B->A should be in the same group."""
        # Add a message from agent-1 in team-lead's inbox (agent-1 → team-lead)
        inbox_path = (
            sample_teams_dir / "teams" / "test-team" / "inboxes" / "team-lead.json"
        )
        inbox_path.write_text(json.dumps([{
            "from": "agent-1",
            "text": "Hello team lead",
            "timestamp": "2026-02-14T18:00:00.000Z",
            "color": "blue",
            "read": False,
        }]), encoding="utf-8")
        resp = client.get("/api/teams/test-team/messages?group_by=pair")
        groups = resp.json()["groups"]
        # Find the agent-1 <-> team-lead group
        pair_group = [
            g for g in groups if set(g["pair"]) == {"agent-1", "team-lead"}
        ]
        assert len(pair_group) == 1
        # Should contain messages from both directions
        from_agents = {m["from_agent"] for m in pair_group[0]["messages"]}
        assert "agent-1" in from_agents
        assert "team-lead" in from_agents

    def test_combining_unresolved_and_group_by_pair(self, client):
        """?unresolved=true&group_by=pair should filter first, then group."""
        resp = client.get(
            "/api/teams/test-team/messages?unresolved=true&group_by=pair"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        # Default fixture: 1 unresolved perm + 1 unresolved shutdown = 2 items
        total = sum(g["message_count"] for g in data["groups"])
        assert total == 2


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


class TestGetHealth:
    def test_returns_health_score(self, client):
        resp = client.get("/api/teams/test-team/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        health = data["health"]
        assert 0 <= health["overall"] <= 100
        assert health["color"] in ("green", "amber", "red")
        assert health["label"] in ("Healthy", "Needs Attention", "Critical")
        assert len(health["dimensions"]) == 4

    def test_health_dimensions_have_required_fields(self, client):
        resp = client.get("/api/teams/test-team/health")
        for dim in resp.json()["health"]["dimensions"]:
            assert "name" in dim
            assert "score" in dim
            assert "weight" in dim
            assert "explanation" in dim
            assert 0 <= dim["score"] <= 100

    def test_404_for_missing_team(self, client):
        resp = client.get("/api/teams/nonexistent/health")
        assert resp.status_code == 404


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

    def test_snapshot_includes_action_queue(self, client):
        resp = client.get("/api/teams/test-team/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "action_queue" in data
        assert isinstance(data["action_queue"], list)
        # Fixture has 1 pending permission → at least 1 queue item
        assert len(data["action_queue"]) >= 1
        item = data["action_queue"][0]
        assert "id" in item
        assert "category" in item
        assert "priority" in item
        assert "title" in item

    def test_snapshot_includes_health_score(self, client):
        resp = client.get("/api/teams/test-team/snapshot")
        data = resp.json()
        assert "health_score" in data
        assert "health_color" in data
        assert "health" in data
        assert isinstance(data["health_score"], int)
        assert 0 <= data["health_score"] <= 100
        assert data["health_color"] in ("green", "amber", "red")
        assert len(data["health"]["dimensions"]) == 4


class TestGetActionQueue:
    def test_returns_action_queue_items(self, client):
        resp = client.get("/api/teams/test-team/action-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["items"], list)
        assert data["total"] == len(data["items"])

    def test_includes_pending_permission(self, client):
        """Fixture has one unresolved permission_request → should appear."""
        resp = client.get("/api/teams/test-team/action-queue")
        items = resp.json()["items"]
        perm_items = [i for i in items if i["category"] == "permission"]
        assert len(perm_items) == 1
        assert perm_items[0]["permission_data"]["request_id"] == "perm-123-abc"
        assert perm_items[0]["permission_data"]["tool_name"] == "Bash"

    def test_permission_disappears_after_approval(self, client):
        resp = client.get("/api/teams/test-team/action-queue")
        perm = [i for i in resp.json()["items"] if i["category"] == "permission"][0]
        pd = perm["permission_data"]

        client.post(
            f"/api/teams/test-team/permissions/{perm['agent_name']}/approve",
            json={"request_id": pd["request_id"], "tool_use_id": pd["tool_use_id"]},
        )

        resp = client.get("/api/teams/test-team/action-queue")
        perm_items = [i for i in resp.json()["items"] if i["category"] == "permission"]
        assert len(perm_items) == 0

    def test_404_for_missing_team(self, client):
        resp = client.get("/api/teams/nonexistent/action-queue")
        assert resp.status_code == 404

    def test_items_sorted_by_priority(self, client):
        resp = client.get("/api/teams/test-team/action-queue")
        items = resp.json()["items"]
        if len(items) > 1:
            priority_order = {"critical": 0, "high": 1, "normal": 2}
            priorities = [priority_order.get(i["priority"], 99) for i in items]
            assert priorities == sorted(priorities)


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


class TestBatchPermissions:
    def test_batch_approve_multiple(self, client, sample_teams_dir):
        """Send 2 approvals in one batch — both succeed."""
        resp = client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "agent-1", "request_id": "perm-1", "tool_use_id": "toolu_1", "action": "approve"},
                    {"agent_name": "agent-2", "request_id": "perm-2", "tool_use_id": "toolu_2", "action": "approve"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0

        # Verify inbox entries were written
        for agent in ("agent-1", "agent-2"):
            inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / f"{agent}.json"
            messages = json.loads(inbox_path.read_text(encoding="utf-8"))
            payload = json.loads(messages[-1]["text"])
            assert payload["type"] == "permission_response"
            assert payload["approved"] is True

    def test_batch_mixed_actions(self, client, sample_teams_dir):
        """1 approve + 1 deny in same batch."""
        resp = client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "agent-1", "request_id": "perm-a", "tool_use_id": "toolu_a", "action": "approve"},
                    {"agent_name": "agent-1", "request_id": "perm-b", "tool_use_id": "toolu_b", "action": "deny"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 2

        inbox_path = sample_teams_dir / "teams" / "test-team" / "inboxes" / "agent-1.json"
        messages = json.loads(inbox_path.read_text(encoding="utf-8"))
        # Last two messages should be the approve and deny
        approve_payload = json.loads(messages[-2]["text"])
        deny_payload = json.loads(messages[-1]["text"])
        assert approve_payload["approved"] is True
        assert deny_payload["approved"] is False

    def test_batch_empty_actions(self, client):
        """Empty actions list returns success with zero counts."""
        resp = client.post(
            "/api/teams/test-team/permissions/batch",
            json={"actions": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["succeeded"] == 0
        assert data["failed"] == 0

    def test_batch_invalid_action(self, client):
        """Invalid action value returns 422."""
        resp = client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "agent-1", "request_id": "p1", "tool_use_id": "t1", "action": "maybe"},
                ]
            },
        )
        assert resp.status_code == 422

    def test_batch_requires_api_key(self, sample_teams_dir):
        """Batch endpoint requires API key when configured."""
        app = create_app(
            teams_dir=sample_teams_dir / "teams",
            tasks_dir=sample_teams_dir / "tasks",
            write_api_key="secret-key",
            settings_path=sample_teams_dir / "settings.json",
        )
        key_client = TestClient(app)
        resp = key_client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "agent-1", "request_id": "p1", "tool_use_id": "t1", "action": "approve"},
                ]
            },
        )
        assert resp.status_code == 401

    def test_batch_with_valid_api_key(self, sample_teams_dir):
        """Batch endpoint succeeds with correct API key."""
        app = create_app(
            teams_dir=sample_teams_dir / "teams",
            tasks_dir=sample_teams_dir / "tasks",
            write_api_key="secret-key",
            settings_path=sample_teams_dir / "settings.json",
        )
        key_client = TestClient(app)
        resp = key_client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "agent-1", "request_id": "p1", "tool_use_id": "t1", "action": "approve"},
                ]
            },
            headers={"X-API-Key": "secret-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["succeeded"] == 1

    def test_batch_invalid_agent_name(self, client):
        """Invalid agent name in batch returns 400."""
        resp = client.post(
            "/api/teams/test-team/permissions/batch",
            json={
                "actions": [
                    {"agent_name": "bad.agent", "request_id": "p1", "tool_use_id": "t1", "action": "approve"},
                ]
            },
        )
        assert resp.status_code == 400


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
            settings_path=sample_teams_dir / "settings.json",
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
            settings_path=sample_teams_dir / "settings.json",
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


class TestSettingsEndpoints:
    def test_get_default_settings(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["auto_approve_enabled"] is True
        assert isinstance(data["auto_approve_tools"], list)
        assert "Read" in data["auto_approve_tools"]

    def test_update_settings(self, client):
        resp = client.put(
            "/api/settings",
            json={
                "auto_approve_enabled": False,
                "auto_approve_tools": ["Bash"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_approve_enabled"] is False
        assert data["auto_approve_tools"] == ["Bash"]

        # Verify persistence
        resp2 = client.get("/api/settings")
        assert resp2.json()["auto_approve_enabled"] is False
        assert resp2.json()["auto_approve_tools"] == ["Bash"]

    def test_partial_update(self, client):
        resp = client.put(
            "/api/settings",
            json={"auto_approve_enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_approve_enabled"] is False
        # Tools should still have defaults
        assert len(data["auto_approve_tools"]) > 0


class TestAutoApprovalsLog:
    def test_empty_log_initially(self, client):
        resp = client.get("/api/auto-approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["entries"] == []

    def test_log_respects_limit(self, client):
        resp = client.get("/api/auto-approvals?limit=5")
        assert resp.status_code == 200


class TestSnapshotAutoApproval:
    def test_snapshot_includes_auto_approval_fields(self, client):
        resp = client.get("/api/teams/test-team/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "auto_approve_enabled" in data
        assert "recent_auto_approvals" in data
        assert isinstance(data["recent_auto_approvals"], list)


class TestDashboard:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Agent Teams Monitor" in resp.text
