---
name: agent-teams-monitor-impact-plan
overview: Phased implementation plan to shift the Agent Teams Monitor from a passive dashboard into an active orchestration tool that reduces time-to-resolve-blockers.
todos:
  - id: phase-1-action-queue
    content: "DONE: Action queue service, models, endpoint, UI panel, tests (132 passing)"
    status: completed
  - id: phase-2-permission-ux
    content: "DONE: Browser notifications, batch permission actions, smart polling (139 passing)"
    status: completed
  - id: phase-3-health-score
    content: "DONE: Health score service (0-100), endpoint, UI badge on team cards and detail header (171 passing)"
    status: completed
  - id: phase-4-message-intel
    content: "DONE: Unresolved items filter, conversation pair grouping on Messages tab (183 passing)"
    status: completed
  - id: phase-5-intervention-hints
    content: "DONE: Permission risk badges (low/medium), stall context with last completed task (191 passing)"
    status: completed
isProject: false
---

# Agent Teams Monitor — Impact Implementation Plan

## Objective

Shift from a passive status dashboard into an active orchestration tool that shortens response time to blockers and improves team throughput.

## Project Context

**Tech stack**: FastAPI backend, vanilla JS + Tailwind CSS frontend, single-page dashboard.
**Data source**: Reads JSON files from `~/.claude/teams/` and `~/.claude/tasks/` on disk.
**Current test count**: 191 passing (pytest).

### Key Files

| File | Purpose |
|------|---------|
| `src/app.py` | FastAPI app factory, all routes, helper functions (`compute_agent_activity`, `extract_pending_permissions`, `build_agent_timeline`) |
| `src/models.py` | Internal dataclasses + Pydantic response models |
| `src/file_reader.py` | `TeamFileReader` — reads team configs, tasks, inbox messages from disk |
| `src/message_writer.py` | `InboxWriter` + `ConfigWriter` — writes to agent inboxes and team config |
| `src/timeline.py` | `TimelineTracker` — in-memory task state change log |
| `src/config.py` | Path constants, env var config (`STALL_THRESHOLD_MINUTES`, `WRITE_API_KEY`, etc.) |
| `src/services/action_queue_service.py` | **Phase 1 (done)** — `build_action_queue()` |
| `templates/dashboard.html` | Single-page HTML shell (Tailwind CDN) |
| `static/app.js` | ~1250 lines vanilla JS — polling, rendering, event handlers |
| `static/styles.css` | Custom CSS for swim lanes, kanban, scrollbars |
| `tests/conftest.py` | Shared fixtures (`sample_teams_dir`, `reader`, `tracker`, `writer`, `client`) |

### Architecture Pattern

- `create_app()` factory in `app.py` accepts path overrides for testing
- Routes read data via `TeamFileReader`, compute derived state via helper functions or services, return Pydantic models
- Frontend polls `GET /api/teams/{name}/snapshot` every 2s for the detail view (consolidated payload), then does tab-specific fetches
- Write endpoints (`POST`) are gated by optional `X-API-Key` header
- All route path params validated against `^[A-Za-z0-9_-]+$`

### Data Flow

```
~/.claude/teams/{name}/config.json     ──┐
~/.claude/teams/{name}/inboxes/*.json  ──┤──> TeamFileReader ──> Route Handlers ──> Pydantic Response
~/.claude/tasks/{name}/*.json          ──┘         │                  │
                                                   │            Services (action_queue, health_score)
                                                   │                  │
                                             TimelineTracker    ──────┘
                                           (in-memory diffs)
```

---

## Phase 1: Action Queue — COMPLETED

**What was built:**

### Backend

**`src/services/action_queue_service.py`** — `build_action_queue()` function:
- Accepts `pending_permissions`, `activity`, `tasks`, `stall_threshold_seconds`, optional `now` for testing
- Produces ranked `ActionQueueItemResponse` list from 3 categories:
  - **permission**: Each pending permission → `high` (recent) or `critical` (older than 2 min)
  - **stalled_agent**: Stalled agents with pending work → `high` or `critical` (>2x threshold)
  - **blocked_task**: Tasks with unresolved `blocked_by` references → `normal`
