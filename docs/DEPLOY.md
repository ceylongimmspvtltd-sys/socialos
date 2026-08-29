# 🚀 Free Hosting Setup — GitHub + Render (ලේසිම පාර)

මේ guide එකෙන් තියෙන්නේ **SocialOS platform එක free domain එකක් එක්ක live internet එකට දාන විදිහ**.
මුලු වැඩේම විනාඩි 10–15යි. Credit card ඕන නෑ. 💳❌

**ලැබෙන URL එක:** `https://socialos-api.onrender.com` (free subdomain — ඕන නම් පස්සේ custom domain add කරන්න පුළුවන්)

---

## පළමුව ඕන දේවල් (Prerequisites)

| එක | මොකක්ද | හදන්නේ කොහෙද |
|---|---|---|
| ✅ GitHub account එකක් | Code එක තියන තැන (free) | github.com/signup |
| ✅ Render account එකක් | Hosting කරන තැන (free) | render.com → **Sign up with GitHub** kiyana eka |

---

## STEP 1️⃣ — Code එක GitHub එකට දාන්න

### ක්‍රමය A: Browser එකෙන් (git CLI nemei — ලේසිම) 🖱️

1. මේ chat එකේ workspace එකෙන් **`socialos.zip`** download කරලා extract කරන්න
2. **github.com/new** යන්න → Repository name = `socialos` → **Public** → **Create repository**
3. අලුත් page එකේ **"uploading an existing file"** link එක click කරන්න
4. Extract කරපු folder එක **ඇතුලෙ තියෙන files ඔක්කොම** (app, deploy, docs, frontend folders + files) browser එකට **drag & drop** කරන්න
5. **Commit changes** button එක click කරන්න ⏳ (upload වෙනකම් බලාගෙන ඉන්න)

### ක්‍රමය B: Terminal එකෙන් (git දනවා නම්) ⌨️

```bash
# socialos folder එක ඇතුලේ:
cd socialos
git remote add origin https://github.com/YOUR_USERNAME/socialos.git
git push -u origin main
```

---

## STEP 2️⃣ — Render එකේ Deploy කරන්න

1. **render.com** → login (GitHub account එකෙන්)
2. Dashboard එකේ **New +** → **Blueprint**
3. ඔයාගේ `socialos` repo එක select කරන්න → **Apply** (blueprint permissions ok karanawa)
4. ඉවරයි! 🎉 `render.yaml` file එක නිසා හැම setting එකක්ම auto configure වෙනවා:
   - Docker build ✅ (backend/Dockerfile)
   - Free plan ✅
   - Health check `/health` ✅
   - Auto-deploy on GitHub push ✅
   - Demo seed data ✅
5. **2–4 මිනිත්තු** build වෙනවා → top එකේ URL එක copy කරන්න

---

## STEP 3️⃣ — Check කරන්න ✅

| URL | පේන්නේ |
|---|---|
| `https://socialos-api.onrender.com/` | Dashboard (stats, calendar) |
| `https://socialos-api.onrender.com/health` | `{"status":"ok",...}` |
| `https://socialos-api.onrender.com/docs` | API testing (Swagger UI) |

API test කරනවා නම් header එකක් ඕන: `X-API-Key: demo-key`

---

## ⚠️ Free Tier — දැනගෙන ඉන්න දේවල්

1. **Sleep:** 15 මිනිත්තු කවදාවත් use නැත්නම් app එක sleep වෙනවා → ඊළඟ වතාවට open කරද්දි **තත්පර 30–60ක්** යනවා (normal!)
2. **Data reset:** Free tier එකේ disk එක permanent නෑ — re-deploy වුනාම demo data නැති වෙනවා (auto-seed නිසා ආපහු එනවා). **Real business use** එකට යදිනවා නම් Render PostgreSQL add කරන්න (Settings → Add database) + `SOCIALOS_DATABASE_URL` set කරන්න
3. **Mock mode:** දැන් posts විතරයි යන්නේ (real pages වලට නෙවෙයි). Real posting වලට:
   - Render → Environment → `SOCIALOS_MOCK_CONNECTORS` = `false`
   - Platform API keys (YouTube, Meta, TikTok...) Environment variables ලෙස add කරන්න
   - `.env.example` file එකේ මොන keys ඕනද කියලා තියෙනවා

---

## ❓ Google Workspace ගැන

Google Workspace (email, docs, drive) එකෙන් **app hosting ලැබෙන්නේ නෑ** — ඒක වෙනම service එකක්.
ඒත් ඔයාගේ Google account එකෙන් **Google Cloud Run** (free tier එකක් තියෙනවා) use කරන්නත් පුළුවන් — ඒ විදිහට යන්න නම් **credit card එකක් link කරන්න ඕන** (charge වෙන්නේ නෑ, verify විතරයි). Credit card නැතුව ඕන නම් **Render path එක තමයි හොඳම** — ඒ නිසයි මම recommend කරේ.

Workspace එකේ වැදගත් වෙන තැන: custom domain එකක් තියෙනවා නම් (උදා: `app.ctech.lk`) පස්සේ ඒක Render එකට point කරන්න පුළුවන් (Settings → Custom Domains → DNS records add karanawa).

---

## 💻 Local එකේ run කරන්න ඕන නම්

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 🔁 Update කරන්න (pahatha deploy එකට)

GitHub එකට push කරාම Render **auto re-deploy** වෙනවා (autoDeploy: true). වෙනදා ම නවතන්න ඕන නෑ.
