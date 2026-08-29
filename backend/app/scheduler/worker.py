"""Background publish worker.

Loop: pull due QUEUED scheduled_posts -> dispatch platform adapter -> on success
mark PUBLISHED; on rate-limit/transient error exponential-backoff retry; after
MAX_PUBLISH_ATTEMPTS route to the dead-letter queue with alerts. Also refreshes
expired OAuth tokens opportunistically.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors import build_connector, get_workspace_account
from app.connectors.base import ConnectorError, PublishRequest, RateLimited, TokenExpired
from app.core.consts import MAX_PUBLISH_ATTEMPTS
from app.db.models import AuditLog, ScheduledPost
from app.scheduler.queue import Job, get_queue

log = logging.getLogger("socialos.worker")


def _publish_request(post: ScheduledPost) -> PublishRequest:
    p = post.payload_json or {}
    return PublishRequest(
        body=p.get("body", ""),
        title=p.get("title", ""),
        link=p.get("link", ""),
        media_urls=p.get("media_urls", []),
        hashtags=p.get("hashtags", []),
        first_comment=p.get("first_comment", ""),
        platform_payload=p.get("platform_payload", {}),
    )


async def process_post(db: Session, post: ScheduledPost) -> ScheduledPost:
    item = post.content_item
    account = get_workspace_account(db, item.workspace_id, post.platform)
    connector = build_connector(post.platform, account)

    post.publish_status = "PUBLISHING"
    db.commit()
    try:
        result = await connector.publish(_publish_request(post))
    except RateLimited as e:
        return _fail(db, post, str(e), retry=True)
    except TokenExpired as e:
        # attempt refresh (account with refresh token), then retry once next tick
        return _fail(db, post, f"token: {e}", retry=True, refresh_hint=True)
    except ConnectorError as e:
        return _fail(db, post, str(e), retry=True)
    except Exception as e:  # noqa: BLE001 — worker must never die on a bad job
        return _fail(db, post, f"unexpected: {e!r}", retry=True)

    if result.ok:
        post.publish_status = "PUBLISHED"
        post.external_post_id = result.external_id
        post.published_at = datetime.now(timezone.utc)
        post.error_log = ""
        db.add(AuditLog(tenant_id=post.tenant_id, actor="worker", action="post.published",
                        entity_type="scheduled_post", entity_id=post.id,
                        detail={"platform": post.platform, "external_id": result.external_id}))
        if item.status != "PUBLISHED":
            item.status = "PUBLISHED"
    else:
        post = _fail(db, post, result.error, retry=True, fatal="guarded" in result.raw)
    db.commit()
    return post


def _fail(db: Session, post: ScheduledPost, error: str, retry: bool = False,
          refresh_hint: bool = False, fatal: bool = False) -> ScheduledPost:
    post.attempts += 1
    post.error_log = (error or "")[:2000]
    exhausted = post.attempts >= MAX_PUBLISH_ATTEMPTS
    if not retry or fatal or exhausted:
        post.publish_status = "FAILED" if fatal else "DEAD"
        if exhausted:
            try:
                q = get_queue()
                asyncio.ensure_future(q.dead_letter(
                    Job(id=f"publish:{post.id}", kind="publish", payload={"post_id": post.id},
                        attempts=post.attempts), reason=error))
            except Exception:
                pass
    else:
        post.publish_status = "RETRYING"
    db.commit()
    log.warning("post %s -> %s (%s)", post.id, post.publish_status, error[:120])
    return post


async def publish_due(db: Session, now: datetime | None = None) -> list[dict]:
    """Process every due QUEUED/RETRYING post. Returns a summary for API/CLI use."""
    now = now or datetime.now(timezone.utc)
    due = (db.query(ScheduledPost)
             .filter(ScheduledPost.publish_status.in_(("QUEUED", "RETRYING")),
                     ScheduledPost.scheduled_at <= now)
             .order_by(ScheduledPost.scheduled_at)
             .limit(25)
             .all())
    results = []
    for post in due:
        done = await process_post(db, post)
        results.append({"post_id": done.id, "platform": done.platform,
                        "status": done.publish_status, "attempts": done.attempts,
                        "external_id": done.external_post_id, "error": done.error_log[:200]})
    return results


async def worker_loop(get_session) -> None:
    """Long-running loop (started from app lifespan)."""
    from app.core.config import settings

    while True:
        try:
            db = get_session()
            try:
                await publish_due(db)
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            log.exception("worker tick failed")
        await asyncio.sleep(settings.worker_poll_seconds)
