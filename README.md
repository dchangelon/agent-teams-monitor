# Agent Teams Monitor

A real-time dashboard for monitoring Claude Code agent team coordination and task progress. Reads team and task data from `~/.claude/teams/` and `~/.claude/tasks/` directories.

## Status

Work in progress.

## Features

- Real-time monitoring of agent team activity
- Task progress tracking and timeline visualization
- Message sending to active agent teams

## Tech Stack

- **Backend**: FastAPI, Uvicorn
- **Language**: Python 3.10+

## Getting Started

### Prerequisites

- Python 3.10+
- Claude Code with agent teams feature

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

## License

MIT
