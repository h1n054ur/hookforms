<p align="center">
  <img src="logo.png" alt="HookForms" width="120">
</p>

<h1 align="center">HookForms</h1>

<p align="center">Self-hosted webhook inbox with multi-channel notifications. Point your HTML forms at a HookForms endpoint and get submissions delivered to email, Discord, Slack, Teams, Telegram, ntfy, or any webhook URL.</p>

```
HTML Form  -->  POST /hooks/contact-form  -->  Discord, Slack, Email, ...
```

> **Want serverless instead?** Check out [hookforms-cloud](https://github.com/h1n054ur/hookforms-cloud) — runs entirely on Cloudflare Workers (D1, KV, Queues). No Docker or VPS needed.
>
> [![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/h1n054ur/hookforms-cloud)

## Features

- **Webhook inboxes** — create named endpoints that capture any HTTP request
- **Multi-channel notifications** — route submissions to Discord, Slack, Microsoft Teams, Telegram, ntfy, email, or any webhook URL
- **Auto-detection** — paste a URL and HookForms detects the channel type automatically
- **Multiple email providers** — Gmail (OAuth), Resend, SendGrid, or SMTP — configure globally or per-inbox
- **Per-inbox sender name** — emails show "Acme Corp" instead of a generic name
- **Turnstile bot protection** — optional Cloudflare Turnstile verification per inbox
- **API key auth** — scoped keys for managing inboxes programmatically
- **Rate limiting** — Redis-backed per-IP rate limiting with lockout protection
- **Event history** — stored events with configurable retention (default 30 days)
- **Cloudflare Tunnel** — expose to the internet without opening ports
- **Docker Compose** — one command to deploy everything
- **Backward compatible** — legacy `notify_email` and `forward_url` still work

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

### 3. Add notification channels

```bash
# Send to Discord (auto-detected from URL)
curl -X POST http://localhost:8000/v1/hooks/inboxes/contact-form/channels \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "webhook", "config": {"url": "https://discord.com/api/webhooks/123/abc"}}'

# Send to Slack (auto-detected from URL)
curl -X POST http://localhost:8000/v1/hooks/inboxes/contact-form/channels \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "webhook", "config": {"url": "https://hooks.slack.com/services/T00/B00/xxx"}}'

# Send email via configured provider
curl -X POST http://localhost:8000/v1/hooks/inboxes/contact-form/channels \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "email", "config": {"recipients": ["team@example.com"]}}'
```

When you pass `type: "webhook"`, HookForms auto-detects the specific platform from the URL (Discord, Slack, Teams, etc.) and formats the payload accordingly. Each inbox can have multiple channels — all fire in parallel when a submission comes in.

### 4. Get notified

Submissions are delivered to all configured channels with rich formatting (Discord embeds, Slack blocks, HTML emails, etc.).

> **Legacy mode**: If you set `notify_email` or `forward_url` on the inbox directly (without channels), those still work the same as before.

## Notification Channels

| Channel | Auto-detected from |
|---------|-------------------|
| Discord | `discord.com/api/webhooks/` |
| Slack | `hooks.slack.com/services/` |
| Microsoft Teams | `*.webhook.office.com/` |
| Telegram | `api.telegram.org/bot` |
| ntfy | `ntfy.sh/` |
| Webhook | Any other URL |
| Email | Set `type: "email"` with config |

## Email Providers

Configure a global email provider, or override per-inbox:

```bash
# Set global provider (e.g. Resend)
curl -X PUT http://localhost:8000/v1/hooks/config/email-provider \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "resend", "config": {"api_key": "re_..."}}'
```

Supported providers: **Gmail** (OAuth), **Resend**, **SendGrid**, **SMTP** (self-hosted only).

If no provider is configured, HookForms falls back to Gmail via environment variables (the v1 behavior).

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
| `POST` | `/v1/hooks/inboxes/{slug}/channels` | Add notification channel |
| `GET` | `/v1/hooks/inboxes/{slug}/channels` | List channels |
| `PATCH` | `/v1/hooks/inboxes/{slug}/channels/{id}` | Update channel |
| `DELETE` | `/v1/hooks/inboxes/{slug}/channels/{id}` | Remove channel |
| `GET` | `/v1/hooks/config/email-provider` | Get email provider config |
| `PUT` | `/v1/hooks/config/email-provider` | Set email provider |
| `DELETE` | `/v1/hooks/config/email-provider` | Remove email provider |
| `POST` | `/v1/auth/keys` | Create API key (admin) |
| `GET` | `/v1/auth/keys` | List API keys (admin) |
| `DELETE` | `/v1/auth/keys/{id}` | Revoke API key (admin) |

## Architecture

```
                         ┌──────────────┐
  HTML Form / curl  ───> │  cloudflared │ ──> ┌─────────┐
                         │  (optional)  │     │   API   │ ──> PostgreSQL
                         └──────────────┘     │ FastAPI │ ──> Redis
                                              └─────────┘
                                                   │
                                              Dispatcher
                                             ┌──┬──┬──┐
                                             │  │  │  │
                                        Discord Slack Email ...
                                              └─────────┘
                                                   │
                                              ┌─────────┐
                                              │ Worker  │ (event cleanup cron)
                                              │   ARQ   │
                                              └─────────┘
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