- Sorted by priority (critical → high → normal), then by duration descending (oldest first)
- Permission items carry `permission_data` dict for inline approve/deny actions

**Models added to `src/models.py`**:
```python
class ActionQueueItemResponse(BaseModel):
    id: str                          # "perm:{request_id}", "stall:{agent}", "blocked:{task_id}"
    category: str                    # "permission" | "blocked_task" | "stalled_agent"
    priority: str                    # "critical" | "high" | "normal"
    title: str
    detail: str
    agent_name: Optional[str]
    agent_color: Optional[str]
    target_link: Optional[str]       # UI element to navigate to
    created_at: Optional[str]
    duration_seconds: Optional[int]
    permission_data: Optional[dict]  # {request_id, tool_use_id, tool_name} for permissions

class ActionQueueResponse(BaseModel):
    success: bool = True
    items: list[ActionQueueItemResponse]
    total: int = 0
```

**`DetailSnapshotResponse`** extended with `action_queue: list[ActionQueueItemResponse] = []`.

**Endpoints added to `src/app.py`**:
- `GET /api/teams/{name}/action-queue` — standalone endpoint
- Snapshot endpoint (`GET /api/teams/{name}/snapshot`) now includes `action_queue` field

### Frontend

**`templates/dashboard.html`**: Action Queue panel added above the alert banner in the detail view. Collapsible with toggle button and chevron.

**`static/app.js`**:
- `state.actionQueueExpanded = true` — expanded by default
- `renderActionQueue(items)` function renders:
  - Priority-colored rows (red/amber/gray backgrounds)
  - Category icons (lock, pause, blocked)
  - Priority badge, title, detail text, duration timer
  - Inline Approve/Deny buttons for permission items (reuses `handlePermission()`)
  - "View" button for blocked tasks (navigates to Tasks tab via `switchTab()`)
- Toggle collapse wired in `init()`
- Called from `poll()` via `snapshot.action_queue`

### Tests (23 new)

**`tests/test_action_queue_service.py`** (17 tests):
- `TestEmptyQueue` — no issues, no data
- `TestPermissionItems` — high/critical priority, sorting by age, agent info passthrough
- `TestStalledAgentItems` — with/without pending work, active excluded, very-stalled → critical
- `TestBlockedTaskItems` — blocked appears, resolved blocker excluded, completed task not flagged
- `TestPrioritySorting` — critical before high before normal, oldest first within same priority
- `TestMixedScenario` — 10 concurrent permissions, all categories present

**`tests/test_routes.py`** (6 new tests):
- `TestGetSnapshot::test_snapshot_includes_action_queue`
- `TestGetActionQueue` — returns items, includes pending permission, disappears after approval, 404, sorted by priority

---

## Phase 2: Permission & Alert UX — COMPLETED

**Goal**: Reduce permission response latency. Permissions are the #1 blocker — every second of delay stalls the entire agent.

### 2a. Browser Notifications

**Backend**: No changes needed. The snapshot already includes `pending_permissions`.

**Frontend (`static/app.js`)**:
- Add `state.knownPermissionIds = new Set()` to track seen permissions
- In `poll()`, after `renderActionQueue()`, compare `snapshot.pending_permissions` against `state.knownPermissionIds`
- For genuinely new permission IDs:
  - Call `new Notification('Permission Request', { body: '...' })` via [Notifications API](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API)
  - Optionally play a short audio beep via `AudioContext` (gated by a settings toggle)
  - Add the new IDs to `state.knownPermissionIds`
- Request notification permission on first visit: `Notification.requestPermission()` — call this on a user gesture (e.g., clicking an "Enable notifications" button in the header)
- Clear `state.knownPermissionIds` when navigating away from team detail

**Frontend (`templates/dashboard.html`)**:
- Add a small settings gear icon in the header (next to the Pause button) with a dropdown:
  - Toggle: "Browser notifications" (on/off)
  - Toggle: "Sound alerts" (on/off)
