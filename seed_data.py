"""Generate realistic mock data for the Agent Teams Monitor dashboard.

Usage:
    python seed_data.py              # Writes to ~/.claude/teams/ and ~/.claude/tasks/
    python seed_data.py --output-dir ./test-data
    python seed_data.py --clean      # Remove seed data only
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEAM_NAME = "dashboard-redesign"


def now_utc():
    return datetime.now(timezone.utc)


def to_ms(dt):
    """Convert datetime to Unix milliseconds."""
    return int(dt.timestamp() * 1000)


def to_iso(dt):
    """Convert datetime to ISO 8601 string with Z suffix."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_config(base_time):
    """Build team config.json matching real Claude agent teams format."""
    return {
        "name": TEAM_NAME,
        "description": "Redesign the analytics dashboard with new charts and filters",
        "createdAt": to_ms(base_time),
        "leadAgentId": f"team-lead@{TEAM_NAME}",
        "leadSessionId": "session-seed-001",
        "members": [
            {
                "agentId": f"team-lead@{TEAM_NAME}",
                "name": "team-lead",
                "agentType": "team-lead",
                "model": "claude-opus-4-6",
                "joinedAt": to_ms(base_time),
                "tmuxPaneId": "",
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "subscriptions": [],
                "backendType": "in-process",
                "prompt": "You are the team lead. Coordinate planning, implementation, and testing across teammates. Break down the dashboard redesign into tasks and assign them.",
                "color": None,
            },
            {
                "agentId": f"planner@{TEAM_NAME}",
                "name": "planner",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=2)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "purple",
            },
            {
                "agentId": f"implementer@{TEAM_NAME}",
                "name": "implementer",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=5)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "blue",
            },
            {
                "agentId": f"tester@{TEAM_NAME}",
                "name": "tester",
                "agentType": "general-purpose",
                "model": "haiku",
                "joinedAt": to_ms(base_time + timedelta(minutes=8)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "green",
            },
        ],
    }


def build_tasks():
    """Build task JSON files — 7 tasks across all statuses."""
    return [
        {
            "id": "1",
            "subject": "Plan architecture",
            "description": "Design the component architecture and data flow for the dashboard redesign",
            "status": "completed",
            "blocks": ["2", "3"],
            "blockedBy": [],
            "owner": "planner",
            "metadata": {"_internal": True},
        },
        {
            "id": "2",
            "subject": "Build API endpoints",
            "description": "Create REST endpoints for chart data, filters, and user preferences",
            "status": "completed",
            "blocks": ["4", "5"],
            "blockedBy": ["1"],
            "owner": "implementer",
        },
        {
            "id": "3",
            "subject": "Design UI mockups",
            "description": "Create wireframes and component layouts for the new dashboard views",
            "status": "completed",
            "blocks": ["5"],
            "blockedBy": ["1"],
            "owner": "planner",
        },
        {
            "id": "4",
            "subject": "Write integration tests",
            "description": "Test API endpoints with realistic fixture data and edge cases",
            "status": "in_progress",
            "blocks": ["7"],
            "blockedBy": ["2"],
            "owner": "tester",
        },
        {
            "id": "5",
            "subject": "Implement frontend",
            "description": "Build React components for charts, filters, and layout using the approved mockups",
            "status": "in_progress",
            "blocks": ["6"],
            "blockedBy": ["2", "3"],
            "owner": "implementer",
        },
        {
            "id": "6",
            "subject": "Code review",
            "description": "Review frontend implementation and test coverage before deployment",
            "status": "pending",
            "blocks": ["7"],
            "blockedBy": ["5"],
            "owner": "team-lead",
        },
        {
            "id": "7",
            "subject": "Deploy to staging",
            "description": "Deploy the redesigned dashboard to the staging environment for QA",
            "status": "pending",
            "blocks": [],
            "blockedBy": ["4", "6"],
            "owner": "team-lead",
        },
    ]


