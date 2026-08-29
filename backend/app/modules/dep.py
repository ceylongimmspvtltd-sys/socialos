"""API auth & tenant resolution + audit helper."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.context import set_context
from app.core.security import hash_api_key
from app.db.base import get_db
from app.db.models import AuditLog, Tenant


def resolve_tenant(x_api_key: str = Header(default=""), db: Session = Depends(get_db)) -> Tenant:
    if not x_api_key:
        raise HTTPException(401, "X-API-Key header required")
    tenant = db.query(Tenant).filter(Tenant.api_key_hash == hash_api_key(x_api_key)).first()
    if tenant is None:
        raise HTTPException(401, "invalid API key")
    set_context(tenant.id, actor="api")
    return tenant


def audit(db: Session, tenant_id: str, action: str, entity_type: str = "", entity_id: str = "",
          detail: dict | None = None) -> None:
    db.add(AuditLog(tenant_id=tenant_id, actor="api", action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail or {}))
    db.commit()


def scoped_ws(db: Session, tenant: Tenant, workspace_id: str):
    ws = next((w for w in tenant.workspaces if w.id == workspace_id), None)
    if ws is None:
        raise HTTPException(404, f"workspace '{workspace_id}' not found for tenant")
    return ws
