"""NicheStrategyAgent — applies vertical prompt chains, content pillars, tone policy,
feeder-market localization and trend angles to produce the creative strategy."""
from __future__ import annotations

from datetime import datetime, timezone

from app.agents.eu_demographics import market_brief, seasonal_intent
from app.agents.llm import get_llm, llm_or
from app.agents.niches import get_niche
from app.agents.state import PipelineState


class NicheStrategyAgent:
    name = "niche_strategy"

    async def __call__(self, state) -> dict:
        s = state if isinstance(state, PipelineState) else PipelineState(**state)
        niche = get_niche(s.niche)
        demo = s.target_demographic or {}
        market = (demo.get("market") or demo.get("feeder_market") or "").upper()
        month = datetime.now(timezone.utc).month

        # Feeder-market localization brief (travel vertical specialization)
        market_brief_data = market_brief(market, month) if (s.niche == "travel" and market) else None
        season = seasonal_intent(month)

        # Pick pillars: rotate deterministically by campaign hash so batches vary
        seed = hash((s.campaign_id or s.master_prompt)[:64]) % len(niche.pillars)
        pillars = (niche.pillars[seed:] + niche.pillars[:seed])[:3]

        # Trend angles injected by the Trend Hunter (already niche-translated)
        trend_angles = [t.angle or t.name for t in s.trends][:2]

        strategy = {
            "niche": niche.key,
            "niche_name": niche.name,
            "objective": niche.objective,
            "prompt_chain": niche.prompt_chain,
            "pillars": pillars,
            "tone": niche.tone,
            "hooks": [h.format(topic=s.title or "this experience", market=market or "European")
                      for h in niche.hook_patterns[:3]],
            "primary_cta": niche.cta_bank[0].format(topic=s.title or "your visit", market=market or "EU"),
            "hashtags": niche.hashtag_bank,
            "disclaimers": niche.disclaimers,
            "visual_style": niche.visual_style,
            "channels_priority": niche.core_channels,
            "seasonal_intent": season["intent"],
            "seasonal_angles": season["angles"],
            "trend_angles": trend_angles,
            "market_brief": market_brief_data,
            "language": s.language,
        }

        # Optional LLM enrichment of the master angle (falls back to deterministic)
        llm = get_llm()
        fallback_angle = (
            f"{pillars[0]}: position '{s.title or s.master_prompt[:60]}' through "
            f"{'the ' + market_brief_data['market_name'] + ' lens' if market_brief_data else niche.name}"
            + (f"; ride trend: {trend_angles[0]}" if trend_angles else "")
        )
        strategy["master_angle"] = await llm_or(
            llm,
            system=niche.prompt_chain,
            user=(f"Brand brief: {s.master_prompt[:900]}\n"
                  f"Pillars: {pillars}\nTone: {niche.tone}\n"
                  f"Market brief: {market_brief_data}\n"
                  "Write ONE master creative angle sentence (max 40 words)."),
            fallback=fallback_angle,
        )

        out = s.model_dump()
        out["strategy"] = strategy
        return out
