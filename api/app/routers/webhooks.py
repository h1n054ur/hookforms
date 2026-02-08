import html
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_scope
from app.database import get_db
from app.models.webhook import WebhookInbox, WebhookEvent
from app.redis import redis as redis_client
from app.response import paginated_response, single_response
from app.schemas.webhook import (
    WebhookInboxCreate,
    WebhookInboxUpdate,
    WebhookInboxResponse,
    WebhookEventResponse,
)
from app.security import is_safe_url, safe_http_client

wh_logger = logging.getLogger("webhooks")

router = APIRouter(prefix="/hooks", tags=["webhooks"])
public_router = APIRouter(tags=["webhooks-public"])


# ---------------------------------------------------------------------------
# Public: receive webhooks
# ---------------------------------------------------------------------------


@public_router.api_route(
    "/hooks/{slug}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Receive a webhook",
)
async def receive_webhook(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WebhookInbox).where(WebhookInbox.slug == slug, WebhookInbox.is_active.is_(True))
    )
    inbox = result.scalar_one_or_none()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")

    # Parse body
    body = None
    try:
        body = await request.json()
    except Exception:
        try:
            raw = await request.body()
            body = {"raw": raw.decode("utf-8", errors="replace")}
        except Exception:
            pass

    # Optional: Cloudflare Turnstile verification
    if inbox.turnstile_secret and body and isinstance(body, dict):
        turnstile_token = body.pop("cf-turnstile-response", None)
        if not turnstile_token:
            raise HTTPException(status_code=400, detail="Missing Turnstile verification token")
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                verify_resp = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={
                        "secret": inbox.turnstile_secret,
                        "response": turnstile_token,
                        "remoteip": request.headers.get("cf-connecting-ip", ""),
                    },
                )
                verify_result = verify_resp.json()
                if not verify_result.get("success"):
                    raise HTTPException(status_code=403, detail="Turnstile verification failed")
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Turnstile verification unavailable")

    event = WebhookEvent(
        inbox_id=inbox.id,
        method=request.method,
        headers=dict(request.headers),
        body=body,
        query_params=dict(request.query_params),
        source_ip=request.client.host if request.client else None,
    )
    db.add(event)
    await db.commit()

    # Optional: forward to another URL
    if inbox.forward_url:
        try:
            async with safe_http_client(timeout=10, follow_redirects=True) as client:
                await client.request(
                    method=request.method,
                    url=inbox.forward_url,
                    json=body,
                    headers={"X-Forwarded-From": f"hookforms/hooks/{slug}"},
                )
        except Exception:
            wh_logger.exception("Forwarding failed for /hooks/%s", slug)

    # Optional: email notification
    if inbox.notify_email and body:
        # Per-inbox rate limit: max 10 emails per 10 minutes
        rate_key = f"webhook_email_rate:{inbox.id}"
        try:
            email_count = await redis_client.incr(rate_key)
            if email_count == 1:
                await redis_client.expire(rate_key, 600)
            if email_count > 10:
                wh_logger.warning("Email rate limit hit for inbox %s", slug)
                return {"status": "received", "event_id": str(event.id)}
        except Exception:
            wh_logger.warning("Email rate limiter unavailable for inbox %s", slug)

        try:
            import asyncio
            from functools import partial
            from app.mail import send_email

            prefix = html.escape(inbox.email_subject_prefix or f"[{slug}]")
            slug_escaped = html.escape(slug)
            inbox_sender_name = inbox.sender_name

            sender_name = html.escape(str(body.get("name", "Unknown")))
            sender_email_raw = str(body.get("email", ""))
            sender_email = html.escape(sender_email_raw)
            subject_detail = f"from {sender_name}" if sender_name != "Unknown" else "New Submission"

            # Build field rows
            field_rows = ""
            skip_keys = {"raw", "source", "cf-turnstile-response"}
            for key, val in body.items():
                if key in skip_keys or not val:
                    continue
                label = html.escape(key.replace("_", " ").title())
                escaped_val = html.escape(str(val))
                field_rows += (
                    f"<tr>"
                    f'<td style="padding:10px 14px;font-weight:600;color:#555;'
                    f'white-space:nowrap;vertical-align:top;border-bottom:1px solid #eee;">{label}</td>'
                    f'<td style="padding:10px 14px;color:#222;border-bottom:1px solid #eee;">{escaped_val}</td>'
                    f"</tr>"
                )

            html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#1a1a2e;padding:24px 32px;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">{prefix} {subject_detail}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px;">
            <p style="margin:0 0 16px;color:#666;font-size:14px;">A new form submission was received:</p>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eee;border-radius:6px;overflow:hidden;">
              {field_rows}
            </table>
          </td>
        </tr>
        {f'<tr><td style="padding:0 32px 24px;"><a href="mailto:{sender_email}" style="display:inline-block;padding:10px 20px;background:#1a1a2e;color:#fff;text-decoration:none;border-radius:5px;font-size:14px;">Reply to {sender_name}</a></td></tr>' if sender_email_raw else ''}
        <tr>
          <td style="padding:16px 32px;background:#fafafa;border-top:1px solid #eee;">
            <p style="margin:0;color:#999;font-size:12px;">Delivered by {html.escape(inbox_sender_name or 'HookForms')} &middot; <code style="background:#eee;padding:2px 6px;border-radius:3px;font-size:11px;">/hooks/{slug_escaped}</code></p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

            plain_prefix = inbox.email_subject_prefix or f"[{slug}]"
            plain_subject_detail = (
                f"from {body.get('name', 'Unknown')}" if body.get("name") else "New Submission"
            )

            recipients = [e.strip() for e in inbox.notify_email.split(",") if e.strip()]
            loop = asyncio.get_running_loop()
            for recipient in recipients:
                await loop.run_in_executor(
                    None,
                    partial(
                        send_email,
                        to=recipient,
                        subject=f"{plain_prefix} {plain_subject_detail}",
                        body=html_body,
                        html=True,
                        sender_name=inbox_sender_name,
                    ),
                )
        except Exception as exc:
            wh_logger.error(
                "Email notification failed for /hooks/%s: %s", slug, exc, exc_info=True
            )

    return {"status": "received", "event_id": str(event.id)}


