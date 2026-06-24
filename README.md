# Hubble — Slack Ticketing Bot

Hubble turns Slack messages into trackable tickets backed by Google Sheets. Any message posted in a monitored channel automatically creates a ticket, replies in a thread, posts to an internal team channel, and keeps everything in sync.

## Overview

- **Automatic ticket creation** from any message in configured channels
- **Multi-channel support** with per-channel configuration (priorities, templates, admins)
- **Internal team channels** with rich ticket cards, assign-to-me, and status toggle
- **Bidirectional thread sync** between public and internal channels
- **Dynamic modal forms** for viewing/editing tickets (admin and creator permissions)
- **Google Sheets backend** for zero-infrastructure persistence

## Quick Start

### Prerequisites

- Python 3.9+
- A Slack workspace with admin access to create apps
- A Google Cloud service account with Sheets API enabled
- A Google Spreadsheet (shared with the service account)

### Local Setup

```bash
# Clone and enter the repo
git clone <repo-url> && cd Hubble-Version0

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Copy the env template and fill in your values
cp .env.template .env
# Edit .env with your tokens / IDs

# Run locally
python app.py
```

The server starts on port 3000 by default. Use ngrok or Cloudflare Tunnel to expose it for Slack event delivery during development.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | App signing secret |
| `TARGET_CHANNEL_ID` | (Legacy) Primary monitored channel |
| `GOOGLE_CREDENTIALS_PATH` | Path to service account JSON (local dev) |
| `GOOGLE_CREDENTIALS` | JSON string of credentials (production) |
| `GOOGLE_SPREADSHEET_ID` | Spreadsheet ID for ticket storage |
| `ADMIN_USER_IDS` | Comma-separated global admin Slack user IDs |
| `PORT` | Server port (default: 3000) |

## Architecture

See [docs/architecture.md](docs/architecture.md) for a full system diagram and component breakdown.

**TL;DR:** Slack events → Flask + Slack Bolt → TicketService → Google Sheets. Thread replies and internal channel cards are posted via the Slack Web API.

## Deployment (Render)

The app is deployed on Render as a Web Service.

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn wsgi:app --workers 1`
- **Health check:** `GET /health`

Set all environment variables in the Render dashboard. Use `GOOGLE_CREDENTIALS` (JSON string) instead of a file path in production.

See [docs/deployment.md](docs/deployment.md) for the full deployment runbook.

## Configuration

### Slack App Settings

| Setting | Value |
|---------|-------|
| Event Subscriptions Request URL | `https://<your-domain>/slack/events` |
| Interactivity Request URL | `https://<your-domain>/slack/interactive` |
| Bot Token Scopes | `chat:write`, `channels:history`, `groups:history`, `users:read`, `commands` |
| Subscribed Bot Events | `message.channels`, `message.groups` |

### Google Sheets Structure

- **Tickets tab:** Main ticket data (A:N columns)
- **Config tab:** Per-channel settings (channel ID, admins, default assignee, priorities, modal template, internal channel)
- **Modal Templates tab:** Dynamic form field definitions per template key

See [docs/setup/multi-channel.md](docs/setup/multi-channel.md) for channel configuration details.

## Development

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code |
| `fix/*` | Bug fixes |
| `feat/*` | New features |
| `chore/*` | Docs, hygiene, non-runtime changes |

All work happens on feature branches. PRs to `main` require review.

### No CI Yet

There is currently no automated CI pipeline. Test files in the repo are manual run scripts that require live credentials. Adding pytest + GitHub Actions CI is on the roadmap.

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask routes, direct interactive handlers |
| `slack_handler.py` | Slack Bolt event/action handlers, deduplication |
| `ticket_service.py` | Ticket CRUD operations |
| `sheets_service.py` | Google Sheets API interactions |
| `internal_channel_handler.py` | Internal channel card formatting |
| `modal_builder.py` | Dynamic modal form construction |
| `modal_submission_handler.py` | Modal submit processing |

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and debugging steps.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the phased improvement plan covering dual-interactivity resolution, ticket ID safety, Sheets caching, file decomposition, and CI.
