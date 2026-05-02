"""Election Education Agent — Gemini-driven orchestration.

The agent decides, based on the user's message, whether to:

* answer directly with grounded election-process knowledge,
* call the Maps tool to look up nearby polling stations,
* call the YouTube tool to recommend an explainer video,
* or suggest a calendar reminder for an upcoming election milestone.

We use a *prompt-based* router rather than full function-calling so the app
works with any Gemini model variant. The router emits a small JSON block
that we parse defensively.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .schemas import ToolCall
from .services.errors import ServiceUnavailable
from .services.gemini import GeminiClient
from .services.maps import MapsClient
from .services.youtube import YouTubeClient

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are **CivicGuide**, a non-partisan, multilingual assistant that helps
citizens understand the election process. You do NOT recommend candidates
or parties. You DO explain procedures, eligibility, timelines, voter
registration, polling logistics, ID requirements, and how votes are counted.

Style:
- Clear, calm, neutral language at a 9th-grade reading level.
- Use short paragraphs and bulleted steps when describing procedures.
- Always state when information may vary by region and recommend the
  user verify on the official Election Commission website.
- If asked partisan questions, politely redirect to procedural topics.

When the user asks about something that requires live data, respond with
ONLY a JSON tool plan in this exact shape (no markdown fences):

{"tool": "<name>", "args": {...}, "say": "<short message to user>"}

Allowed tools:
- "polling_locations" — args: {"address": "<full address or city>"}
- "videos"            — args: {"topic": "<what to learn about>"}
- "none"              — when no tool is needed; "say" carries the answer.

If you are unsure, choose "none" and answer directly in "say".
"""


@dataclass
class AgentDeps:
    gemini: GeminiClient
    maps: MapsClient | None = None
    youtube: YouTubeClient | None = None


@dataclass
class AgentResult:
    reply: str
    tools_used: list[ToolCall] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)


_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_plan(raw: str) -> dict[str, Any] | None:
    """Best-effort JSON plan extraction; returns None if not parseable."""
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        plan = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(plan, dict):
        return None
    return plan


class ElectionAgent:
    """Coordinates Gemini + tools to answer election-related questions."""

    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def respond(
        self,
        *,
        user_message: str,
        locale: str,
        location: str | None,
    ) -> AgentResult:
        user_prompt = self._build_user_prompt(user_message, locale, location)

        raw = await self._deps.gemini.generate(SYSTEM_PROMPT, user_prompt)
        plan = _extract_plan(raw) or {"tool": "none", "say": raw}

        tool = (plan.get("tool") or "none").lower()
        say = (plan.get("say") or "").strip()
        args = plan.get("args") or {}

        if tool == "polling_locations" and self._deps.maps:
            return await self._handle_polling(say, args, location)

        if tool == "videos" and self._deps.youtube:
            return await self._handle_videos(say, args, locale)

        # Default / "none": return the model's answer directly.
        return AgentResult(
            reply=say or raw.strip(),
            citations=["Verify region-specific details on your official Election Commission portal."],
        )

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    async def _handle_polling(
        self, say: str, args: dict[str, Any], fallback_location: str | None
    ) -> AgentResult:
        address = (args.get("address") or fallback_location or "").strip()
        if not address:
            return AgentResult(
                reply=(
                    "Please share your city or address (e.g. 'Bandra West, Mumbai') "
                    "so I can find polling locations near you."
                )
            )
        try:
            assert self._deps.maps is not None
            formatted, places = await self._deps.maps.find_polling_places(address)
        except ServiceUnavailable as exc:
            return AgentResult(reply=f"Polling lookup is unavailable right now: {exc.detail or exc}")

        lines: list[str] = [say or f"Here are polling-style venues near **{formatted}**:", ""]
        if not places:
            lines.append("I couldn't find candidate venues. Try a more specific address.")
        for p in places[:5]:
            dist = f" ({p.distance_m / 1000:.1f} km away)" if p.distance_m else ""
            link = f" — [map]({p.map_url})" if p.map_url else ""
            lines.append(f"- **{p.name}**{dist}{link}\n  {p.address}")

        lines.append(
            "\n_Caveat: assigned polling booths are decided by the Election "
            "Commission. Confirm yours on the official voter portal._"
        )

        return AgentResult(
            reply="\n".join(lines),
            tools_used=[
                ToolCall(
                    name="polling_locations",
                    arguments={"address": address},
                    result_summary=f"{len(places)} candidates",
                )
            ],
            citations=["Google Maps Platform"],
        )

    async def _handle_videos(
        self, say: str, args: dict[str, Any], locale: str
    ) -> AgentResult:
        topic = (args.get("topic") or "voter registration process").strip()
        try:
            assert self._deps.youtube is not None
            items = await self._deps.youtube.search(topic, locale=locale, max_results=5)
        except ServiceUnavailable as exc:
            return AgentResult(reply=f"Video search is unavailable: {exc.detail or exc}")

        lines: list[str] = [say or f"Here are explainer videos on **{topic}**:", ""]
        for it in items:
            lines.append(f"- [{it.title}]({it.url}) — *{it.channel}*")
        if not items:
            lines.append("No videos found — try a different topic.")

        return AgentResult(
            reply="\n".join(lines),
            tools_used=[
                ToolCall(
                    name="videos",
                    arguments={"topic": topic},
                    result_summary=f"{len(items)} results",
                )
            ],
            citations=["YouTube Data API v3"],
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        message: str, locale: str, location: str | None
    ) -> str:
        ctx_parts = [f"User locale: {locale}"]
        if location:
            ctx_parts.append(f"User location hint: {location}")
        return f"[Context] {' | '.join(ctx_parts)}\n\n[Question] {message}"
