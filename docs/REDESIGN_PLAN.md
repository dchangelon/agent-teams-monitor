# Agent Teams Monitor — Single-Page Redesign

## Context

The monitor's detail view currently splits timeline, tasks, and messages into three separate tabs, forcing constant switching. Permission requests show in two duplicate banners. Content messages are unformatted walls of text indistinguishable from system chatter. The API key prompt adds unnecessary friction on every load. And the entire frontend lives in a monolithic 1650-line `app.js`.

This plan consolidates everything into a single-page layout, differentiates message types, adds markdown rendering, removes the API key prompt, and modularizes the frontend.

---

## Layout: Single-Page Two-Column Design

Replace the three-tab detail view with everything on one page:

```
+=====================================================================+
| [< Back]  Team Name  [Health: 87]  "description"          [Pause]   |
+=====================================================================+
| ACTION BAR (only when items exist)                                   |
| [Approve All (3)]  [perm: Edit ↦ Approve|Deny] [stalled: agent-x]  |
+=====================================================================+
|                                                                      |
|  MESSAGE FEED (~65%)               |  RIGHT PANEL (~35%)             |
|  [Send form at top]                |                                 |
|  [Filters + system msg toggle]     |  Agents (5)   8/13 tasks (62%) |
|                                    |  [progress bar]                 |
|  ┌─ content msg (markdown) ─────┐  |  [agent1: Active, 3/5]         |
|  │ **Step 4 — AI_ENGINEERING**  │  |  [agent2: Stalled 12m ⚠]       |
|  │ - 4a: model refs updated    │  |  [agent3: Idle]                 |
|  │ - 4b: system prompts fixed  │  |                                 |
|  └──────────────────────────────┘  |  Tasks                          |
|  ╌ idle: content-agent (compact) ╌ |  [pending: 2] [in progress: 3] |
|  ╌ permission approved (compact) ╌ |  [compact task list]            |
|  ┌─ content msg (markdown) ─────┐  |                                 |
|  │ Completed auth refactor...   │  |  Timeline                       |
|  └──────────────────────────────┘  |  [▶ Expand swim lanes]          |
|                                    |                                 |
+=====================================================================+
```

**Responsive**: Below `lg` breakpoint, right panel stacks below the message feed.

---

## Phase 1: Modularize app.js (zero behavior change)

Split the 1650-line monolith into focused modules loaded via `<script>` tags:

| File | Contents | ~Lines |
|------|----------|--------|
| `static/js/helpers.js` | `state`, `escapeHtml`, `truncate`, `timeAgo`, `formatDuration`, `colorDot`, `$()`, `COLOR_MAP`, toast system | ~120 |
| `static/js/api.js` | API layer (`_jsonHeaders`, `getTeams`, `getSnapshot`, `sendMessage`, `handlePermission`, etc.) | ~150 |
| `static/js/render-overview.js` | `renderTeamCards`, `renderOverviewEmpty`, overview click handlers | ~150 |
| `static/js/render-detail.js` | Action queue, alert banner, completion bar, activity cards, message feed, kanban, task timeline | ~500 |
| `static/js/render-timeline.js` | Swim lane chart, event markers, SVG connectors | ~250 |
| `static/js/handlers.js` | Permission approve/deny, send message, remove member, batch operations, `ensureWriteApiKey` | ~150 |
| `static/js/app.js` | `init()`, polling loop, navigation, tab switching, event listeners | ~200 |

**Load order** in dashboard.html:
```html
<script src="/static/js/helpers.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/render-overview.js"></script>
<script src="/static/js/render-detail.js"></script>
<script src="/static/js/render-timeline.js"></script>
<script src="/static/js/handlers.js"></script>
<script src="/static/js/app.js"></script>
```

Communication between modules via the shared `state` object (defined in helpers.js, used everywhere).

**Goal**: Exact same behavior as before, just split across files. Verify by running the app and testing all views/tabs.

**Files modified**: `templates/dashboard.html` (script tags), `static/app.js` → **deleted** and replaced by `static/js/*.js`

---

## Phase 2: Layout Restructure — Two-Column Single Page

### Remove
- Tab navigation bar (`<nav>` with `.tab-btn` buttons)
- `switchTab()`, `updateTabUI()`, `state.currentTab`

### Restructure
Detail view HTML becomes two columns:
- **Left column (65%)**: Message feed with send form + filters
- **Right column (35%)**: Agent sidebar + compact task list + collapsible timeline

### Keep (unchanged this phase)
- Action queue and alert banner (consolidated in Phase 3)
- Completion bar (integrated in Phase 5)
- Existing render functions (just repositioned in new layout)

**Files modified**: `templates/dashboard.html`, `static/js/render-detail.js`, `static/js/app.js`

---

## Phase 3: Consolidate Permission Banners → Action Bar

### Delete
- `#alert-banner` section from `dashboard.html`
- `renderAlertBanner()` function

### Modify
- `renderActionQueue()` → rename to `renderActionBar()`
- Becomes the single place for permissions + stalled agents + blocked tasks
- Keep: "Approve All" button for 2+ permissions, inline Approve/Deny buttons, priority coloring

