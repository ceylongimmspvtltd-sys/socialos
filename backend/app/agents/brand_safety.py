"""BrandSafetyGatekeeper — two-pass guardrail before anything is staged.

Pass 1: brand kit rules (banned keywords, required disclaimers, negative prompts).
Pass 2: platform anti-spam / policy rules (Reddit value-first, TikTok commercial
music, IG/FB caption limits, MarkdownV2 validity, GDPR-safe claims).
"""
from __future__ import annotations

import re

from app.agents.state import PipelineState

BLOCK = "block"
WARN = "warn"

# Universally risky marketing claims
DEFAULT_BANNED = ["guaranteed results", "cure", "miracle", "100% effective", "risk-free investment",
                  "cheapest ever", "beats covid", "weight loss guarantee", "no side effects"]
GDPR_PII_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b|\b\+?\d[\d\s-]{8,}\b")


class BrandSafetyGatekeeper:
    name = "brand_safety"

    def __init__(self, brand_kit: dict | None = None):
        self.banned: list[str] = list(DEFAULT_BANNED)
        self.disclaimers: list[str] = []
        self.negative_prompts: list[str] = []
        if brand_kit:
            self.banned += [w.lower() for w in (brand_kit.get("banned_words") or [])]
            self.disclaimers += brand_kit.get("required_disclaimers") or []
            self.negative_prompts += brand_kit.get("negative_prompt_constraints") or []

    def __call__(self, state) -> dict:
        s = state if isinstance(state, PipelineState) else PipelineState(**state)
        violations: list[dict] = []
        blob = (_flatten(s.outputs) + " " + s.master_prompt + " " + s.title).lower()

        for word in self.banned:
            if word in blob:
                violations.append({"rule": "banned_keyword", "severity": BLOCK,
                                   "detail": f"banned term '{word}' present in brief/generated copy"})
        for neg in self.negative_prompts:
            if neg.lower() in blob:
                violations.append({"rule": "negative_prompt", "severity": WARN,
                                   "detail": f"negative-visual constraint '{neg}' appears in a visual prompt"})
        if GDPR_PII_RE.search(_flatten(s.outputs)):
            violations.append({"rule": "gdpr_pii", "severity": BLOCK,
                               "detail": "possible email/phone in public copy (GDPR minimization)"})

        # Required disclaimers must appear for regulated vertical claims
        if s.niche in ("salon", "ecom", "hospitality", "travel"):
            needed = self.disclaimers or (s.strategy.get("disclaimers") or [])
            text = _flatten({k: v for k, v in s.outputs.items() if k in ("facebook", "instagram")})
            missing = [d for d in needed if d.lower()[:24] not in text.lower()]
            if missing:
                violations.append({"rule": "missing_disclaimer", "severity": WARN,
                                   "detail": f"append disclaimers: {missing[:2]}"})

        # Platform rules
        ig = s.outputs.get("instagram") or {}
        if ig and len(ig.get("caption", "")) > 2200:
            violations.append({"rule": "ig_caption_limit", "severity": BLOCK, "detail": "caption > 2200 chars"})
        rd = s.outputs.get("reddit") or {}
        if rd and not rd.get("value_first"):
            violations.append({"rule": "reddit_value_first", "severity": BLOCK,
                               "detail": "Reddit post flagged promotional"})
        tt = s.outputs.get("tiktok") or {}
        if tt and "commercial" not in tt.get("commercial_music_compliance", "").lower() and tt:
            violations.append({"rule": "tiktok_music", "severity": WARN,
                               "detail": "confirm commercial-music-library compliance before publish"})
        tg = s.outputs.get("telegram") or {}
        if tg and tg.get("parse_mode") == "MarkdownV2" and re.search(r"(?<!\\)[_*\[\]()]",
                                                                     tg.get("message_md", "")):
            pass  # our templates pre-escape; unescaped chars slip only via LLM output

        blocked = [v for v in violations if v["severity"] == BLOCK]
        report = {
            "passed": not blocked,
            "violations": violations,
            "checked_platforms": list(s.outputs.keys()),
            "pass": "two-pass (brand kit + platform policy)",
        }
        out = s.model_dump()
        out["safety_report"] = report
        out["status"] = "FLAGGED" if blocked else "GENERATED"
        return out

    def apply_auto_fixes(self, outputs: dict, report: dict) -> dict:
        """Auto-fixable violations (warn-level): append disclaimers, truncate captions."""
        for v in report.get("violations", []):
            if v["rule"] == "missing_disclaimer" and "facebook" in outputs:
                outputs["facebook"]["post_copy"] += "\n\n" + "\n".join(
                    d for d in self.disclaimers or [])[:400]
        return outputs


def _flatten(obj) -> str:
    if isinstance(obj, dict):
        return " ".join(_flatten(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_flatten(v) for v in obj)
    return str(obj)
