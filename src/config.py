import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CLAUDE_HOME = Path(os.getenv("CLAUDE_HOME", str(Path.home() / ".claude")))
TEAMS_DIR = CLAUDE_HOME / "teams"
TASKS_DIR = CLAUDE_HOME / "tasks"

PORT = int(os.getenv("PORT", 5050))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DEFAULT_POLL_INTERVAL_MS = int(os.getenv("POLL_INTERVAL_MS", 2000))
DEFAULT_SENDER_NAME = os.getenv("SENDER_NAME", "user")
STALL_THRESHOLD_MINUTES = int(os.getenv("STALL_THRESHOLD_MINUTES", 10))
TIMELINE_MAX_EVENTS = int(os.getenv("TIMELINE_MAX_EVENTS", 10000))
WRITE_API_KEY = os.getenv("WRITE_API_KEY", "").strip()
SETTINGS_PATH = CLAUDE_HOME / "agent-monitor-settings.json"

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