- Store preferences in `localStorage`

### 2b. Batch Permission Actions

**Backend (`src/app.py`)**:
- New endpoint: `POST /api/teams/{name}/permissions/batch`
- Request model in `src/models.py`:
  ```python
  class BatchPermissionAction(BaseModel):
      agent_name: str
      request_id: str
      tool_use_id: str
      action: str  # "approve" | "deny"

  class BatchPermissionRequest(BaseModel):
      actions: list[BatchPermissionAction]
  ```
- Implementation: iterate `actions`, call `writer.send_permission_response()` for each, collect results
- Response: `ActionResponse` with count of successes

**Frontend (`static/app.js`)**:
- In `renderActionQueue()`, when 2+ permission items exist, add an "Approve All" button at the top of the queue panel
- Collect all permission items' `permission_data` and POST to batch endpoint
- Show toast with count of approved permissions

### 2c. Smart Polling (Page Visibility API)

**Frontend (`static/app.js`)**:
- In `init()`, add:
  ```js
  document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
          stopPolling();
      } else {
          startPolling(); // calls poll() immediately then resumes interval
      }
  });
  ```
- This pauses polling when the tab is backgrounded, resumes with an immediate fetch when focus returns

### Tests

- Extend `tests/test_routes.py` with `TestBatchPermissions`:
  - `test_batch_approve_multiple` — sends 2 approvals, both resolve
  - `test_batch_mixed_actions` — 1 approve + 1 deny
  - `test_batch_empty_actions` — empty list returns success
  - `test_batch_invalid_action` — bad action value returns 422
  - `test_batch_requires_api_key` — 401 without key

### Files to modify

| File | Changes |
|------|---------|
| `src/models.py` | Add `BatchPermissionAction`, `BatchPermissionRequest` |
| `src/app.py` | Add `POST /api/teams/{name}/permissions/batch` |
| `static/app.js` | Notifications, batch approve button, Page Visibility handler |
| `templates/dashboard.html` | Settings dropdown in header |
| `tests/test_routes.py` | `TestBatchPermissions` class |

---

## Phase 3: Workflow Health Score — COMPLETED

**Goal**: At-a-glance "is this team healthy?" signal for overview and detail views.

### Backend

**New file: `src/services/health_score_service.py`**

```python
def compute_health_score(
    pending_permissions: list[PermissionAlertResponse],
    activity: list[AgentActivityResponse],
    tasks: list,
    counts: dict,  # {"pending": N, "in_progress": N, "completed": N}
    now: Optional[datetime] = None,
) -> HealthScoreBreakdown:
```

Computes a 0–100 score from 4 weighted dimensions:

| Dimension | Weight | Logic |
|-----------|--------|-------|
| Permission latency | 30% | Start at 100, subtract 25 per pending permission, additional penalty scaled by wait time (seconds / 60) |
| Stall ratio | 25% | `100 * (1 - stalled_agents / total_agents)` |
| Blocked ratio | 25% | `100 * (1 - blocked_tasks / total_tasks)`. Blocked = has unresolved `blocked_by`. |
| Throughput | 20% | `100 * (completed / total)` if total > 0, else 100 |

Overall = weighted sum, clamped to 0–100.

Color thresholds: `green` (80+), `amber` (50–79), `red` (<50).
Labels: `Healthy`, `Needs Attention`, `Critical`.

Each dimension returns a `DimensionScore` with `name`, `score`, `weight`, and `explanation` (plain-language string).

**Models in `src/models.py`**:

```python
class DimensionScoreResponse(BaseModel):
    name: str
    score: int
    weight: float
    explanation: str

class HealthScoreBreakdown(BaseModel):
    overall: int
    color: str      # "green" | "amber" | "red"
    label: str      # "Healthy" | "Needs Attention" | "Critical"
    dimensions: list[DimensionScoreResponse]

class HealthScoreResponse(BaseModel):
    success: bool = True
    health: HealthScoreBreakdown
```

