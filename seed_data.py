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

TEAM_NAMES = ["dashboard-redesign", "api-migration"]


def now_utc():
    return datetime.now(timezone.utc)


def to_ms(dt):
    """Convert datetime to Unix milliseconds."""
    return int(dt.timestamp() * 1000)


def to_iso(dt):
    """Convert datetime to ISO 8601 string with Z suffix."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def build_config(team_name, base_time):
    """Build team config.json matching real Claude agent teams format."""
    if team_name == "dashboard-redesign":
        return _build_dashboard_config(team_name, base_time)
    elif team_name == "api-migration":
        return _build_migration_config(team_name, base_time)


def _build_dashboard_config(team_name, base_time):
    return {
        "name": team_name,
        "description": "Redesign the analytics dashboard with new charts and filters",
        "createdAt": to_ms(base_time),
        "leadAgentId": f"team-lead@{team_name}",
        "leadSessionId": "session-seed-001",
        "members": [
            {
                "agentId": f"team-lead@{team_name}",
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
                "agentId": f"planner@{team_name}",
                "name": "planner",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=2)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "purple",
            },
            {
                "agentId": f"implementer@{team_name}",
                "name": "implementer",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=5)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "blue",
            },
            {
                "agentId": f"tester@{team_name}",
                "name": "tester",
                "agentType": "general-purpose",
                "model": "haiku",
                "joinedAt": to_ms(base_time + timedelta(minutes=8)),
                "cwd": "c:\\Users\\dchan\\Desktop\\project",
                "color": "green",
            },
        ],
    }


def _build_migration_config(team_name, base_time):
    return {
        "name": team_name,
        "description": "Migrate REST API from v1 to v2 with breaking change management",
        "createdAt": to_ms(base_time),
        "leadAgentId": f"team-lead@{team_name}",
        "leadSessionId": "session-seed-002",
        "members": [
            {
                "agentId": f"team-lead@{team_name}",
                "name": "team-lead",
                "agentType": "team-lead",
                "model": "claude-opus-4-6",
                "joinedAt": to_ms(base_time),
                "tmuxPaneId": "",
                "cwd": "c:\\Users\\dchan\\Desktop\\api-project",
                "subscriptions": [],
                "backendType": "in-process",
                "prompt": "You are the team lead. Coordinate the API migration from v1 to v2. Ensure backward compatibility during the transition period.",
                "color": None,
            },
            {
                "agentId": f"researcher@{team_name}",
                "name": "researcher",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=1)),
                "cwd": "c:\\Users\\dchan\\Desktop\\api-project",
                "color": "orange",
            },
            {
                "agentId": f"implementer@{team_name}",
                "name": "implementer",
                "agentType": "general-purpose",
                "model": "opus",
                "joinedAt": to_ms(base_time + timedelta(minutes=3)),
                "cwd": "c:\\Users\\dchan\\Desktop\\api-project",
                "color": "blue",
            },
            {
                "agentId": f"reviewer@{team_name}",
                "name": "reviewer",
                "agentType": "general-purpose",
                "model": "sonnet",
                "joinedAt": to_ms(base_time + timedelta(minutes=4)),
                "cwd": "c:\\Users\\dchan\\Desktop\\api-project",
                "color": "red",
            },
            {
                "agentId": f"tester@{team_name}",
                "name": "tester",
                "agentType": "general-purpose",
                "model": "haiku",
                "joinedAt": to_ms(base_time + timedelta(minutes=6)),
                "cwd": "c:\\Users\\dchan\\Desktop\\api-project",
                "color": "green",
            },
        ],
    }


def build_tasks(team_name):
    """Build task JSON files for a team."""
    if team_name == "dashboard-redesign":
        return _build_dashboard_tasks()
    elif team_name == "api-migration":
        return _build_migration_tasks()
    return []


def _build_dashboard_tasks():
    """7 tasks across all statuses for the dashboard project."""
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


def _build_migration_tasks():
    """9 tasks for the API migration — more tasks, different status distribution."""
    return [
        {
            "id": "1",
            "subject": "Audit v1 endpoints",
            "description": "Catalog all existing v1 REST endpoints, request/response schemas, and consumer dependencies",
            "status": "completed",
            "blocks": ["2", "3"],
            "blockedBy": [],
            "owner": "researcher",
        },
        {
            "id": "2",
            "subject": "Design v2 schema",
            "description": "Define new v2 API contracts with OpenAPI spec, including breaking changes and deprecation plan",
            "status": "completed",
            "blocks": ["4", "5"],
            "blockedBy": ["1"],
            "owner": "researcher",
        },
        {
            "id": "3",
            "subject": "Set up versioned routing",
            "description": "Implement /api/v1 and /api/v2 route prefixes with shared middleware",
            "status": "completed",
            "blocks": ["4"],
            "blockedBy": ["1"],
            "owner": "implementer",
        },
        {
            "id": "4",
            "subject": "Implement v2 endpoints",
            "description": "Build all v2 endpoint handlers based on the new schema design",
            "status": "in_progress",
            "blocks": ["6", "7"],
            "blockedBy": ["2", "3"],
            "owner": "implementer",
        },
        {
            "id": "5",
            "subject": "Write migration guide",
            "description": "Document all breaking changes and provide code examples for consumers upgrading from v1 to v2",
            "status": "in_progress",
            "blocks": ["9"],
            "blockedBy": ["2"],
            "owner": "researcher",
        },
        {
            "id": "6",
            "subject": "Write v2 unit tests",
            "description": "Full test coverage for all v2 endpoints including edge cases and error responses",
            "status": "pending",
            "blocks": ["8"],
            "blockedBy": ["4"],
            "owner": "tester",
        },
        {
            "id": "7",
            "subject": "Review v2 implementation",
            "description": "Code review of v2 endpoints for security, performance, and API design best practices",
            "status": "pending",
            "blocks": ["8"],
            "blockedBy": ["4"],
            "owner": "reviewer",
        },
        {
            "id": "8",
            "subject": "Deploy v2 to staging",
            "description": "Deploy v2 alongside v1 in staging for parallel testing with real traffic",
            "status": "pending",
            "blocks": ["9"],
            "blockedBy": ["6", "7"],
            "owner": "team-lead",
        },
        {
            "id": "9",
            "subject": "Deprecate v1 endpoints",
            "description": "Add deprecation headers to v1, update docs, and notify consumers of sunset timeline",
            "status": "pending",
            "blocks": [],
            "blockedBy": ["5", "8"],
            "owner": "team-lead",
        },
    ]


def build_inboxes(team_name, base_time):
    """Build inbox messages for each agent in a team."""
    if team_name == "dashboard-redesign":
        return _build_dashboard_inboxes(base_time)
    elif team_name == "api-migration":
        return _build_migration_inboxes(base_time)
    return {}


def _build_dashboard_inboxes(base_time):
    inboxes = {}

    # team-lead inbox: 2 plain messages from planner + implementer (with markdown)
    inboxes["team-lead"] = [
        {
            "from": "planner",
            "text": "## Architecture Plan Ready\n\nI've broken the dashboard redesign into:\n\n**Frontend components:**\n- `ChartPanel` — renders chart grid with filter controls\n- `FilterBar` — date range, metric selector, team filter\n- `DashboardLayout` — responsive grid wrapper\n\n**API modules:**\n- `/api/charts` — chart data endpoints\n- `/api/preferences` — user filter preferences\n\n> All components use the existing `useDataFetch` hook for polling.\n\nAssigning tasks now.",
            "timestamp": to_iso(base_time + timedelta(minutes=6)),
            "color": "purple",
            "read": True,
        },
        {
            "from": "implementer",
            "text": "API endpoints are done. Starting on the frontend components.\n\n**Note:** The chart library needs a peer dependency update:\n```bash\nnpm install recharts@2.12 --save\n```\nThis is a minor version bump, no breaking changes.",
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


def _build_migration_inboxes(base_time):
    inboxes = {}

    # team-lead inbox: updates from researcher and implementer
    inboxes["team-lead"] = [
        {
            "from": "researcher",
            "text": "Audit complete. Found 23 v1 endpoints across 4 resource groups. 8 have breaking changes in v2. Full report in task #1.",
            "timestamp": to_iso(base_time + timedelta(minutes=5)),
            "color": "orange",
            "read": True,
        },
        {
            "from": "researcher",
            "text": "## v2 Schema Draft Ready\n\nKey breaking changes from v1:\n\n| Area | v1 | v2 |\n|------|-----|-----|\n| Pagination | `offset`/`limit` | **Cursor-based** (`after`/`before`) |\n| Auth | API key header | **Bearer tokens** (OAuth2) |\n| Timestamps | Unix epoch | **ISO 8601** with timezone |\n| Errors | Status code only | RFC 7807 `problem+json` |\n\nFull OpenAPI spec is in `docs/v2-openapi.yaml`.",
            "timestamp": to_iso(base_time + timedelta(minutes=14)),
            "color": "orange",
            "read": True,
        },
        {
            "from": "implementer",
            "text": "Versioned routing is set up. Starting on v2 endpoints now. Question: should we keep the legacy XML response format as an option or drop it entirely?",
            "timestamp": to_iso(base_time + timedelta(minutes=20)),
            "color": "blue",
            "read": False,
        },
    ]

    # researcher inbox
    inboxes["researcher"] = [
        {
            "from": "team-lead",
            "text": "Great audit. Start on the migration guide while implementer builds the endpoints — consumers will need lead time.",
            "timestamp": to_iso(base_time + timedelta(minutes=6)),
            "color": None,
            "read": True,
        },
    ]

    # implementer inbox: permission request for running DB migration
    permission_request = json.dumps({
        "type": "permission_request",
        "request_id": "perm-seed-002",
        "agent_id": "implementer",
        "tool_name": "Bash",
        "tool_use_id": "toolu_seed_DEF",
        "description": "Run database migration",
        "input": {"command": "python manage.py migrate --database=staging"},
        "permission_suggestions": [
            {
                "type": "add_tool_rule",
                "tool": "Bash",
                "rule_type": "always_allow",
                "rule_pattern": "python manage.py migrate*",
            }
        ],
    })

    inboxes["implementer"] = [
        {
            "from": "team-lead",
            "text": "Drop the XML format — v2 is JSON-only. Document it as a breaking change in the migration guide.",
            "timestamp": to_iso(base_time + timedelta(minutes=22)),
            "color": None,
            "read": False,
        },
        {
            "from": "implementer",
            "text": permission_request,
            "timestamp": to_iso(base_time + timedelta(minutes=24)),
            "color": "blue",
            "read": False,
        },
    ]

    # reviewer inbox: waiting for work
    inboxes["reviewer"] = [
        {
            "from": "team-lead",
            "text": "Implementer is working on v2 endpoints. Be ready to review once task #4 is done. Focus on auth and rate limiting.",
            "timestamp": to_iso(base_time + timedelta(minutes=15)),
            "color": None,
            "read": True,
        },
    ]

    # tester inbox: standing by
    inboxes["tester"] = [
        {
            "from": "team-lead",
            "text": "Start writing test scaffolding based on the v2 schema. Full tests once endpoints are implemented.",
            "timestamp": to_iso(base_time + timedelta(minutes=16)),
            "color": None,
            "read": True,
        },
    ]

    return inboxes


def write_seed_data(output_dir):
    """Write all seed data files to the output directory."""
    output_dir = Path(output_dir)

    for i, team_name in enumerate(TEAM_NAMES):
        teams_dir = output_dir / "teams" / team_name
        tasks_dir = output_dir / "tasks" / team_name
        inboxes_dir = teams_dir / "inboxes"

        # Create directories
        inboxes_dir.mkdir(parents=True, exist_ok=True)
        tasks_dir.mkdir(parents=True, exist_ok=True)

        # Stagger base times so teams look like they started at different times
        base_time = now_utc() - timedelta(minutes=30 + i * 15)

        # Write config
        config = build_config(team_name, base_time)
        (teams_dir / "config.json").write_text(
            json.dumps(config, indent=2), encoding="utf-8"
        )
        print(f"  [{team_name}] Created config.json")

        # Write tasks
        tasks = build_tasks(team_name)
        for task in tasks:
            task_path = tasks_dir / f"{task['id']}.json"
            task_path.write_text(json.dumps(task, indent=2), encoding="utf-8")
        (tasks_dir / ".lock").write_text("", encoding="utf-8")
        print(f"  [{team_name}] Created {len(tasks)} task files + .lock")

        # Write inboxes
        inboxes = build_inboxes(team_name, base_time)
        for agent_name, messages in inboxes.items():
            inbox_path = inboxes_dir / f"{agent_name}.json"
            inbox_path.write_text(json.dumps(messages, indent=2), encoding="utf-8")
        print(f"  [{team_name}] Created {len(inboxes)} inbox files")


def clean_seed_data(output_dir):
    """Remove seed data directories."""
    output_dir = Path(output_dir)

    removed = False
    for team_name in TEAM_NAMES:
        team_dir = output_dir / "teams" / team_name
        tasks_dir = output_dir / "tasks" / team_name

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
