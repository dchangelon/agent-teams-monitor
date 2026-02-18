import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.file_reader import TeamFileReader
from src.message_writer import InboxWriter
from src.timeline import TimelineTracker

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_teams_dir(tmp_path):
    """Create tmp dirs with sample JSON data mimicking real ~/.claude/ structure."""
    teams_dir = tmp_path / "teams"
    tasks_dir = tmp_path / "tasks"

    # Create team directory structure
    team_dir = teams_dir / "test-team"
    team_dir.mkdir(parents=True)
    inboxes_dir = team_dir / "inboxes"
    inboxes_dir.mkdir()

    # Copy team config
    shutil.copy(FIXTURES_DIR / "team_config.json", team_dir / "config.json")

    # Copy inbox messages for agent-1
    shutil.copy(FIXTURES_DIR / "inbox_messages.json", inboxes_dir / "agent-1.json")

    # Create empty inbox for team-lead
    (inboxes_dir / "team-lead.json").write_text("[]", encoding="utf-8")

    # Create tasks directory with task files + .lock
    tasks_team_dir = tasks_dir / "test-team"
    tasks_team_dir.mkdir(parents=True)
    shutil.copy(FIXTURES_DIR / "task_pending.json", tasks_team_dir / "1.json")
    shutil.copy(FIXTURES_DIR / "task_in_progress.json", tasks_team_dir / "2.json")
    shutil.copy(FIXTURES_DIR / "task_completed.json", tasks_team_dir / "3.json")
    (tasks_team_dir / ".lock").write_text("", encoding="utf-8")

    # Create a team dir with no config.json (edge case)
    no_config_dir = teams_dir / "broken-team"
    no_config_dir.mkdir()
    broken_inboxes = no_config_dir / "inboxes"
    broken_inboxes.mkdir()
    (broken_inboxes / "agent-x.json").write_text(
        json.dumps([{"from": "someone", "text": "hello", "timestamp": "2026-02-14T10:00:00.000Z", "read": False}]),
        encoding="utf-8",
    )

    # Create an empty tasks dir (edge case — only .lock)
    empty_tasks_dir = tasks_dir / "empty-team"
    empty_tasks_dir.mkdir(parents=True)
    (empty_tasks_dir / ".lock").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture
def reader(sample_teams_dir):
    """TeamFileReader with overridden paths pointing to tmp fixtures."""
    return TeamFileReader(
        teams_base=sample_teams_dir / "teams",
        tasks_base=sample_teams_dir / "tasks",
    )


@pytest.fixture
def tracker():
    """Fresh TimelineTracker instance."""
    return TimelineTracker()


@pytest.fixture
def writer(sample_teams_dir):
    """InboxWriter with overridden path pointing to tmp fixtures."""
    return InboxWriter(teams_base=sample_teams_dir / "teams")


@pytest.fixture
def client(sample_teams_dir):
    """FastAPI TestClient with overridden paths."""
    app = create_app(
        teams_dir=sample_teams_dir / "teams",
        tasks_dir=sample_teams_dir / "tasks",
    )
    return TestClient(app)
