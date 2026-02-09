# HookForms v2 — Notification Engine Sprint Plan

## Vision

Transform HookForms from a Gmail-only webhook inbox into a fully configurable notification engine. Users pick their email provider, connect multiple notification channels per inbox, and the system auto-detects and formats payloads for each destination.

---

## Architecture Changes Required

### Current (v1)

```
Inbox
  ├── notify_email (comma-separated string)      → Gmail only
  ├── forward_url (single URL)                    → Discord/Slack auto-detect, generic fallback
  └── email_subject_prefix / sender_name          → Per-inbox branding
```

### Target (v2)

```
Inbox
  └── has many → NotificationChannel
                    ├── type: "email" | "discord" | "slack" | "teams" | "telegram" | "ntfy" | "webhook"
                    ├── config: JSON (provider-specific settings)
                    ├── is_active: boolean
                    └── created_at
  └── has one → EmailProvider (global or per-inbox)
                    ├── type: "gmail" | "resend" | "sendgrid" | "smtp"
                    ├── config: JSON (credentials, sender, etc.)
                    └── is_active
```

Key design decisions:

1. **NotificationChannel** replaces `forward_url` and `notify_email` as flat columns. Each inbox can have multiple channels (e.g., Discord AND email AND Telegram simultaneously).
2. **EmailProvider** is a separate concept from channels. A channel of type `email` references the configured email provider. Provider config can be global (instance-wide default) or per-inbox override.
3. **Backward compatibility**: The old `forward_url` and `notify_email` fields continue to work during migration. A migration script converts them to NotificationChannel rows.
4. **Auto-detection preserved**: If a user creates a channel of type `webhook` with a Discord URL, the system auto-detects and formats. But users can also explicitly set `type: "discord"` to bypass detection.

---

## Email Providers

| Provider | CF Workers | Self-Hosted | Config Fields | Free Tier |
|---|---|---|---|---|
| Gmail (current) | Yes (OAuth2 REST) | Yes (OAuth2 SDK) | client_id, client_secret, refresh_token, sender_email | Unlimited (own account) |
| Resend | Yes | Yes | api_key, from_email | 100/day, 3k/month |
| SendGrid | Yes | Yes | api_key, from_email | 100/day |
| Generic SMTP | No (no TCP) | Yes | host, port, username, password, use_tls, from_email | N/A |

**Implementation priority**: Gmail (keep) > Resend > SendGrid > SMTP (self-hosted only)

---

## Notification Channels

| Channel | Detection Pattern | Payload Format | Both Platforms |
|---|---|---|---|
| Discord (current) | `discord.com/api/webhooks` | Embed with fields, gold color, footer | Yes |
| Slack (current) | `hooks.slack.com/` | mrkdwn blocks | Yes |
| Microsoft Teams | `webhook.office.com` or `logic.azure.com` | Adaptive Card with FactSet | Yes |
| Telegram | `api.telegram.org/bot` | HTML-formatted sendMessage | Yes |
| Ntfy.sh | `ntfy.sh/` (hosted) or explicit type | Title header + text body | Yes |
| Zapier | `hooks.zapier.com` | Flat JSON (enhanced with metadata) | Yes |
| Make | `hook.` + `.make.com` | Flat JSON (enhanced with metadata) | Yes |
| n8n | `n8n.cloud/webhook` (cloud) or explicit type | Flat JSON (enhanced with metadata) | Yes |
| Generic Webhook | Default fallback | Raw JSON + X-Forwarded-From header | Yes |
| Email | N/A (configured via email provider) | HTML email via configured provider | Yes |

---

## Epics and Stories

### Epic 1: Notification Channel Data Model

**Goal**: Replace flat `forward_url`/`notify_email` columns with a flexible multi-channel model.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 1.1 | Design `notification_channels` table schema | High | S | Fields: id, inbox_id (FK), type (enum), label, config (JSON), is_active, created_at |
| 1.2 | CF Worker: Create D1 migration for `notification_channels` | High | S | SQL migration file |
| 1.3 | Self-hosted: Create Alembic migration for `notification_channels` | High | S | SQLAlchemy model + Alembic revision |
| 1.4 | CF Worker: Add CRUD API endpoints for channels (`/v1/hooks/inboxes/:slug/channels`) | High | M | POST, GET, PATCH, DELETE |
| 1.5 | Self-hosted: Add CRUD API endpoints for channels | High | M | Mirror CF Worker API surface |
| 1.6 | Write backward-compat migration script: convert existing `forward_url` and `notify_email` rows into `notification_channels` | High | M | Both platforms |
| 1.7 | Keep `forward_url`/`notify_email` working as shortcuts in the create/update inbox API (auto-create channels) | Medium | S | Convenience for simple setups |

### Epic 2: Channel Dispatcher

