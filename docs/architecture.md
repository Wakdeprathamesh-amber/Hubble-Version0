# Architecture — Hubble Slack Ticketing Bot

## Current System (as of June 2025)

### High-Level Data Flow

```
Slack Event (message in channel)
  │
  ▼
Flask (app.py) — /slack/events route
  │  • X-Slack-Retry-Num header check → short-circuit with 200
  │
  ▼
Slack Bolt (SlackRequestHandler)
  │  • process_before_response=False → ack 200 immediately
  │  • Handler runs in background thread
  │
  ▼
SlackHandler.handle_message_events (slack_handler.py)
  │  • Event ID dedup (in-memory TTL cache)
  │  • Message dedup (channel_id + ts, in-memory TTL cache)
  │  • Sheets dedup (full sheet scan — safety net)
  │
  ▼
TicketService.create_ticket (ticket_service.py)
  │  • Increments in-memory ticket ID counter
  │  • Calls SheetsService.append_ticket
  │
  ▼
SheetsService (sheets_service.py)
  │  • Appends row to Google Sheets via Sheets API v4
  │
  ▼
Post-creation side effects (back in slack_handler.py):
  • Post threaded confirmation message with buttons
  • Post ticket card to internal team channel (if configured)
  • Store internal_message_ts back to sheet
```

### Component Responsibilities

| Component | File(s) | Role |
|-----------|---------|------|
| HTTP layer | `app.py`, `wsgi.py` | Flask routes, retry guard, CORS |
| Event processing | `slack_handler.py` | Bolt listeners for messages, actions, commands |
| Interactive handling | `app.py` (direct handlers) + `slack_handler.py` (Bolt handlers) | **⚠️ DUAL PATH — see Known Issues** |
| Ticket logic | `ticket_service.py` | CRUD, ID generation, status transitions |
| Persistence | `sheets_service.py` | All Google Sheets API calls |
| Internal channels | `internal_channel_handler.py` | Rich card formatting, post/update |
| Modal forms | `modal_builder.py`, `modal_view_builder.py` | Dynamic block construction |
| Modal submission | `modal_submission_handler.py` | Extract values, update ticket |

### Deduplication Layers (fix/duplicate-tickets branch)

1. **Flask level:** Reject any request with `X-Slack-Retry-Num` header
2. **Event ID cache:** TTL-based dict keyed on Slack `event_id` (5 min)
3. **Message cache:** TTL-based dict keyed on `channel_id:ts` (10 min)
4. **Sheets check:** Full scan of tickets sheet for matching `thread_ts` (safety net)

### Deployment

- **Platform:** Render (Web Service)
- **Process model:** 1 gunicorn worker (required for in-memory dedup)
- **Persistence:** Google Sheets (no database)
- **Secrets:** Environment variables on Render

---

## Known Issues (Current State)

### 1. Dual Interactivity Handlers

Both of these exist and contain complete, overlapping implementations:

- `app.py` lines 85–930: Flask route `/slack/interactive` with `handle_*_direct()` functions
- `slack_handler.py` lines 639–1145: Bolt `@action()` and `@view()` handlers via `/slack/events`

**Which is live depends on the Slack app's Interactivity Request URL setting.** If it points to `/slack/interactive`, the Bolt action handlers are dead code (events still go through Bolt). If it points to `/slack/events`, the Flask direct handlers are dead code.

**Impact:** Confusing codebase, risk of double-processing if misconfigured.

### 2. Ticket ID Race Condition

`ticket_service.py` holds `next_ticket_id` in memory and increments without a lock. With Bolt's background thread pool, concurrent events can produce duplicate IDs.

### 3. Excessive Sheets Reads

A single message triggers 3–5 full-sheet reads (get_all_tickets + get_channel_config_map) with no caching. At scale this hits Google API rate limits.

---

## Target V1 Architecture

Goals: single interaction path, one sheet read per event, safe ticket IDs, Sheets backend retained.

### Changes from Current

| Area | Current | Target V1 |
|------|---------|-----------|
| Interaction path | Dual (Flask direct + Bolt handlers) | Single path via Bolt only; remove `/slack/interactive` route |
| Ticket IDs | In-memory counter, no lock | Thread-locked counter OR atomic read-MAX-from-sheet |
| Sheets reads | 3–5 full reads per message | TTL-cached reads (30s config, 10s tickets) → max 1 fresh read |
| File structure | 3 monolith files (1000+ lines each) | Split into focused modules (~200 lines each) |
| Testing | Manual scripts only | pytest unit tests + GitHub Actions CI |
| Dedup | 4 layers (good) | Keep all 4 layers, improve Layer 4 with cache |

### Target Component Layout

```
hubble/
├── app.py                    (slim: Flask init + route registration)
├── routes/
│   ├── events.py             (retry guard + Bolt delegation)
│   └── api.py                (/health, /tickets, /)
├── handlers/
│   ├── message_handler.py    (ticket creation, thread replies)
│   ├── action_handlers.py    (button clicks)
│   └── command_handlers.py   (slash commands)
├── services/
│   ├── ticket_service.py     (CRUD with locked ID generation)
│   ├── sheets_service.py     (Sheets API, slim)
│   └── sheets_cache.py       (TTL cache wrapper)
├── internal_channel_handler.py
├── modal_builder.py
├── modal_submission_handler.py
└── dedup.py                  (EventDeduplicator, MessageDeduplicator)
```

The Sheets backend is retained for V1. A future V2 could swap in PostgreSQL or SQLite without changing the service layer interface.
