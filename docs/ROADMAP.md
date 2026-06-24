# Hubble — Phased Fix & Improvement Plan

This roadmap captures the prioritized fixes identified during the June 2025 code audit. Each phase is independently shippable.

---

## Phase 0: Documentation & Hygiene ✅ SHIPPED (SAFE-NOW)

- Rename product to "Hubble" in README and banner
- Move .md files into `/docs/` structure
- Delete dead `claude_suggestion/` folder
- Add `slack-sdk` to requirements.txt
- Create `docs/architecture.md` and `docs/ROADMAP.md`

**Status:** Shipped on `chore/docs-and-hygiene` branch.

---

## Phase 1: Resolve Dual Interactivity (CRITICAL, NEEDS-TESTING)

**Problem:** `app.py` has raw Flask handlers for `/slack/interactive` AND `slack_handler.py` has Bolt `@action()` handlers. Both contain complete, overlapping implementations.

**Actions:**
1. Determine which path is live (check Slack app's Interactivity Request URL)
2. If `/slack/interactive` is live → remove Bolt `@action`/`@view` handlers from `slack_handler.py`
3. If `/slack/events` is live → remove entire `/slack/interactive` route and all `handle_*_direct` functions from `app.py`
4. Remove ~500 lines of dead code

**Files:** `app.py` or `slack_handler.py` (one or the other)
**Risk:** Medium — wrong path removal breaks buttons/modals
**Rollback:** Revert commit
**Test plan:** Manual test all buttons (View/Edit, Close, Assign, Status) + modal submit in both main and internal channels

---

## Phase 2: Fix Ticket ID Race (CRITICAL, NEEDS-TESTING)

**Problem:** `ticket_service.py` holds `next_ticket_id` in memory, incremented without a lock. Bolt's thread pool (5 threads) can produce duplicate IDs.

**Actions:**
- Option A: Add `threading.Lock` around the read + increment
- Option B: Replace counter with atomic read-MAX-from-sheet inside `append_ticket()`

**Files:** `ticket_service.py` (Option A) or `sheets_service.py` (Option B)
**Risk:** Low (Option A) / Medium (Option B adds latency)
**Rollback:** Revert commit
**Test plan:** Load test with concurrent simulated messages; verify no duplicate/skipped IDs

---

## Phase 3: Sheets Read Caching (IMPORTANT, NEEDS-TESTING)

**Problem:** A single message triggers 3–5 full-sheet reads + 3–5 Config tab reads. No caching.

**Actions:**
1. Add 30s TTL cache for `get_channel_config_map()`
2. Add 10s TTL cache for `get_tickets()` (mitigated by in-memory dedup for freshness)
3. Remove redundant `get_tickets()` call inside `append_ticket()` (caller already checked)

**Files:** `sheets_service.py`
**Risk:** Medium — stale cache could mask a just-created ticket (mitigated by in-memory dedup Layer 3)
**Rollback:** Revert commit
**Test plan:** Monitor Google Sheets API quota before/after; verify ticket creation still works

**Expected improvement:** ~8 API calls → 2 per message within cache window.

---

## Phase 4: File Decomposition (IMPORTANT, NEEDS-TESTING)

**Problem:** `app.py` (1015 lines), `slack_handler.py` (1145 lines), `sheets_service.py` (1035 lines) are unmaintainable monoliths.

**Actions:**
- Split `app.py` → `app.py` (slim) + `routes/` modules
- Split `slack_handler.py` → `slack_handler.py` (slim) + `handlers/` modules
- Split `sheets_service.py` → `sheets_service.py` (slim) + `sheets/` modules

**Files:** All three, new directories
**Risk:** Medium — import path changes, subtle circular imports possible
**Rollback:** Revert commit
**Test plan:** Full manual regression of all features. Ideally Phase 5 (tests) ships first.

---

## Phase 5: Add Tests & CI (IMPORTANT, NEEDS-TESTING)

**Problem:** Zero automated tests. All `test_*.py` files are manual scripts requiring live credentials.

**Actions:**
1. Add `pytest`, `pytest-mock` to `requirements.txt`
2. Write unit tests for `TicketService`, `EventDeduplicator`, `MessageDeduplicator`
3. Write integration test stubs (mocked Sheets + Slack)
4. Add GitHub Actions CI workflow (lint + test on PR)
5. Move old `test_*.py` scripts to `scripts/` or delete

**Files:** `tests/`, `.github/workflows/ci.yml`, `requirements.txt`
**Risk:** None (additive)
**Rollback:** Revert commit
**Ship criteria:** CI passes on PR, coverage ≥ critical paths

---

## Phase 6: Minor Fixes & Hardening (MINOR, SAFE after testing)

| Fix | File | Risk |
|-----|------|------|
| Move hardcoded workspace URL to env var | `sheets_service.py:207-211` | Low |
| Replace `print()` with `logger` | `sheets_service.py` | None |
| Fix `clear_all_data` range `A:K` → `A:N` | `sheets_service.py:823` | Low |
| Move inline `import json` to file top | `sheets_service.py` | None |
| Add basic auth to `/tickets` and `/test/message` | `app.py` | Low |

**Rollback:** Revert commit per fix
**Test plan:** Smoke test Sheets operations after range fix

---

## Backlog / Future

- Swap Sheets backend for PostgreSQL or SQLite (V2)
- Rate limiting on public API endpoints
- Slack Socket Mode support (eliminates need for public URL)
- Multi-workspace support (remove hardcoded workspace ID)
- Audit git history for leaked secrets (`gitleaks` / `trufflehog`)
