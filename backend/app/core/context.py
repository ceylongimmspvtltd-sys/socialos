"""Request-scoped tenant context. Every DB query is filtered by the resolved tenant;
on PostgreSQL an equivalent Row-Level Security policy is additionally enforced (see migrations)."""
from __future__ import annotations

import contextvars
from typing import Any
from uuid import uuid4

current_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_tenant_id", default=None)
current_workspace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_workspace_id", default=None)
current_actor: contextvars.ContextVar[str] = contextvars.ContextVar("current_actor", default="system")


def new_id() -> str:
    return uuid4().hex


def set_context(tenant_id: str | None = None, workspace_id: str | None = None, actor: str = "system") -> None:
    if tenant_id:
        current_tenant_id.set(tenant_id)
    if workspace_id:
        current_workspace_id.set(workspace_id)
    current_actor.set(actor)


def get_context() -> dict[str, Any]:
    return {
        "tenant_id": current_tenant_id.get(),
        "workspace_id": current_workspace_id.get(),
        "actor": current_actor.get(),
    }