**Endpoints in `src/app.py`**:
- `GET /api/teams/{name}/health` → `HealthScoreResponse`
- Extend `DetailSnapshotResponse` with `health_score: Optional[int] = None` and `health_color: Optional[str] = None`
- Extend `TeamSummaryResponse` with `health_score: Optional[int] = None` and `health_color: Optional[str] = None` (for overview cards)

**Note**: The `list_teams` endpoint would need to compute health for each team. Since this involves reading tasks/messages for every team on every poll, consider caching or only computing it for the detail view initially. Start with detail-only and add to overview if performance is acceptable.

### Frontend

- **Team detail header**: Score badge — colored circle with number (e.g., green circle with "87") next to the team name
- **Expandable breakdown**: Click badge to show per-dimension scores with explanations
- **Overview cards** (if performance permits): Small colored dot with score number in the team card corner

### Tests

**New file: `tests/test_health_score_service.py`**:
- Score = 100 for a team with no issues (all tasks completed, no stalls, no permissions)
- Score drops with pending permissions (test exact math)
- Score drops with stalled agents
- Score drops with blocked tasks
- Score = 0 for a team with everything broken
- Color boundaries: 80 → green, 79 → amber, 50 → amber, 49 → red
- Dimension explanations are non-empty strings
- Empty team (0 tasks, 0 agents) → score 100 (nothing is wrong)

Extend `tests/test_routes.py`:
- `TestGetHealth` — endpoint contract, 404
- `TestGetSnapshot` — snapshot includes `health_score` and `health_color`

### Files to modify

| File | Changes |
|------|---------|
| `src/services/health_score_service.py` | New file |
| `src/models.py` | `DimensionScoreResponse`, `HealthScoreBreakdown`, `HealthScoreResponse`, extend snapshot + summary |
| `src/app.py` | `GET /api/teams/{name}/health`, wire into snapshot |
| `static/app.js` | `renderHealthBadge()`, expandable breakdown, badge on overview cards |
| `templates/dashboard.html` | Health badge container in header, breakdown panel |
| `tests/test_health_score_service.py` | New file |
| `tests/test_routes.py` | `TestGetHealth` class |

---

## Phase 4: Scoped Message Intelligence — PENDING

**Goal**: Make it easy to find unresolved items without scanning the full message feed.

This is a **scoped-down** version of the original plan's "Conversation Intelligence" phase. No NLP, no decision extraction, no decision threads.

### 4a. Unresolved Items Filter

**Backend (`src/app.py`)**:
- Extend `GET /api/teams/{name}/messages` with optional query param `?unresolved=true`
- When set, return only:
  - `permission_request` messages whose `request_id` has no matching `permission_response` (reuse `extract_pending_permissions` logic)
  - `shutdown_request` messages whose `target_agent` has not sent a `shutdown_response` (new check — scan for `type: "shutdown_response"` in messages)
- This is a server-side filter so the client just gets a smaller list

**Frontend (`static/app.js`)**:
- Add a toggle button/chip above the message filters: "Show unresolved only"
- When active, call `api.getMessages(name, { unresolved: true })` (add query param support to the API call)
- Style the toggle with amber when active to signal filtered state

### 4b. Conversation Pair Grouping

**Backend (`src/app.py`)**:
- Extend `GET /api/teams/{name}/messages` with optional query param `?group_by=pair`
- When set, return messages grouped by `from_agent → target_agent` pair:
  ```json
  {
    "groups": [
      {
        "pair": ["agent-1", "team-lead"],
        "messages": [...],
        "message_count": 5
      }
    ]
  }
  ```
- New response model `GroupedMessagesResponse` in `src/models.py`

**Frontend (`static/app.js`)**:
- Add a "Group by pair" toggle alongside existing filters
- When active, render messages in collapsible sections per agent pair instead of flat chronological
- Each section header: `agent-1 ↔ team-lead (5 messages)` with colored dots

### Tests