def build_inboxes(base_time):
    """Build inbox messages for each agent."""
    inboxes = {}

    # team-lead inbox: 2 plain messages from planner + implementer
    inboxes["team-lead"] = [
        {
            "from": "planner",
            "text": "Architecture plan is ready. I've broken it into 3 frontend components and 2 API modules. Assigning tasks now.",
            "timestamp": to_iso(base_time + timedelta(minutes=6)),
            "color": "purple",
            "read": True,
        },
        {
            "from": "implementer",
            "text": "API endpoints are done. Starting on the frontend components. The chart library needs a peer dependency update.",
            "timestamp": to_iso(base_time + timedelta(minutes=18)),
            "color": "blue",
            "read": False,
        },
    ]

    # planner inbox: 1 plain from team-lead
    inboxes["planner"] = [
        {
            "from": "team-lead",
            "text": "Good work on the architecture. Please review the API contracts before implementer starts the frontend.",
            "timestamp": to_iso(base_time + timedelta(minutes=7)),
            "color": None,
            "read": True,
        },
    ]

    # implementer inbox: 1 permission_request + 1 plain
    permission_request = json.dumps({
        "type": "permission_request",
        "request_id": "perm-seed-001",
        "agent_id": "implementer",
        "tool_name": "Bash",
        "tool_use_id": "toolu_seed_ABC",
        "description": "Run production build",
        "input": {"command": "npm run build"},
        "permission_suggestions": [
            {
                "type": "add_tool_rule",
                "tool": "Bash",
                "rule_type": "always_allow",
                "rule_pattern": "npm run*",
            }
        ],
    })

    inboxes["implementer"] = [
        {
            "from": "implementer",
            "text": permission_request,
            "timestamp": to_iso(base_time + timedelta(minutes=22)),
            "color": "blue",
            "read": False,
        },
        {
            "from": "team-lead",
            "text": "Make sure to use the existing chart component library. Don't add new dependencies without checking first.",
            "timestamp": to_iso(base_time + timedelta(minutes=10)),
            "color": None,
            "read": True,
        },
    ]

    # tester inbox: 1 shutdown_request + 1 plain
    shutdown_request = json.dumps({
        "type": "shutdown_request",
        "reason": "Pausing test work until frontend is closer to done",
        "requestId": "shutdown-seed-001",
    })

    inboxes["tester"] = [
        {
            "from": "team-lead",
            "text": "Start with the API integration tests. Frontend tests can wait until implementer is further along.",
            "timestamp": to_iso(base_time + timedelta(minutes=12)),
            "color": None,
            "read": True,
        },
        {
            "from": "team-lead",
            "text": shutdown_request,
            "timestamp": to_iso(base_time + timedelta(minutes=25)),
            "color": None,
            "read": False,
        },
    ]

    return inboxes


def write_seed_data(output_dir):
    """Write all seed data files to the output directory."""
    output_dir = Path(output_dir)
    teams_dir = output_dir / "teams" / TEAM_NAME
    tasks_dir = output_dir / "tasks" / TEAM_NAME
    inboxes_dir = teams_dir / "inboxes"

    # Create directories
    inboxes_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Base time: 30 minutes ago
    base_time = now_utc() - timedelta(minutes=30)

    # Write config
    config = build_config(base_time)
    (teams_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    print(f"  Created {teams_dir / 'config.json'}")

    # Write tasks
    tasks = build_tasks()
    for task in tasks:
        task_path = tasks_dir / f"{task['id']}.json"
        task_path.write_text(json.dumps(task, indent=2), encoding="utf-8")
    (tasks_dir / ".lock").write_text("", encoding="utf-8")
    print(f"  Created {len(tasks)} task files + .lock in {tasks_dir}")

    # Write inboxes
    inboxes = build_inboxes(base_time)
    for agent_name, messages in inboxes.items():
        inbox_path = inboxes_dir / f"{agent_name}.json"
        inbox_path.write_text(json.dumps(messages, indent=2), encoding="utf-8")
    print(f"  Created {len(inboxes)} inbox files in {inboxes_dir}")


def clean_seed_data(output_dir):
    """Remove seed data directories."""
    output_dir = Path(output_dir)
    team_dir = output_dir / "teams" / TEAM_NAME
    tasks_dir = output_dir / "tasks" / TEAM_NAME

    removed = False
    if team_dir.exists():
        shutil.rmtree(team_dir)
        print(f"  Removed {team_dir}")
        removed = True
    if tasks_dir.exists():
        shutil.rmtree(tasks_dir)
        print(f"  Removed {tasks_dir}")
        removed = True

    if not removed:
        print("  No seed data found to clean")


def main():
    parser = argparse.ArgumentParser(description="Generate mock data for Agent Teams Monitor")
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / ".claude"),
        help="Base directory for teams/ and tasks/ (default: ~/.claude/)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove seed data instead of creating it",
    )
    args = parser.parse_args()

    print(f"Agent Teams Monitor — Seed Data")
    print(f"Target: {args.output_dir}")
    print()

    if args.clean:
        print("Cleaning seed data...")
        clean_seed_data(args.output_dir)
    else:
        print("Writing seed data...")
        write_seed_data(args.output_dir)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