### Polling update
- Remove `renderAlertBanner()` calls from poll loop
- `renderActionBar()` receives both `action_queue` and `pending_permissions` data

**Files modified**: `templates/dashboard.html`, `static/js/render-detail.js`, `static/js/app.js`

---

## Phase 4: Message Feed Redesign

### Content messages (type `"plain"` with substantive text)
- Full-width cards with agent-colored left border
- Markdown-rendered body via `marked.js` CDN (~28KB)
- Agent name, timestamp, direction (→ target) in header
- White background, generous padding

### System messages (idle, permission_request/response, shutdown_request/response)
- Compact single-line rows, no card wrapper
- Muted gray text (text-xs text-gray-400)
- Icon prefix: clock for idle, lock for permission, power for shutdown
- Hidden by default behind "Show system events" toggle

### Markdown rendering
- Add `<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js">` to dashboard.html
- Render cache (`Map` keyed by message timestamp+hash) to avoid re-parsing every 2s poll
- Custom CSS class `.msg-markdown` for typography: headings, lists, code blocks, bold, links
- Sanitize output (marked.js sanitize option + escapeHtml for untrusted content)

**Files modified**: `templates/dashboard.html`, `static/js/render-detail.js`, `static/styles.css`

---

## Phase 5: Right Panel — Agent Sidebar, Compact Tasks, Collapsible Timeline

### Agent sidebar (replaces horizontal activity cards)
- Summary line at top: `Agents (5)    8/13 tasks (62%)` with thin progress bar
- Vertical list of agent cards, each showing:
  - Color dot + name + status badge (Active/Stalled/Idle/Completed)
  - Compact stats: `3/5 tasks` + model badge
  - Stall warning when applicable
- Delete standalone `#completion-bar` section

### Compact task list (replaces kanban board)
- Compact list grouped by status
- Show pending + in-progress by default, completed behind toggle
- Each task: one line with `#id`, truncated subject, owner dot, status icon
- Minimal search/filter bar above

### Collapsible timeline
- Timeline (swim lanes) moves to bottom of right panel, collapsed by default *THIS WAS CHANGED IN FINAL DESIGN - TIMELINE IS IMPORTANT AND SHOULDN'T BE MOVED FROM CENTER DISPLAY
- "Expand timeline" button — only fetches `/api/teams/{name}/agent-timeline` when expanded
- Saves an API call per poll when collapsed

**Files modified**: `templates/dashboard.html`, `static/js/render-detail.js`, `static/js/render-timeline.js`, `static/js/app.js`

---

## Phase 6: Cleanup

### Remove API Key Prompt
- Delete `ensureWriteApiKey()` function and all callers
- Delete `state.writeApiKey` and localStorage reads/writes for `agent_monitor_write_api_key`
- Keep `X-API-Key` header in `_jsonHeaders()` — always send empty string (backend handles gracefully)

### Polish
- Responsive breakpoints: right panel stacks below message feed at `< lg`
- Scroll position preservation in message feed across poll re-renders
- "N new messages" indicator when user has scrolled up
- Clean up any dead CSS classes from removed elements

**Files modified**: `static/js/handlers.js`, `static/js/api.js`, `static/js/helpers.js`, `static/styles.css`

---

## Polling Updates (applies across phases)

- **Current**: Snapshot + 1 tab-specific endpoint per poll
- **New**: Snapshot + messages per poll (tasks come from snapshot counts). Timeline only when expanded.
- No backend changes needed — existing endpoints provide all required data.

---

## Files Summary

| File | Change |
|------|--------|
| `templates/dashboard.html` | New two-column layout, remove tabs/alert-banner/completion-bar, add marked.js CDN, update script tags |
| `static/app.js` | **Delete** (replaced by `static/js/*.js` modules) |
| `static/js/helpers.js` | **New** — shared utilities and state |
| `static/js/api.js` | **New** — API layer |
| `static/js/render-overview.js` | **New** — overview grid |
| `static/js/render-detail.js` | **New** — detail page: action bar, messages, sidebar, tasks |
| `static/js/render-timeline.js` | **New** — swim lane chart |
| `static/js/handlers.js` | **New** — user action handlers |
| `static/js/app.js` | **New** — init, polling, navigation |
| `static/styles.css` | Add `.msg-markdown` typography styles for rendered markdown |

**No backend changes required.**

---

## Verification

1. **Run existing tests**: `pytest` in project root — no backend changes means all tests should pass
2. **After each phase**: Start the monitor (`python run.py`), navigate to a team detail, verify:
   - Phase 1: All existing functionality works identically after split
   - Phase 2: All content visible on one page without tabs
   - Phase 3: Single action bar, no duplicate permission display
   - Phase 4: Content messages render markdown, system messages are compact
   - Phase 5: Agent sidebar + compact tasks + collapsible timeline in right panel
   - Phase 6: No API key prompt, responsive layout works
3. **Browser DevTools**: Check for console errors, verify polling calls are correct
