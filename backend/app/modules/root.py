"""Root endpoints: health + full operations dashboard (self-contained SPA — no external assets)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.db.base import get_db
from app.db.models import (Campaign, ClientApproval, ContentItem, PostAnalytics,
                           ScheduledPost, Tenant, Workspace)
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
    return HTMLResponse(_HTML)


_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SocialOS — Operations Dashboard</title>
<style>
:root{--bg:#070b1a;--card:linear-gradient(180deg,rgba(148,180,255,.07),rgba(16,24,48,.55));--card2:rgba(56,80,140,.28);
--ink:#eaf0ff;--dim:#9fb0d6;--ash:#c9d4e8;--sky:#5ec8f8;--green:#39e6a3;--lpink:#ff9ecf;--lgreen:#a8f0c6;
--acc:var(--sky);--acc2:var(--green);--ok:var(--green);--warn:var(--lpink);--bad:#ff7ab0;--line:rgba(130,160,230,.22)}
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);min-height:100vh;position:relative}
/* ---- cosmic aurora + stars ---- */
body::before{content:"";position:fixed;inset:-35%;z-index:-2;
background:radial-gradient(42% 34% at 28% 28%,rgba(94,200,248,.20),transparent 70%),
radial-gradient(38% 30% at 72% 62%,rgba(168,240,198,.15),transparent 70%),
radial-gradient(36% 30% at 56% 22%,rgba(255,158,207,.15),transparent 70%),
radial-gradient(30% 26% at 12% 78%,rgba(201,212,232,.10),transparent 70%);
filter:blur(58px);animation:aurora 24s ease-in-out infinite alternate}
@keyframes aurora{from{transform:rotate(0deg) scale(1)}to{transform:rotate(16deg) scale(1.14)}}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background-image:
radial-gradient(1.6px 1.6px at 11% 18%,rgba(255,255,255,.85),transparent 60%),
radial-gradient(1.1px 1.1px at 32% 64%,rgba(255,255,255,.55),transparent 60%),
radial-gradient(1.4px 1.4px at 54% 12%,rgba(168,240,198,.8),transparent 60%),
radial-gradient(1px 1px at 68% 42%,rgba(255,255,255,.5),transparent 60%),
radial-gradient(1.7px 1.7px at 81% 74%,rgba(255,158,207,.8),transparent 60%),
radial-gradient(1px 1px at 23% 88%,rgba(255,255,255,.45),transparent 60%),
radial-gradient(1.3px 1.3px at 91% 22%,rgba(94,200,248,.85),transparent 60%),
radial-gradient(1px 1px at 44% 36%,rgba(255,255,255,.4),transparent 60%),
radial-gradient(1.2px 1.2px at 15% 52%,rgba(255,158,207,.6),transparent 60%),
radial-gradient(1px 1px at 62% 92%,rgba(168,240,198,.6),transparent 60%);animation:twinkle 5s ease-in-out infinite alternate}
@keyframes twinkle{from{opacity:.55}to{opacity:1}}
header{position:sticky;top:0;z-index:50;background:rgba(7,11,26,.72);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:10px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.logo{font-weight:800;font-size:17px;letter-spacing:.4px;color:var(--ash)}
.logo span{background:linear-gradient(90deg,var(--sky),var(--green) 55%,var(--lpink));-webkit-background-clip:text;background-clip:text;color:transparent}
nav{display:flex;gap:4px;flex-wrap:wrap}
nav button{background:none;border:1px solid transparent;color:var(--dim);padding:6px 12px;border-radius:10px;cursor:pointer;font-size:13px;font-weight:600;transition:.2s}
nav button.active{color:#fff;background:rgba(94,200,248,.13);border-color:rgba(94,200,248,.45);box-shadow:0 0 14px rgba(94,200,248,.18)}
nav button:hover{color:var(--ink)}
.spacer{flex:1}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}
.dot.ok{background:var(--green);box-shadow:0 0 10px var(--green)}.dot.bad{background:var(--bad)}.dot.wait{background:var(--sky);box-shadow:0 0 8px var(--sky)}
#conn{font-size:12px;color:var(--dim)}
main{max-width:1180px;margin:0 auto;padding:20px 18px 60px}
h2{font-size:18px;margin:6px 0 14px;color:var(--ink)}
h3{font-size:13px;color:var(--ash);margin:14px 0 8px;text-transform:uppercase;letter-spacing:.7px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;backdrop-filter:blur(14px);box-shadow:0 8px 28px rgba(3,8,25,.45)}
.grid{display:grid;gap:12px}
.g5{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.k{font-size:24px;font-weight:800;background:linear-gradient(90deg,#fff,var(--lgreen));-webkit-background-clip:text;background-clip:text;color:transparent}
.card small{color:var(--dim)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.tag{border:1px solid rgba(130,160,230,.35);border-radius:99px;padding:2px 10px;font-size:11.5px;color:var(--ash)}
.tag.on{color:#0b1f16;background:linear-gradient(90deg,var(--lgreen),var(--green));border-color:transparent;font-weight:700}
.pill{padding:2px 9px;border-radius:99px;font-size:11px;font-weight:700}
.p-ok{background:rgba(57,230,163,.16);color:var(--green)}
.p-w{background:rgba(255,158,207,.16);color:var(--lpink)}
.p-b{background:rgba(94,200,248,.16);color:var(--sky)}
.p-bad{background:rgba(255,122,176,.18);color:var(--bad)}
button.btn{background:linear-gradient(135deg,var(--sky),var(--green));color:#04121f;border:none;border-radius:10px;padding:8px 14px;font-weight:800;cursor:pointer;font-size:13px;box-shadow:0 4px 18px rgba(94,200,248,.3);transition:.2s}
button.btn:hover{filter:brightness(1.12);box-shadow:0 6px 24px rgba(94,200,248,.45)}
button.ghost{background:rgba(56,80,140,.28);color:var(--ink);border:1px solid var(--line);box-shadow:none}
button.danger{background:transparent;border:1px solid var(--bad);color:var(--bad)}
input,select,textarea{background:rgba(9,15,36,.72);border:1px solid var(--line);color:var(--ink);border-radius:10px;padding:8px 10px;font-size:13px;width:100%}
input:focus,select:focus,textarea:focus{border-color:var(--sky);box-shadow:0 0 0 3px rgba(94,200,248,.16);outline:none}
textarea{resize:vertical;min-height:80px}
label{font-size:12px;color:var(--dim);display:block;margin:8px 0 4px}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:7px 8px;border-bottom:1px solid rgba(130,160,230,.14);text-align:left}th{color:var(--dim);font-weight:600;font-size:12px}
.bar{height:8px;border-radius:6px;background:rgba(130,160,230,.15);overflow:hidden}
.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--sky),var(--green),var(--lpink));box-shadow:0 0 10px rgba(57,230,163,.4)}
.day{margin:10px 0 4px;font-size:12px;color:var(--sky);font-weight:800;letter-spacing:.6px}
.post{display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:11px;padding:8px 12px;margin:6px 0;backdrop-filter:blur(10px)}
.pf{width:74px;font-size:11px;font-weight:800;color:var(--sky)}
#wake{display:none;background:rgba(94,200,248,.12);border:1px solid rgba(94,200,248,.4);color:var(--sky);border-radius:10px;padding:8px 14px;margin:12px 0;font-size:13px}
.tabbtns{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.tabbtns button{background:rgba(56,80,140,.28);border:1px solid var(--line);color:var(--dim);border-radius:9px;padding:5px 12px;cursor:pointer;font-size:12px;font-weight:600}
.tabbtns button.active{color:#04121f;border-color:transparent;background:linear-gradient(90deg,var(--sky),var(--lgreen));font-weight:800}
.out{background:rgba(7,12,30,.8);border:1px solid var(--line);border-radius:11px;padding:12px;font-size:12.5px;white-space:pre-wrap;max-height:340px;overflow:auto;font-family:ui-monospace,Menlo,Consolas,monospace;color:var(--lgreen)}
.muted{color:var(--dim);font-size:12.5px}
.big{font-size:15px;font-weight:700}
.hide{display:none}
footer{color:var(--dim);font-size:12px;text-align:center;padding:18px}
.camp{cursor:pointer}.camp:hover{border-color:var(--sky);box-shadow:0 0 16px rgba(94,200,248,.22)}
.kpi{display:flex;justify-content:space-between;font-size:13px;padding:4px 0;border-bottom:1px dashed rgba(130,160,230,.25)}
::selection{background:rgba(94,200,248,.35)}
</style></head><body>
<header>
  <div class="logo">⚡ Social<span>OS</span></div>
  <nav id="nav">
    <button data-v="overview" class="active">Overview</button>
    <button data-v="calendar">Calendar</button>
    <button data-v="campaigns">Campaigns</button>
    <button data-v="analytics">Analytics</button>
    <button data-v="trends">Trends</button>
    <button data-v="settings">Settings</button>
  </nav>
  <div class="spacer"></div>
  <div id="conn"><span class="dot wait"></span>connecting…</div>
</header>
<div id="wake">⏳ Render free instance අඳෝනවට එනකම් බලාගන්න (30–60s) — retrying…</div>
<main>
  <section id="v-overview"></section>
  <section id="v-calendar" class="hide"></section>
  <section id="v-campaigns" class="hide"></section>
  <section id="v-analytics" class="hide"></section>
  <section id="v-trends" class="hide"></section>
  <section id="v-settings" class="hide"></section>
</main>
<footer>C Tech SocialOS v1.0 — demo-key auth · connectors in mock mode until API keys are configured</footer>
<script>
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const store={get base(){return localStorage.sosBase||(localStorage.sosBase=location.origin)},set base(v){localStorage.sosBase=v},
  get key(){return localStorage.sosKey||(localStorage.sosKey='demo-key')},set key(v){localStorage.sosKey=v}};
let WAKE=false;
async function api(path,opts={},tries=8){
  setConn('wait');
  for(let i=0;i<tries;i++){
    try{
      const r=await fetch(store.base+path,{...opts,headers:{'X-API-Key':store.key,'Content-Type':'application/json',...(opts.headers||{})}});
      const t=await r.text();
      if(r.status===401){setConn('bad');throw new Error('Invalid API key (Settings බලන්න)')}
      if(r.status===404&&t.trim()==='Not Found'){WAKE=true;$('#wake').style.display='block';await sleep(3000);continue}
      WAKE=false;$('#wake').style.display='none';setConn('ok');
      return {status:r.status,data:JSON.parse(t)}
    }catch(e){if(e.message.includes('API key'))throw e;await sleep(2500)}
  }
  setConn('bad');throw new Error('unreachable')
}
function setConn(s){const c=$('#conn');c.innerHTML={ok:'<span class="dot ok"></span>API live',wait:'<span class="dot wait"></span>waking…',bad:'<span class="dot bad"></span>offline'}[s]}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=n=>Number(n||0).toLocaleString();
const pclass=s=>s==='PUBLISHED'?'p-ok':(s==='QUEUED'||s==='PENDING'?'p-b':(s==='FAILED'||s==='DEAD'||s==='REJECTED'?'p-bad':'p-w'));
const PLATFORMS=['youtube','instagram','facebook','tiktok','pinterest','reddit','telegram'];
const NICHE_CHANNELS={hospitality:['instagram','facebook','tiktok','pinterest'],travel:['pinterest','youtube','instagram','reddit','facebook'],salon:['instagram','tiktok','facebook','telegram'],production:['youtube','reddit','instagram','pinterest'],ecom:['tiktok','pinterest','instagram','facebook','reddit']};

/* ---------- nav ---------- */
$('#nav').onclick=e=>{const b=e.target.closest('button');if(!b)return;
  $$('#nav button').forEach(x=>x.classList.toggle('active',x===b));
  $$('main section').forEach(s=>s.classList.add('hide'));
  $('#v-'+b.dataset.v).classList.remove('hide');
  ({overview:loadOverview,calendar:loadCalendar,campaigns:loadCampaigns,analytics:loadAnalytics,trends:loadTrends,settings:loadSettings}[b.dataset.v])();
};

/* ---------- overview ---------- */
async function loadOverview(){
  const v=$('#v-overview');v.innerHTML='<h2>Overview</h2><div class="muted">loading…</div>';
  const [st,plat]=await Promise.all([api('/api/stats'),api('/api/connectors/platforms').catch(()=>({data:[]}))]);
  const s=st.data;
  v.innerHTML=`<h2>Overview — ${esc(s.tenant)}</h2>
  <div class="grid g5">
    ${[['Workspaces',s.workspaces],['Campaigns',s.campaigns],['Content items',s.content_items],['Scheduled posts',s.scheduled_posts],['Published',s.published],['Pending approvals',s.pending_approvals],['Impressions',fmt(s.impressions)],['Engagements',fmt(s.engagements)]]
      .map(([k,n])=>`<div class="card"><div class="k">${n}</div><small>${k}</small></div>`).join('')}
  </div>
  <h3>Channels</h3>
  <div class="card"><div class="row">${(plat.data||[]).map(p=>`<span class="tag ${p.connected?'on':''}">${p.platform}${p.connected?' ✓':''}</span>`).join('')}</div>
  <p class="muted" style="margin-top:10px">Mock mode — connectors simulate publishing until API keys are added (Settings tab).</p></div>
  <h3>Quick actions</h3>
  <div class="row">
    <button class="btn" onclick="navTo('campaigns')">+ New AI Campaign</button>
    <button class="btn ghost" onclick="publishNow()">⚡ Publish due posts</button>
    <button class="btn ghost" onclick="syncAnalytics();navTo('analytics')">📈 Sync analytics</button>
  </div>`;
}
function navTo(t){document.querySelector(`#nav button[data-v=${t}]`).click()}
async function publishNow(){const r=await api('/api/schedule/worker/tick',{method:'POST'});
  alert(`Published/processed: ${r.data.processed}\n`+r.data.results.map(x=>`${x.platform} → ${x.status}`).join('\n'));loadOverview()}
async function syncAnalytics(){const r=await api('/api/analytics/sync',{method:'POST'});alert('Synced posts: '+r.data.synced)}

/* ---------- calendar ---------- */
async function loadCalendar(){
  const v=$('#v-calendar');v.innerHTML='<h2>Publishing Calendar</h2><div class="muted">loading…</div>';
  const r=await api('/api/schedule');const posts=r.data;
  const groups={};posts.forEach(p=>{const d=p.scheduled_at.slice(0,10);(groups[d]=groups[d]||[]).push(p)});
  v.innerHTML=`<h2>Publishing Calendar <span class="muted">(${posts.length} scheduled)</span></h2>
  <div class="row" style="margin-bottom:10px">${['PUBLISHED','QUEUED','PENDING','RETRYING'].map(s=>`<span class="pill ${pclass(s)}">${s}</span>`).join('')}</div>
  ${Object.keys(groups).sort().map(d=>`<div class="day">${d}</div>`+groups[d].map(p=>`
    <div class="post"><div class="pf">${p.platform}</div>
      <div style="flex:1"><div>${esc(p.title)||'—'}</div><div class="muted">${p.niche} · ${p.scheduled_at.slice(11,16)} UTC ${p.external_post_id?'· '+esc(p.external_post_id.slice(0,18)):''}</div></div>
      <span class="pill ${pclass(p.publish_status)}">${p.publish_status}</span></div>`).join('')).join('')||'<div class="muted">No posts scheduled.</div>'}`;
}

/* ---------- campaigns ---------- */
let WS=[];
async function loadCampaigns(){
  const v=$('#v-campaigns');
  const [w,c]=await Promise.all([api('/api/workspaces'),api('/api/campaigns')]);
  WS=w.data;
  v.innerHTML=`<h2>Campaigns</h2>
  <div class="grid g2">
    <div class="card"><h3>🤖 New AI Campaign — 1 brief → 7 channels</h3>
      <label>Workspace</label><select id="f-ws">${WS.map(x=>`<option value="${x.id}" data-niche="${x.industry_niche}">${esc(x.name)} (${x.industry_niche})</option>`).join('')}</select>
      <label>Campaign name</label><input id="f-name" placeholder="e.g. Sunset Dining Promo">
      <label>Master brief (මේ එකම ලියන්න ඕන දේ — AI එක ඔක්කොම හදනවා)</label><textarea id="f-brief" placeholder="Promote beachfront sunset dining for couples this weekend…"></textarea>
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:10px">
        <div><label>Governance</label><select id="f-gov"><option value="supervised">Supervised (internal review)</option><option value="autonomous">Autonomous (auto-publish)</option><option value="client_portal">Client portal (external approval)</option></select></div>
        <div><label>Region</label><select id="f-region" onchange="marketVis()"><option>EU</option><option>GLOBAL</option><option>LK</option></select></div>
      </div>
      <div id="mk" style="display:none"><label>EU feeder market</label><select id="f-market"><option>DACH</option><option>UK</option><option>FR</option><option>NORDICS</option><option>BENELUX</option></select></div>
      <label>Destination URL (for UTM links)</label><input id="f-url" placeholder="https://yoursite.lk/offer">
      <label>Channels (auto-selected for niche)</label>
      <div class="row" id="f-plats">${PLATFORMS.map(p=>`<label class="tag" style="cursor:pointer"><input type="checkbox" value="${p}" style="width:auto"> ${p}</label>`).join('')}</div>
      <br><button class="btn" onclick="createCampaign()">🚀 Generate Content</button>
      <div id="f-status" class="muted" style="margin-top:8px"></div>
    </div>
    <div class="card"><h3>Existing campaigns</h3><div id="camp-list"></div></div>
  </div>
  <div id="content-detail"></div>`;
  $('#f-ws').onchange=pickNiche;pickNiche();
  $('#camp-list').innerHTML=c.data.map(x=>`
    <div class="post camp" onclick="showContent('${x.content_item_ids[0]||''}')">
      <div style="flex:1"><div>${esc(x.name)}</div><div class="muted">${x.governance_mode} · ${x.content_item_ids.length} item(s)</div></div>
      <span class="pill p-b">${x.status}</span></div>`).join('')||'<div class="muted">None yet</div>';
}
function pickNiche(){const n=$('#f-ws').selectedOptions[0].dataset.niche;const ch=NICHE_CHANNELS[n]||[];
  $$('#f-plats input').forEach(i=>i.checked=ch.includes(i.value))}
function marketVis(){$('#mk').style.display=$('#f-region').value==='EU'?'block':'none'}
async function createCampaign(){
  const st=$('#f-status');st.textContent='⏳ AI pipeline running (trend hunt → strategy → create → safety)…';
  try{
    const ws=$('#f-ws').selectedOptions[0];const niche=ws.dataset.niche;
    const plats=[...$$('#f-plats input:checked')].map(i=>i.value);
    const demo={region:$('#f-region').value,destination_url:$('#f-url').value||'https://example.com/offer'};
    if($('#f-region').value==='EU')demo.market=$('#f-market').value;
    const body={workspace_id:ws.value,name:$('#f-name').value||'Untitled campaign',niche,master_prompt:$('#f-brief').value,
      target_demographic:demo,governance_mode:$('#f-gov').value,target_platforms:plats};
    const r=await api('/api/campaigns',{method:'POST',body:JSON.stringify(body)});
    const id=r.data.content_item_ids[0];
    for(let i=0;i<25;i++){await sleep(2500);
      const c=await api('/api/content/'+id);
      if(!['GENERATING','DRAFT'].includes(c.data.status)){st.textContent='✅ Done — '+c.data.status;showContent(id);return}}
    st.textContent='⏳ still generating — refresh campaigns in a moment'
  }catch(e){st.textContent='❌ '+e.message}
}
async function showContent(id){
  if(!id)return;const r=await api('/api/content/'+id);const d=r.data;const v=$('#content-detail');
  const first=Object.keys(d.outputs_json)[0]||'youtube';
  v.innerHTML=`<h2 style="margin-top:18px">Content — ${esc(d.title)}</h2>
  <div class="row" style="margin:8px 0">
    <span class="pill ${pclass(d.status)}">${d.status}</span>
    <span class="tag">niche: ${d.niche}</span><span class="tag">safety: ${d.safety_report.passed?'PASS ✅':'FLAGGED ⚠️'}</span>
    ${d.governance.approval_token?`<a class="tag on" href="${store.base}/portal/${d.governance.approval_token}" target="_blank">client portal link ↗</a>`:''}
    ${['STAGED','FLAGGED','GENERATED'].includes(d.status)?`<button class="btn" onclick="approve('${d.id}')">✅ Approve & Queue</button>`:''}
    <button class="btn ghost" onclick="publishNow()">⚡ Publish now</button>
  </div>
  ${d.safety_report.violations&&d.safety_report.violations.length?`<div class="card" style="border-color:var(--bad);margin:8px 0"><b style="color:var(--bad)">Safety violations</b><ul style="margin:6px 0 0 18px">${d.safety_report.violations.map(x=>`<li>${esc(x.detail)}</li>`).join('')}</ul></div>`:''}
  <div class="tabbtns">${Object.keys(d.outputs_json).map(p=>`<button class="${p===first?'active':''}" onclick="outTab(this,'${p}')">${p}</button>`).join('')}</div>
  <div id="out"></div>
  <h3>Scheduled posts</h3>
  ${d.scheduled_posts.map(p=>`<div class="post"><div class="pf">${p.platform}</div><div style="flex:1" class="muted">${p.scheduled_at.slice(0,16).replace('T',' ')} UTC</div><span class="pill ${pclass(p.publish_status)}">${p.publish_status}</span></div>`).join('')||'<div class="muted">none</div>'}`;
  window._outs=d.outputs_json;outTab(null,first);
}
function outTab(btn,p){if(btn){$$('#content-detail .tabbtns button').forEach(b=>b.classList.remove('active'));btn.classList.add('active')}
  $('#out').innerHTML=`<div class="out">${esc(JSON.stringify(window._outs[p],null,2))}</div>`}
async function approve(id){const r=await api('/api/content/'+id+'/approve',{method:'POST'});
  alert('Queued '+r.data.queued+' posts');showContent(id)}

/* ---------- analytics ---------- */
async function loadAnalytics(){
  const v=$('#v-analytics');v.innerHTML='<h2>Analytics</h2><div class="muted">loading…</div>';
  const r=await api('/api/analytics/dashboard');const d=r.data;const maxImp=Math.max(1,...Object.values(d.by_platform).map(x=>x.impressions));
  v.innerHTML=`<h2>Unified Analytics</h2>
  <div class="grid g5">${Object.entries(d.totals).map(([k,n])=>`<div class="card"><div class="k">${fmt(n)}</div><small>${k}</small></div>`).join('')}</div>
  <div class="grid g2" style="margin-top:14px">
    <div class="card"><h3>Impressions by platform</h3>
      ${Object.entries(d.by_platform).map(([p,x])=>`<div style="margin:8px 0"><div class="row" style="justify-content:space-between"><b>${p}</b><span class="muted">${fmt(x.impressions)} · ER ${(x.er*100).toFixed(1)}% · PPI ${x.avg_ppi}</span></div><div class="bar"><i style="width:${x.impressions/maxImp*100}%"></i></div></div>`).join('')}
      <h3>Scheduling weights (PPI feedback loop)</h3>
      <div class="row">${Object.entries(d.feedback_loop).map(([p,w])=>`<span class="tag ${w>=1?'on':''}">${p} ×${w}</span>`).join('')}</div>
    </div>
    <div class="card"><h3>Top posts (PPI)</h3>
      <table><tr><th>Platform</th><th>Title</th><th>PPI</th><th>ER</th><th>Impr.</th></tr>
      ${d.top_posts.map(t=>`<tr><td><b>${t.platform}</b></td><td>${esc(t.title)||'—'}</td><td>${t.ppi}</td><td>${(t.er*100).toFixed(1)}%</td><td>${fmt(t.impressions)}</td></tr>`).join('')}</table>
      <br><button class="btn ghost" onclick="syncAnalytics();loadAnalytics()">🔄 Sync latest metrics</button>
    </div>
  </div>`;
}

/* ---------- trends ---------- */
async function loadTrends(){
  const v=$('#v-trends');
  v.innerHTML=`<h2>Trend Intelligence</h2>
  <div class="row"><select id="t-niche" onchange="loadTrendList()">${['hospitality','travel','salon','production','ecom'].map(n=>`<option>${n}</option>`).join('')}</select>
  <select id="t-market" onchange="loadMarket()">${['DACH','UK','FR','NORDICS','BENELUX'].map(m=>`<option>${m}</option>`).join('')}</select></div>
  <div id="t-list" style="margin-top:14px"></div><div id="t-mkt" style="margin-top:14px"></div>`;
  await Promise.all([loadTrendList(),loadMarket()]);
}
async function loadTrendList(){
  const n=$('#t-niche').value;const r=await api('/api/trends?niche='+n);
  $('#t-list').innerHTML=`<h3>Trends → ${n} angles</h3>`+r.data.trends.map(t=>`
    <div class="card" style="margin:8px 0"><div class="row" style="justify-content:space-between">
      <b>${esc(t.name)}</b><span class="pill ${t.phase==='emerging'?'p-ok':t.phase==='peaking'?'p-b':'p-w'}">${t.phase}</span></div>
      <div class="muted" style="margin:4px 0">${esc(t.source)} · velocity ${t.velocity}× · saturation ${t.saturation_index}</div>
      <div>💡 ${esc(t.niche_angle)}</div></div>`).join('');
}
async function loadMarket(){
  const m=$('#t-market').value;const r=await api('/api/trends/eu-demographics?market='+m);const b=r.data.market_brief;
  $('#t-mkt').innerHTML=`<h3>EU feeder market — ${b.market_name}</h3><div class="card">
    <div class="kpi"><span>Seasonal intent</span><b>${b.seasonal_intent.replace(/_/g,' ')}</b></div>
    <div class="kpi"><span>Peak window</span><b>${b.peak_window}</b></div>
    <div class="kpi"><span>Copy style</span><b style="text-align:right">${esc(b.copy_style)}</b></div>
    <p style="margin-top:8px"><b>Tone rules:</b> ${b.tone_rules.join(' · ')}</p>
    <p><b>Priorities:</b> ${b.priorities.join(' · ')}</p>
    <p><b>Angles now:</b> ${b.recommended_angles.join(' · ')}</p>
    <p class="muted">GDPR: ${b.gdpr_note}</p></div>`;
}

/* ---------- settings ---------- */
function loadSettings(){
  $('#v-settings').innerHTML=`<h2>Settings</h2><div class="grid g2">
  <div class="card"><h3>Connection</h3>
    <label>API base URL</label><input id="s-base" value="${esc(store.base)}">
    <label>API key</label><input id="s-key" value="${esc(store.key)}">
    <br><button class="btn" onclick="store.base=$('#s-base').value.trim().replace(/\\/+$/,'');store.key=$('#s-key').value.trim();alert('Saved');loadOverview()">Save & Test</button>
    <p class="muted" style="margin-top:10px">Default: this site + demo-key. Render URL example: https://socialos-api-6d8k.onrender.com</p></div>
  <div class="card"><h3>Client portal</h3>
    <label>Portal token (from campaign)</label><input id="s-token" placeholder="paste token">
    <br><button class="btn ghost" onclick="window.open(store.base+'/portal/'+$('#s-token').value.trim(),'_blank')">Open portal ↗</button>
    <h3>Status</h3><div id="s-status" class="muted">checking…</div></div></div>`;
  api('/health').then(r=>{$('#s-status').innerHTML=`<span class="dot ok"></span>API ok — ${r.data.connectors} connectors · ${r.data.database}`})
    .catch(()=>{$('#s-status').innerHTML='<span class="dot bad"></span>API unreachable'});
}

loadOverview();
</script></body></html>"""
