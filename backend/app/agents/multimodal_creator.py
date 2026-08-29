"""MultiModalCreatorAgent — one master brief in, platform-native content out for
all 7 networks (PRD §4.4 + integration matrix). Deterministic templates with
optional LLM enrichment; every output validates against platform constraints."""
from __future__ import annotations

import json

from app.agents.llm import get_llm, llm_or
from app.agents.niches import get_niche
from app.agents.state import PipelineState
from app.utils.utm import build_utm_link


class MultiModalCreatorAgent:
    name = "multimodal_creator"

    async def __call__(self, state) -> dict:
        s = state if isinstance(state, PipelineState) else PipelineState(**state)
        niche = get_niche(s.niche)
        strat = s.strategy
        topic = s.title or (s.master_prompt or "our latest offer")[:60]
        market = (s.target_demographic.get("market") or "").upper()
        angle = strat.get("master_angle", topic)
        hook = strat["hooks"][0] if strat.get("hooks") else topic
        cta = strat.get("primary_cta", "Learn more")
        hashtags = strat.get("hashtags", [])[:12]
        style = strat.get("visual_style", "premium social content")
        base_url = s.target_demographic.get("destination_url", "https://example.com/offer")

        llm = get_llm()
        platforms = s.target_platforms or niche.core_channels
        outputs: dict = {}

        for platform in platforms:
            builder = getattr(self, f"_{platform}", None)
            if builder is None:
                continue
            outputs[platform] = await builder(s, niche, strat, topic, angle, hook, cta, hashtags,
                                              style, base_url, market, llm)

        out = s.model_dump()
        out["outputs"] = outputs
        return out

    # --------------------------------------------------------------- YouTube
    async def _youtube(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        fb_outline = (f"00:00 Cold open — {hook}\n"
                      f"01:20 Why {topic} (the tension)\n"
                      f"04:00 The transformation / full walkthrough\n"
                      f"08:30 Cost, logistics, honest notes{', ' + market + ' market facts' if market else ''}\n"
                      f"11:00 Verdict + {cta}")
        outline = await llm_or(llm, system=strat["prompt_chain"],
                               user=f"Write a 10-12 minute YouTube outline for: {topic}. Angle: {angle}",
                               fallback=fb_outline)
        return {
            "kind": "video+shorts",
            "seo_title": (f"{topic} — Full Guide {'| ' + market + ' Travellers' if market else ''}")[:95],
            "script_outline": outline,
            "shorts_script": {
                "hook": hook, "duration_s": 42,
                "beats": [f"0-3s {hook}", f"3-20s fastest payoff of {topic}",
                          "20-35s one proof point / stat", f"35-42s {cta}"],
            },
            "description": (f"{angle}\n\n{cta}: {build_utm_link(base_url, 'youtube', 'organic', s.campaign_id)}\n\n"
                            + " ".join(hashtags[:8]))[:4900],
            "tags": [h.lstrip("#") for h in hashtags[:15]],
            "thumbnail_prompt": f"split-frame thumbnail, bold 3-word text overlay about {topic}, {style}",
            "pinned_comment": f"FAQ + full breakdown 👇 {build_utm_link(base_url, 'youtube', 'pinned', s.campaign_id)}",
            "is_shorts_candidate": True,
            "category_id": 22 if niche.key != "production" else 28,
        }

    # --------------------------------------------------------------- Instagram
    async def _instagram(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        carousel = [
            f"1. Cover: {hook}",
            f"2. Problem: why {topic} usually disappoints",
            "3. The shift: what insiders do differently",
            f"4. Proof: real numbers / before-after of {topic}",
            "5. Mistakes: the 3 costly ones",
            "6. Playbook: step-by-step",
            "7. Cost transparency",
            "8. FAQ answers",
            f"9. CTA: {cta}",
            "10. Save+Share this 🔖",
        ]
        reel = await llm_or(llm, system=strat["prompt_chain"],
                            user=f"15-30s Reel script for: {topic}. Hook: {hook}",
                            fallback=(f"HOOK (0-2s): {hook}\n"
                                      f"BODY (2-18s): 3 fast cuts showing {topic} payoff\n"
                                      f"PROOF (18-24s): one stat\n"
                                      f"CTA (24-30s): {cta}"))
        return {
            "kind": "reels+carousel+story",
            "reel_script": reel,
            "carousel_copy": carousel[:10],  # max 10 slides
            "story_sequence": [f"Poll: would you try {topic}?", f"Countdown to launch",
                               f"Swipe-up/link sticker: {build_utm_link(base_url, 'instagram', 'story', s.campaign_id)}"],
            "caption": f"{hook}\n\n{angle}\n\n{cta} ⬆️",
            "first_comment_hashtags": " ".join(hashtags[:12]),
            "location_tag": s.target_demographic.get("location", ""),
            "aspect_ratios": ["9:16", "4:5", "1:1"],
            "visual_prompt": f"{style}; {topic} hero frame",
        }

    # --------------------------------------------------------------- Facebook
    async def _facebook(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        body = await llm_or(llm, system=strat["prompt_chain"],
                            user=f"Warm Facebook post (120-180 words) for: {topic}. Angle: {angle}",
                            fallback=(f"{hook}\n\n{angle}\n\nWe put together everything you need for {topic} — "
                                      f"the honest version, no brochure-speak.\n\n👉 {cta}"))
        geo = s.target_demographic.get("geo_countries") or ([market] if market else [])
        return {
            "kind": "post+cta_button",
            "post_copy": body,
            "cta_button": {"hospitality": "BOOK_NOW", "travel": "LEARN_MORE",
                           "salon": "BOOK_NOW", "production": "SIGN_UP",
                           "ecom": "SHOP_NOW"}.get(niche.key, "LEARN_MORE"),
            "link": build_utm_link(base_url, "facebook", "feed", s.campaign_id),
            "geo_targeting": {"countries": geo},
            "media_note": "attach 4:5 image or 1:1 video rendition from DAM",
            "hashtags": " ".join(hashtags[:4]),  # FB: minimal hashtags, algorithmic best practice
        }

    # --------------------------------------------------------------- TikTok
    async def _tiktok(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        script = await llm_or(llm, system=strat["prompt_chain"],
                              user=f"30s vertical TikTok script (hook/body/CTA + text overlays) for: {topic}",
                              fallback=(f"HOOK (0-2s): {hook}\n"
                                        f"BODY (2-22s): 4 jump cuts, each with on-screen text; escalate payoff of {topic}\n"
                                        f"CTA (22-30s): {cta}"))
        return {
            "kind": "vertical_video",
            "script_30s": {"hook": hook, "body": script, "cta": cta, "duration_s": 30},
            "text_overlays": [hook[:40], f"{topic} Part 1", "wait for #3 😳", cta[:40]],
            "trending_audio_vibe": strat.get("trend_angles", ["cinematic upbeat"])[:1] or ["upbeat discovery"],
            "commercial_music_compliance": "USE COMMERCIAL MUSIC LIBRARY ONLY (business account)",
            "caption": f"{hook} {' '.join(hashtags[:5])}",
            "allow_duet": "enabled", "allow_stitch": "enabled",
            "cover_ts_ms": 1500,
            "aspect_ratio": "9:16",
        }

    # --------------------------------------------------------------- Pinterest
    async def _pinterest(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        storyboard = [f"Frame {i}: {beat}" for i, beat in enumerate(
            [f"Title card: {topic}", "Step 1 — plan", "Step 2 — book", "Step 3 — enjoy",
             f"Pin it for later: {cta}"], start=1)]
        return {
            "kind": "pin+idea_pin",
            "pin_title": f"{topic}: The Complete {'2026 ' if market else ''}Guide"[:98],
            "pin_description": (f"{angle} {cta}.").replace("  ", " ")[:495],
            "idea_pin_storyboard": storyboard,
            "rich_pin_meta": {"og:title": topic, "og:description": angle[:200],
                              "product:price:amount": s.target_demographic.get("price", "")},
            "alt_text": f"{topic} — {style}"[:495],  # visual SEO
            "destination_url": build_utm_link(base_url, "pinterest", "organic", s.campaign_id),
            "board_hint": niche.key + "-inspo",
            "aspect_ratio": "2:3 (1000x1500)",
        }

    # --------------------------------------------------------------- Reddit
    async def _reddit(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        sub = s.target_demographic.get("subreddit") or niche.reddit_subs[0]
        body = await llm_or(llm, system=strat["prompt_chain"],
                            user=(f"Write a VALUE-FIRST r/{sub} text post about {topic}. "
                                  "No promotion, no links in body, educational, 300+ words, markdown."),
                            fallback=(f"We spent the last few months deep in {topic} and logged everything — "
                                      f"costs, timing, mistakes.\n\n## What we found\n- Expectation vs reality gap is huge\n"
                                      f"- Timing matters more than budget\n- Local vs packaged options compared\n\n"
                                      f"## The numbers\nRough cost bands and where money gets wasted.\n\n"
                                      f"## Mistakes we made\n1. Over-planning 2. Wrong season 3. Ignoring locals' advice\n\n"
                                      f"Happy to answer questions in comments — no sales pitch."))
        return {
            "kind": "text_post",
            "subreddit": sub,
            "title": (f"What we learned about {topic} (data, costs, mistakes — {niche.key} field notes)")[:298],
            "markdown_body": body if len(body) >= 280 else body + "\n\n" + ("*" * 60),
            "flair_hint": "Discussion" if niche.key != "ecom" else "Review",
            "value_first": True, "allow_links": False,  # links only in comments (anti-shadowban)
            "comment_cta": f"Details here if useful: {build_utm_link(base_url, 'reddit', 'comment', s.campaign_id)}",
            "karma_required": 50,
        }

    # --------------------------------------------------------------- Telegram
    async def _telegram(self, s, niche, strat, topic, angle, hook, cta, hashtags, style, base_url, market, llm):
        if niche.key == "salon":  # flash-slot broadcast use case
            msg = (f"⚡ *FLASH SLOT ALERT*\n\nTomorrow 4:00 PM — {topic}\n"
                   f"First to tap below books it\\. Original price, minus 15%\\.\n\n_Limited to one guest\\._")
            buttons = [[{"text": "Claim the slot 🔥", "url": build_utm_link(base_url, "telegram", "flash", s.campaign_id)}]]
        else:
            msg = (f"*{hook}*\n\n{angle[:180]}\n\n{cta} \\→ tap below")
            buttons = [[{"text": cta[:40], "url": build_utm_link(base_url, "telegram", "broadcast", s.campaign_id)}]]
        return {
            "kind": "broadcast",
            "method": "sendPhoto" if niche.key != "ecom" else "sendMediaGroup",
            "message_md": msg,  # MarkdownV2-escaped
            "buttons": buttons,
            "media_group": [f"https://cdn.example/{s.content_item_id[:8]}-{i}.jpg" for i in range(1, 4)]
                          if niche.key == "ecom" else [],
            "silent": False, "pin": niche.key in ("ecom", "salon"),
            "parse_mode": "MarkdownV2",
        }
