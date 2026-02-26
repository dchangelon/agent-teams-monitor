# Agent Teams Monitor

A real-time dashboard for monitoring Claude Code agent team coordination. Shows team activity, task progress, agent timelines, and a live message feed — with the ability to send messages to active agents.

## Why This Exists

When running Claude Code agent teams (multiple agents working on a task together), there's no built-in way to see what's happening across all agents at once. This dashboard reads directly from Claude Code's team and task files to give you a live view of who's doing what, where tasks stand, and what messages are flowing between agents.

## Features

- **Team overview** — Grid of active teams with agent count, task progress, and health indicators
- **Agent timeline** — Swim lane visualization showing each agent's activity over time
- **Live message feed** — Real-time stream of agent messages with type indicators (plain, permission requests, responses)
- **Message sending** — Select an agent and send messages to active teams from the dashboard
- **Task tracking** — Progress bars and status for each task with search and filtering
- **Auto-refresh** — Dashboard updates automatically as agents work

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Data Source**: Reads from `~/.claude/teams/` and `~/.claude/tasks/` directories (Claude Code's local state)

## Status

Work in progress — core monitoring and messaging are functional. Timeline visualization and settings are being refined.

## Getting Started

### Prerequisites

- Python 3.10+
- Claude Code with agent teams feature enabled

### Setup

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
# or
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

### Environment Variables

```bash
cp .env.example .env
# Edit .env with your settings
```

### Run

```bash
python run.py
```

The dashboard opens at `http://localhost:8000`.

## License

MIT
