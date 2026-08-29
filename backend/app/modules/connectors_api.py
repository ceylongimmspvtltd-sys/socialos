"""Social platform connection endpoints: OAuth start/callback, account status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors import adapter_class, build_connector, client_credentials
from app.core.config import settings
from app.core.security import generate_pkce_pair, generate_state, vault
from app.db.base import get_db
from app.db.models import SocialAccount, Tenant
from app.modules.dep import audit, resolve_tenant, scoped_ws

router = APIRouter(prefix="/api/connectors", tags=["connectors"])

_PKCE_STORE: dict[str, str] = {}  # state -> verifier (prod: Redis with TTL)


@router.get("/platforms")
def platforms(workspace_id: str | None = None, tenant: Tenant = Depends(resolve_tenant),
              db: Session = Depends(get_db)):
    out = []
    for platform in ["youtube", "instagram", "facebook", "tiktok", "pinterest", "reddit", "telegram"]:
        cid, _ = client_credentials(platform)
        cls = adapter_class(platform)
        connected = False
        if workspace_id:
            ws = scoped_ws(db, tenant, workspace_id)
            acct = db.query(SocialAccount).filter(SocialAccount.workspace_id == ws.id,
                                                  SocialAccount.platform == platform).first()
            connected = bool(acct and acct.status == "connected")
        out.append({"platform": platform, "oauth": bool(cls.auth_url), "pkce": cls.pkce_required(),
                    "scopes": cls.default_scopes, "app_configured": bool(cid or settings.mock_connectors),
                    "connected": connected})
    return out


@router.post("/{platform}/oauth/start")
def oauth_start(platform: str, workspace_id: str, redirect_uri: str,
                tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    scoped_ws(db, tenant, workspace_id)
    if platform not in ["youtube", "instagram", "facebook", "tiktok", "pinterest", "reddit"]:
        raise HTTPException(422, "platform does not use OAuth (telegram uses a bot token)")
    cid, _ = client_credentials(platform)
    if not cid and not settings.mock_connectors:
        raise HTTPException(409, f"configure SOCIALOS_{platform.upper()}_CLIENT_ID first")
    cls = adapter_class(platform)(client_id=cid or "mock-client-id")
    state = generate_state()
    verifier = challenge = None
    if cls.pkce_required():
        verifier, challenge = generate_pkce_pair()
        _PKCE_STORE[state] = verifier
    url = cls.authorize_url(state=state, redirect_uri=redirect_uri, code_challenge=challenge)
    audit(db, tenant.id, "oauth.start", "platform", platform, {"workspace": workspace_id})
    return {"authorize_url": url, "state": state, "pkce": cls.pkce_required(),
            "note": "mock mode: call /callback with any code to provision a simulated account"}


@router.get("/{platform}/oauth/callback")
async def oauth_callback(platform: str, code: str, state: str, workspace_id: str,
                         redirect_uri: str = "", tenant: Tenant = Depends(resolve_tenant),
                         db: Session = Depends(get_db)):
    ws = scoped_ws(db, tenant, workspace_id)
    verifier = _PKCE_STORE.pop(state, None)
    cls = adapter_class(platform)(client_id=client_credentials(platform)[0] or "mock",
                                  client_secret=client_credentials(platform)[1] or "mock")
    if settings.mock_connectors:
        bundle = {"access_token": f"mock-access-{platform}-{code[:8]}",
                  "refresh_token": f"mock-refresh-{platform}", "expires_in": 3600,
                  "scopes": cls.default_scopes}
    else:
        try:
            tb = await cls.exchange_code(code, redirect_uri=redirect_uri, code_verifier=verifier)
            bundle = {"access_token": tb.access_token, "refresh_token": tb.refresh_token,
                      "expires_in": tb.expires_in, "scopes": tb.scopes}
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"token exchange failed: {e}")

    from datetime import datetime, timedelta, timezone

    acct = db.query(SocialAccount).filter(SocialAccount.workspace_id == ws.id,
                                          SocialAccount.platform == platform).first()
    if acct is None:
        acct = SocialAccount(workspace_id=ws.id, platform=platform, account_id=f"{platform}_{ws.id[:8]}")
        db.add(acct)
    acct.access_token_enc = vault.encrypt(bundle["access_token"])
    acct.refresh_token_enc = vault.encrypt(bundle.get("refresh_token", ""))
    acct.scopes = bundle.get("scopes", [])
    acct.status = "connected"
    acct.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=bundle.get("expires_in") or 3600)
    db.commit()
    audit(db, tenant.id, "oauth.connected", "social_account", acct.id, {"platform": platform})
    return {"status": "connected", "platform": platform, "account_id": acct.account_id,
            "token_storage": "AES-256-GCM vault"}


@router.post("/{platform}/test-publish")
async def test_publish(platform: str, workspace_id: str, body: str = "Hello from SocialOS 🚀",
                       tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    """Dry-run a connector for this workspace (mock mode = deterministic simulation)."""
    from app.connectors.base import PublishRequest

    ws = scoped_ws(db, tenant, workspace_id)
    acct = db.query(SocialAccount).filter(SocialAccount.workspace_id == ws.id,
                                          SocialAccount.platform == platform).first()
    if acct is None:
        if not settings.mock_connectors:
            raise HTTPException(409, "connect the account first")
        acct = SocialAccount(workspace_id=ws.id, platform=platform, account_id=f"mock_{platform}",
                             status="connected")
        db.add(acct)
        db.commit()
    connector = build_connector(platform, acct)
    result = await connector.publish(PublishRequest(body=body, title="SocialOS test"))
    return {"ok": result.ok, "external_id": result.external_id, "error": result.error, "mock": connector.mock}
