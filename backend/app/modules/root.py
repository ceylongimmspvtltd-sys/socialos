"""Root endpoints: health + landing dashboard (inline styles only — no external assets)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.db.base import get_db
from app.db.models import (Campaign, ContentItem, PostAnalytics, ScheduledPost, Tenant,
                           Workspace, ClientApproval)
from app.modules.dep import resolve_tenant

router = APIRouter(tags=["root"])


@router.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": __version__,
            "database": "postgres" if settings.is_postgres else "sqlite-demo",
            "queue": settings.queue_backend, "connectors": "mock" if settings.mock_connectors else "live",
            "llm": settings.llm_provider}


@router.get("/api/stats")
def stats(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    tid = tenant.id
    return {
        "app": settings.app_name,
        "tenant": tenant.name,
        "workspaces": db.query(Workspace).filter(Workspace.tenant_id == tid).count(),
        "campaigns": db.query(Campaign).count(),
        "content_items": db.query(ContentItem).count(),
        "scheduled_posts": db.query(ScheduledPost).filter(ScheduledPost.tenant_id == tid).count(),
        "published": db.query(ScheduledPost).filter(ScheduledPost.tenant_id == tid,
                                                    ScheduledPost.publish_status == "PUBLISHED").count(),
        "pending_approvals": db.query(ClientApproval).filter(ClientApproval.status == "pending").count(),
        "impressions": sum(r[0] for r in db.query(PostAnalytics.impressions).all()),
        "engagements": sum(r[0] for r in db.query(PostAnalytics.engagements).all()),
    }


@router.get("/", include_in_schema=False)
def landing():
    return _HTML


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>C Tech SocialOS — Autonomous AI Social Platform</title>
<style>
:root{--bg:#0b1020;--card:#141b31;--ink:#e8ecff;--dim:#93a0c8;--acc:#6c8cff;--ok:#3ddc97;--warn:#ffb86c;--bad:#ff6c8c}
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);padding:32px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:26px;letter-spacing:.3px} .sub{color:var(--dim);margin:6px 0 26px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:26px}
.card{background:var(--card);border:1px solid #232d52;border-radius:12px;padding:14px 16px}
.k{font-size:26px;font-weight:700}.card small{color:var(--dim)}
.panel{background:var(--card);border:1px solid #232d52;border-radius:12px;padding:18px;margin-bottom:18px}
.panel h2{font-size:15px;margin-bottom:10px;color:#c3cfff}
.row{display:flex;flex-wrap:wrap;gap:8px}
.tag{border:1px solid #2c3a6b;border-radius:99px;padding:3px 10px;font-size:12px;color:var(--dim)}
.tag.on{color:var(--ok);border-color:var(--ok)}
.flow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12.5px;color:var(--dim)}
.flow b{color:var(--ink);background:#1b2547;border-radius:8px;padding:5px 9px;font-weight:600}
.arw{color:var(--acc)}
a{color:var(--acc);text-decoration:none} code{background:#0d1428;border-radius:6px;padding:2px 6px;font-size:12.5px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td,th{padding:6px 8px;border-bottom:1px solid #1d2749;text-align:left}th{color:var(--dim);font-weight:600}
.pill{padding:2px 9px;border-radius:99px;font-size:11.5px}
.p-ok{background:rgba(61,220,151,.15);color:var(--ok)}.p-w{background:rgba(255,184,108,.15);color:var(--warn)}
.p-b{background:rgba(108,140,255,.15);color:var(--acc)}
</style></head><body><div class="wrap">
<h1>⚡ C Tech SocialOS</h1>
<div class="sub">Multi-niche autonomous AI social marketing &amp; publishing — Hospitality · Travel · Salons · Production · E-Commerce → 7 channels</div>
<div class="grid" id="stats"></div>
<div class="panel"><h2>Multi-agent pipeline</h2>
<div class="flow"><b>Trend Hunter</b><span class="arw">→</span><b>Niche Strategy</b><span class="arw">→</span>
<b>Multi-Modal Creator</b><span class="arw">→</span><b>Brand Safety Gate</b><span class="arw">→</span>
<b>Governance (3-tier)</b><span class="arw">→</span><b>Queue / DLQ</b><span class="arw">→</span><b>Publish ×7</b>
<span class="arw">→</span><b>Analytics → PPI feedback</b></div></div>
<div class="panel"><h2>Publishing calendar (next up)</h2><table id="cal"><tr><th>When (UTC)</th><th>Platform</th><th>Title</th><th>Status</th></tr></table></div>
<div class="panel"><h2>Channels</h2><div class="row">
<span class="tag">YouTube</span><span class="tag">Instagram</span><span class="tag">Facebook</span>
<span class="tag">TikTok</span><span class="tag">Pinterest</span><span class="tag">Reddit</span><span class="tag">Telegram</span>
<span class="tag on" id="mode">…</span></div>
<p style="margin-top:10px;color:var(--dim);font-size:13px">API docs: <a href="/docs">/docs</a> · auth header <code>X-API-Key: demo-key</code> · portal approve/reject at <code>/portal/{token}</code></p>
</div>
<script>
const S = (l,v,d=0)=>document.querySelector(l).textContent=v;
fetch('/api/stats',{headers:{'X-API-Key':'demo-key'}}).then(r=>r.json()).then(s=>{
  document.getElementById('stats').innerHTML=[
    ['Workspaces',s.workspaces],['Campaigns',s.campaigns],['Content items',s.content_items],
    ['Scheduled',s.scheduled_posts],['Published',s.published],['Approvals pending',s.pending_approvals],
    ['Impressions',s.impressions.toLocaleString()],['Engagements',s.engagements.toLocaleString()]
  ].map(([k,v])=>`<div class="card"><div class="k">${v}</div><small>${k}</small></div>`).join('');
  document.getElementById('mode').textContent = 'mock publish mode — connectors simulated';
});
fetch('/api/schedule',{headers:{'X-API-Key':'demo-key'}}).then(r=>r.json()).then(rows=>{
  document.getElementById('cal').innerHTML += rows.slice(0,8).map(p=>{
    const cls = p.publish_status==='PUBLISHED'?'p-ok':(p.publish_status==='QUEUED'?'p-b':'p-w');
    return `<tr><td>${p.scheduled_at.slice(0,16).replace('T',' ')}</td><td>${p.platform}</td>
    <td>${(p.title||'').slice(0,60)||'—'}</td><td><span class="pill ${cls}">${p.publish_status}</span></td></tr>`;
  }).join('');
});
</script></div></body></html>"""