Extend `tests/test_routes.py`:
- `test_messages_unresolved_filter` — only unresolved items returned
- `test_messages_unresolved_excludes_resolved` — approved permissions not returned
- `test_messages_group_by_pair` — groups present, each group has pair and messages
- `test_messages_group_by_pair_with_agent_filter` — combining filters

### Files to modify

| File | Changes |
|------|---------|
| `src/models.py` | `MessageGroupResponse`, `GroupedMessagesResponse` |
| `src/app.py` | Extend messages endpoint with `unresolved` and `group_by` params |
| `static/app.js` | Unresolved toggle, pair grouping toggle, grouped rendering |
| `templates/dashboard.html` | Toggle buttons in messages filter bar |
| `tests/test_routes.py` | New test cases in `TestGetMessages` |

---

## Phase 5: Intervention Hints — COMPLETED

**Goal**: Help the operator make faster decisions by surfacing contextual information. Visual hints only — **no auto-approve, no auto-actions**.

### 5a. Permission Safety Indicators

**Backend (`src/services/action_queue_service.py`)**:
- Add `risk_level` field to `ActionQueueItemResponse` (update model in `src/models.py`):
  ```python
  risk_level: Optional[str] = None  # "low" | "medium" | None
  ```
- In `build_action_queue()`, for permission items, set `risk_level` based on `tool_name`:
  - `Read`, `Glob`, `Grep`, `WebSearch`, `WebFetch` → `"low"`
  - `Bash`, `Write`, `Edit`, `NotebookEdit` → `"medium"`
  - Everything else → `None` (no indicator)

**Frontend (`static/app.js`)**:
- In `renderActionQueue()`, for permission items with `risk_level`:
  - `"low"` → small green badge: "Low risk"
  - `"medium"` → small amber badge: "Review carefully"
  - `None` → no badge

### 5b. Stall Context

**Frontend (`static/app.js`)**:
- In `renderActionQueue()`, for `stalled_agent` items, enhance the `detail` text to include more context from the activity data:
  - Already shows: "No activity for Xm. N pending, M in progress."
  - Could also show: last completed task subject (if available from the tasks data passed through)

This is a minor enhancement to existing rendering — no new backend changes needed.

### Tests

- Extend `tests/test_action_queue_service.py`:
  - `test_permission_risk_level_low` — Read tool gets "low"
  - `test_permission_risk_level_medium` — Bash tool gets "medium"
  - `test_permission_risk_level_none` — unknown tool gets None

### Files to modify

| File | Changes |
|------|---------|
| `src/models.py` | Add `risk_level` to `ActionQueueItemResponse` |
| `src/services/action_queue_service.py` | Set `risk_level` for permission items |
| `static/app.js` | Render risk badges in action queue |
| `tests/test_action_queue_service.py` | Risk level tests |

---

## What's Explicitly Deferred

| Item | Why |
|------|-----|
| **Persistence / SQLite / JSONL** | Agent teams are ephemeral. Historical data has unclear value until proven. |
| **Trend sparklines** | Requires persistence layer. |
| **ML-based prediction** | Start with deterministic heuristics only. |
| **Auto-approval of permissions** | Too risky — approving the wrong permission has real consequences. |
| **Full NLP decision extraction** | Over-engineered for typical message volumes (tens, not thousands). |

---

## Delivery Order

| Phase | Dependencies | Can Parallelize With |
|-------|-------------|---------------------|
| Phase 1 (Action Queue) | None | — **COMPLETED** |
| Phase 2 (Permission UX) | Phase 1 (builds on action queue panel) | Phase 3 |
| Phase 3 (Health Score) | None | Phase 2 |
| Phase 4 (Message Intel) | None | — |
| Phase 5 (Intervention Hints) | Phase 1 (extends action queue) | — |

---

## Verification Checklist (per phase)

1. Run `pytest` — all tests pass, no regressions
2. Start server: `python run.py`
3. Open dashboard with an active agent team running in another terminal
4. Verify new UI elements render and update on poll cycles
5. For write actions, verify JSON files in `~/.claude/teams/` are correctly modified
6. Check browser console for JS errors