# ---------------------------------------------------------------------------
# Authenticated: manage inboxes
# ---------------------------------------------------------------------------


@router.get("/inboxes", summary="List webhook inboxes")
async def list_inboxes(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    total = (await db.execute(select(func.count()).select_from(WebhookInbox))).scalar()
    result = await db.execute(
        select(WebhookInbox).order_by(WebhookInbox.created_at.desc()).limit(limit).offset(offset)
    )
    items = [WebhookInboxResponse.from_inbox(i) for i in result.scalars().all()]
    return paginated_response(items, total, limit, offset)


@router.post("/inboxes", status_code=201, summary="Create a webhook inbox")
async def create_inbox(
    body: WebhookInboxCreate,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    if body.forward_url:
        safe, reason = is_safe_url(body.forward_url)
        if not safe:
            raise HTTPException(status_code=400, detail=f"Invalid forward_url: {reason}")

    inbox = WebhookInbox(**body.model_dump())
    db.add(inbox)
    await db.commit()
    await db.refresh(inbox)
    return single_response(WebhookInboxResponse.from_inbox(inbox))


@router.patch("/inboxes/{slug}", summary="Update a webhook inbox")
async def update_inbox(
    slug: str,
    body: WebhookInboxUpdate,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    result = await db.execute(select(WebhookInbox).where(WebhookInbox.slug == slug))
    inbox = result.scalar_one_or_none()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")

    update_data = body.model_dump(exclude_unset=True)
    if "forward_url" in update_data and update_data["forward_url"]:
        safe, reason = is_safe_url(update_data["forward_url"])
        if not safe:
            raise HTTPException(status_code=400, detail=f"Invalid forward_url: {reason}")

    if update_data:
        await db.execute(
            update(WebhookInbox).where(WebhookInbox.slug == slug).values(**update_data)
        )
        await db.commit()
        await db.refresh(inbox)

    return single_response(WebhookInboxResponse.from_inbox(inbox))


@router.delete("/inboxes/{slug}", status_code=204, summary="Delete a webhook inbox")
async def delete_inbox(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    result = await db.execute(select(WebhookInbox).where(WebhookInbox.slug == slug))
    inbox = result.scalar_one_or_none()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    await db.delete(inbox)
    await db.commit()


@router.get("/{slug}/events", summary="List webhook events")
async def list_events(
    slug: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    _key=Depends(require_scope("webhooks")),
):
    result = await db.execute(select(WebhookInbox).where(WebhookInbox.slug == slug))
    inbox = result.scalar_one_or_none()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")

    total = (
        await db.execute(
            select(func.count()).select_from(WebhookEvent).where(WebhookEvent.inbox_id == inbox.id)
        )
    ).scalar()

    events = await db.execute(
        select(WebhookEvent)
        .where(WebhookEvent.inbox_id == inbox.id)
        .order_by(WebhookEvent.received_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [WebhookEventResponse.model_validate(e) for e in events.scalars().all()]
    return paginated_response(items, total, limit, offset)