**Goal**: Build a pluggable dispatcher that routes submissions to all active channels for an inbox.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 2.1 | Design channel dispatcher interface/pattern | High | S | Each channel type implements a `format(inbox, body)` -> `{url, method, headers, body}` function |
| 2.2 | CF Worker: Implement dispatcher that iterates inbox channels and fires all | High | M | Use `waitUntil` for fire-and-forget per channel |
| 2.3 | Self-hosted: Implement dispatcher (async, parallel via `asyncio.gather`) | High | M | Replace inline forwarding logic in webhooks.py |
| 2.4 | Move Discord formatting into dedicated `discord.ts` / `discord.py` adapter | Medium | S | Extract from monolithic webhook handler |
| 2.5 | Move Slack formatting into dedicated `slack.ts` / `slack.py` adapter | Medium | S | Extract from monolithic webhook handler |
| 2.6 | Auto-detection logic: if channel type is `webhook`, inspect URL and delegate to specific adapter | Medium | S | Preserves current behavior for users who just paste a URL |

### Epic 3: New Notification Channels

**Goal**: Add Teams, Telegram, Ntfy, and enhanced automation platform support.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 3.1 | Microsoft Teams adapter | High | M | Adaptive Card with FactSet for fields. Detect `webhook.office.com` or `logic.azure.com` |
| 3.2 | Telegram adapter | High | M | HTML parse_mode, bold labels. Config requires `chat_id`. Detect `api.telegram.org/bot`. Extract chat_id from config, token from URL |
| 3.3 | Ntfy.sh adapter | Medium | S | POST with Title/Tags headers and plain text body. Detect `ntfy.sh/` |
| 3.4 | Enhanced Zapier/Make/n8n formatting | Low | S | Add metadata envelope: `inbox_slug`, `submitted_at`, `submission_id` alongside flat form fields |
| 3.5 | Generic webhook adapter (refactor current) | Medium | S | Clean up: always POST (not preserve original method), add configurable custom headers |
| 3.6 | Implement all adapters for CF Worker (TypeScript) | High | L | All channels in src/channels/*.ts |
| 3.7 | Implement all adapters for self-hosted (Python) | High | L | All channels in api/app/channels/*.py |

### Epic 4: Email Provider Abstraction

**Goal**: Support multiple email providers beyond Gmail.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 4.1 | Design email provider interface | High | S | `send(to, subject, html_body, from_name)` — each provider implements this |
| 4.2 | Refactor Gmail into provider adapter (CF Worker) | High | M | Extract from gmail.ts into providers/gmail.ts |
| 4.3 | Refactor Gmail into provider adapter (self-hosted) | High | M | Extract from mail.py into providers/gmail.py |
| 4.4 | Resend provider adapter (both platforms) | High | S | Simple fetch POST to api.resend.com/emails |
| 4.5 | SendGrid provider adapter (both platforms) | Medium | S | fetch POST to api.sendgrid.com/v3/mail/send |
| 4.6 | SMTP provider adapter (self-hosted only) | Medium | M | aiosmtplib, config: host/port/user/pass/tls |
| 4.7 | Email provider configuration API endpoint | High | M | Global config: `POST /v1/config/email-provider` with type + credentials |
| 4.8 | CF Worker: Store provider config in KV or D1 | High | S | Secrets via wrangler secret or D1 encrypted column |
| 4.9 | Self-hosted: Store provider config in DB or env vars | High | S | Allow both env-based (simple) and DB-based (multi-provider) |
| 4.10 | Email HTML template extraction | Medium | S | Move inline HTML template to shared template module |

### Epic 5: Configuration UI / DX

**Goal**: Make everything easily configurable via API with clear documentation.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 5.1 | Channel configuration examples in API docs | High | M | Curl examples for each channel type |
| 5.2 | Email provider setup guides in docs | High | M | Step-by-step for Gmail, Resend, SendGrid, SMTP |
| 5.3 | Update webhook forwarding docs page with all new channels | High | M | Teams, Telegram, Ntfy sections |
| 5.4 | Update environment variables docs | Medium | S | New env vars for provider config |
| 5.5 | Add channel type validation with helpful error messages | Medium | S | "Unknown channel type 'telegarm'. Did you mean 'telegram'?" |
| 5.6 | Add config validation per channel type | Medium | M | e.g., Telegram requires chat_id, SMTP requires host/port |
| 5.7 | Update README for both repos | Medium | S | Mention multi-channel, multi-provider |

### Epic 6: Reliability and Observability

**Goal**: Add retry logic and delivery status tracking.

| ID | Story | Priority | Effort | Notes |
|---|---|---|---|---|
| 6.1 | CF Worker: Queue-based channel dispatch (not just email) | Medium | L | Send all notifications through queues for retry |
| 6.2 | Self-hosted: ARQ task for notification dispatch | Medium | L | Finally use the idle ARQ worker for its intended purpose |
| 6.3 | Delivery status tracking per channel | Low | L | New `notification_deliveries` table: channel_id, event_id, status, attempts, last_error |
| 6.4 | Retry logic for failed notifications | Low | M | Exponential backoff, max 3 retries |
| 6.5 | Dead letter handling | Low | M | Store failed notifications for manual review |

---

## Sprint Breakdown

### Sprint 1 — Foundation (Week 1-2)

**Goal**: New data model in place, dispatcher pattern, existing channels refactored.

| Stories | Total Effort |
|---|---|
| 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7 | ~M-L |
| 2.1, 2.2, 2.3, 2.4, 2.5, 2.6 | ~M-L |
| 4.1, 4.2, 4.3, 4.10 | ~M |

**Deliverable**: Both platforms have the new channel model, dispatcher, and Gmail refactored as a provider. Existing behavior is preserved (backward compat). All current tests pass.

### Sprint 2 — New Channels + Email Providers (Week 3-4)

**Goal**: All new notification channels and email providers implemented.

| Stories | Total Effort |
|---|---|
| 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7 | ~L |
| 4.4, 4.5, 4.6, 4.7, 4.8, 4.9 | ~M-L |

**Deliverable**: Teams, Telegram, Ntfy adapters working. Resend and SendGrid as email alternatives. SMTP for self-hosted. Test on live CF deployment (hookforms-cf).

### Sprint 3 — Docs, DX, Reliability (Week 5)

**Goal**: Full documentation, config validation, and optional reliability features.

| Stories | Total Effort |
|---|---|
| 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7 | ~M-L |
| 6.1, 6.2 | ~L (stretch) |
| 6.3, 6.4, 6.5 | ~L (stretch/optional) |

**Deliverable**: Docs site updated with all new channels and providers. Config validation in place. Optionally, queue-based dispatch with retries.

---

## Channel Config JSON Schemas

Reference for what `config` looks like per channel type:

### Email

```json
{ "recipients": ["alice@example.com", "bob@example.com"] }
```

### Discord

```json
{ "webhook_url": "https://discord.com/api/webhooks/..." }
```

### Slack

```json
{ "webhook_url": "https://hooks.slack.com/services/..." }
```

### Microsoft Teams

```json
{ "webhook_url": "https://xxx.webhook.office.com/webhookb2/..." }
```

### Telegram

```json
{ "bot_url": "https://api.telegram.org/bot<TOKEN>/sendMessage", "chat_id": "123456789" }
```

### Ntfy

```json
{ "url": "https://ntfy.sh/my-topic", "priority": 3 }
```

### Zapier / Make / n8n / Generic Webhook

```json
{ "url": "https://hooks.zapier.com/hooks/catch/...", "custom_headers": { "X-Secret": "abc" } }
```

---

## API Surface (New Endpoints)

### Channel Management

```
POST   /v1/hooks/inboxes/:slug/channels      — Add a notification channel
GET    /v1/hooks/inboxes/:slug/channels      — List channels for an inbox
PATCH  /v1/hooks/inboxes/:slug/channels/:id  — Update a channel
DELETE /v1/hooks/inboxes/:slug/channels/:id  — Remove a channel
```

### Email Provider Configuration

```
GET    /v1/config/email-provider             — Get current email provider config (secrets redacted)
PUT    /v1/config/email-provider             — Set/update email provider
DELETE /v1/config/email-provider             — Remove email provider (disables email notifications)
```

### Example: Create an inbox with multiple channels in one call

```bash
curl -X POST https://hookforms.yourdomain.com/v1/hooks/inboxes \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "contact-form",
    "description": "Main contact form",
    "channels": [
      { "type": "email", "config": { "recipients": ["me@gmail.com"] } },
      { "type": "discord", "config": { "webhook_url": "https://discord.com/api/webhooks/..." } },
      { "type": "telegram", "config": { "bot_url": "https://api.telegram.org/bot.../sendMessage", "chat_id": "123456" } }
    ]
  }'
```

### Backward-compatible shorthand (still works)

```bash
curl -X POST https://hookforms.yourdomain.com/v1/hooks/inboxes \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "simple-form",
    "notify_email": "me@gmail.com",
    "forward_url": "https://discord.com/api/webhooks/..."
  }'
```

This auto-creates two channels: one `email` and one `discord` (auto-detected from URL).

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Telegram bot token exposed in URL (stored in DB) | High | Encrypt channel config at rest. Redact in API responses. |
| Teams webhook deprecation (O365 Connectors retiring) | Medium | Target Workflows (Adaptive Cards) format primarily |
| SMTP not available in CF Workers | Medium | Document clearly. Offer Resend/SendGrid as alternatives. |
| Migration breaks existing inboxes | High | Backward-compat layer: old fields auto-create channels. Migration script tested thoroughly. |
| Queue-based dispatch adds complexity | Medium | Make it optional in Sprint 3. Fire-and-forget remains the default. |
| Rate limiting per channel vs per inbox | Low | Start with per-inbox, refine later if needed |

---

## Open Questions

1. **Per-inbox email provider override?** Should each inbox be able to use a different email provider, or is one global provider enough for v2?
2. **Channel ordering / priority?** If one channel fails, should it affect others? (Current answer: no, all are independent fire-and-forget.)
3. **Webhook signing?** Should we add HMAC signing for outbound webhooks so receivers can verify authenticity? (Nice to have, not MVP.)
4. **Config encryption at rest?** Channel configs contain secrets (API keys, bot tokens). Encrypt the `config` JSON column? Or rely on DB-level encryption?
