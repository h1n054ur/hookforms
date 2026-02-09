<p align="center">
  <img src="logo.png" alt="HookForms" width="120">
</p>

<h1 align="center">HookForms</h1>

<p align="center">Self-hosted webhook inbox with Gmail email forwarding. Point your HTML forms at a HookForms endpoint and get submissions delivered straight to your inbox.</p>

```
HTML Form  -->  POST /hooks/contact-form  -->  Gmail notification
```

> **Want serverless instead?** Check out [hookforms-cloud](https://github.com/h1n054ur/hookforms-cloud) — runs entirely on Cloudflare Workers (D1, KV, Queues). No Docker or VPS needed.
>
> [![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/h1n054ur/hookforms-cloud)

## Features

- **Webhook inboxes** — create named endpoints that capture any HTTP request
- **Gmail forwarding** — form submissions forwarded as clean HTML emails via Gmail API
- **Per-inbox sender name** — emails show "Acme Corp" instead of a generic name
- **Turnstile bot protection** — optional Cloudflare Turnstile verification per inbox
- **Webhook forwarding** — optionally relay events to another URL (Slack, Discord, etc.)
- **API key auth** — scoped keys for managing inboxes programmatically
- **Rate limiting** — Redis-backed per-IP rate limiting with lockout protection
- **Event history** — stored events with configurable retention (default 30 days)
- **Cloudflare Tunnel** — expose to the internet without opening ports
- **Docker Compose** — one command to deploy everything

## Quick Start

```bash
git clone https://github.com/h1n054ur/hookforms.git
cd hookforms

# Configure
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, ADMIN_API_KEY, REDIS_PASSWORD

# Deploy
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head
```

Your API is now running at `http://localhost:8000`.

## Usage

### 1. Create an inbox

```bash
curl -X POST http://localhost:8000/v1/hooks/inboxes \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "contact-form",
    "description": "Website contact form",
    "notify_email": "you@gmail.com",
    "email_subject_prefix": "[Website]",
    "sender_name": "My Website"
  }'
```

### 2. Point your form at it

```html
<form action="https://hooks.yourdomain.com/hooks/contact-form" method="POST">
  <input type="text" name="name" placeholder="Name" required>
  <input type="email" name="email" placeholder="Email" required>
  <textarea name="message" placeholder="Message" required></textarea>
  <button type="submit">Send</button>
</form>
```

Or send JSON:

```bash
curl -X POST https://hooks.yourdomain.com/hooks/contact-form \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane", "email": "jane@example.com", "message": "Hello!"}'
```

### 3. Get an email

You'll receive a formatted HTML email with all form fields, a reply button, and the inbox slug in the footer. The sender name shows whatever you configured (e.g. "My Website").

## Gmail Setup

Email forwarding requires a one-time Gmail OAuth2 setup:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth 2.0 Client ID (Desktop application)
3. Download the JSON and save it as `config/gmail/credentials.json`
4. Run the auth script:

```bash
pip install google-auth-oauthlib
python scripts/gmail_auth.py
```

5. Set `GMAIL_SENDER_EMAIL` in your `.env` to the Gmail address you authorized
6. Restart: `docker compose restart api worker`

## Cloudflare Tunnel (Optional)

Expose HookForms to the internet without opening ports:

1. [Install cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/) and create a tunnel
2. Copy `config/cloudflared/config.yml.example` to `config/cloudflared/config.yml`
3. Fill in your tunnel ID and hostname
4. Place your tunnel credentials JSON in `config/cloudflared/`
5. Start with the tunnel profile:

```bash
docker compose --profile tunnel up -d
```

## API Reference

### Public (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST/PUT/PATCH/DELETE` | `/hooks/{slug}` | Receive a webhook event |
| `GET` | `/health` | Health check |

### Authenticated (X-API-Key header)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/hooks/inboxes` | List inboxes |
| `POST` | `/v1/hooks/inboxes` | Create inbox |
| `PATCH` | `/v1/hooks/inboxes/{slug}` | Update inbox |
| `DELETE` | `/v1/hooks/inboxes/{slug}` | Delete inbox + events |
| `GET` | `/v1/hooks/{slug}/events` | List events for inbox |
| `POST` | `/v1/auth/keys` | Create API key (admin) |
| `GET` | `/v1/auth/keys` | List API keys (admin) |
| `DELETE` | `/v1/auth/keys/{id}` | Revoke API key (admin) |

### Inbox fields

| Field | Description |
|-------|-------------|
| `slug` | URL-safe name used in the webhook URL |
| `description` | What this inbox is for |
| `notify_email` | Comma-separated email recipients |
| `email_subject_prefix` | Prefix for email subjects (e.g. `[Website]`) |
| `sender_name` | Display name in the From field (e.g. `Acme Corp`) |
| `forward_url` | Relay events to another URL |
| `turnstile_secret` | Cloudflare Turnstile secret for bot protection |

## Architecture

```
                         ┌──────────────┐
  HTML Form / curl  ───> │  cloudflared │ ──> ┌─────────┐
                         │  (optional)  │     │   API   │ ──> PostgreSQL
                         └──────────────┘     │ FastAPI │ ──> Redis
                                              └─────────┘
                                                   │
                                              ┌─────────┐
                                              │ Worker  │ (event cleanup cron)
                                              │   ARQ   │
                                              └─────────┘
                                                   │
                                              Gmail API
```

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_PASSWORD` | Yes | — | Database password |
| `ADMIN_API_KEY` | Yes | — | Master admin API key |
| `REDIS_PASSWORD` | Yes | — | Redis password |
| `GMAIL_SENDER_EMAIL` | No | — | Gmail address for sending |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `EVENT_RETENTION_DAYS` | No | `30` | Days to keep events before cleanup |

## License

[MIT](LICENSE)
