"""Agent unit tests with in-memory fakes for every Google service."""

from __future__ import annotations

from typing import Any

import pytest

from app.agent import AgentDeps, ElectionAgent, _extract_plan
from app.schemas import PollingPlace, VideoItem
from app.services.errors import ServiceUnavailable

pytestmark = pytest.mark.unit


class FakeGemini:
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str, **_: Any) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self._response


class FakeMaps:
    async def find_polling_places(self, address: str, radius_m: int = 5000):
        return (
            f"{address}, India",
            [
                PollingPlace(
                    name="Govt High School",
                    address="Main Rd",
                    distance_m=420.0,
                    place_id="abc",
                    map_url="https://maps.example/abc",
                )
            ],
        )


class FakeYouTube:
    async def search(self, topic: str, *, locale: str = "en", max_results: int = 5):
        return [VideoItem(title=f"How {topic} works", channel="ECI", url="https://yt/x")]


@pytest.mark.asyncio
async def test_agent_returns_direct_answer():
    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"none","say":"Indian Parliament has two houses."}'),
        maps=FakeMaps(),  # type: ignore[arg-type]
        youtube=FakeYouTube(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    # Use a query that won't match any FAQ entry, forcing LLM routing.
    result = await agent.respond(
        user_message="describe the structure of indian parliament briefly",
        locale="en",
        location=None,
    )
    assert "Parliament" in result.reply
    assert result.tools_used == []


@pytest.mark.asyncio
async def test_agent_invokes_polling_tool():
    deps = AgentDeps(
        gemini=FakeGemini(
            '{"tool":"polling_locations","args":{"address":"MG Road, Bengaluru"},"say":"Looking up..."}'
        ),
        maps=FakeMaps(),  # type: ignore[arg-type]
        youtube=FakeYouTube(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="Find polling near MG Road", locale="en", location=None
    )
    assert "Govt High School" in result.reply
    assert result.tools_used and result.tools_used[0].name == "polling_locations"


@pytest.mark.asyncio
async def test_agent_invokes_video_tool():
    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"videos","args":{"topic":"EVM"},"say":"Here are some videos:"}'),
        maps=FakeMaps(),  # type: ignore[arg-type]
        youtube=FakeYouTube(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    # The phrase "show me explainer videos" trips the tool-intent heuristic
    # so the agent skips the FAQ and lets the LLM route to the video tool.
    result = await agent.respond(
        user_message="show me explainer videos on EVM",
        locale="en",
        location=None,
    )
    assert "How EVM works" in result.reply
    assert result.tools_used[0].name == "videos"


@pytest.mark.asyncio
async def test_agent_handles_invalid_json_gracefully():
    deps = AgentDeps(gemini=FakeGemini("Not JSON, just prose about something obscure."))
    agent = ElectionAgent(deps)
    # Use a query that won't match any FAQ so we exercise the LLM path.
    result = await agent.respond(
        user_message="tell me about something obscure", locale="en", location=None
    )
    assert "obscure" in result.reply.lower()


@pytest.mark.asyncio
async def test_faq_short_circuits_known_question():
    """The agent should answer common questions from the FAQ without
    calling the LLM at all — saving cost and working even if Gemini is down."""

    class ExplodingGemini:
        async def generate(self, *_args, **_kwargs):
            raise AssertionError("Gemini should not be called for FAQ questions")

    deps = AgentDeps(gemini=ExplodingGemini())  # type: ignore[arg-type]
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="How do I register as a first-time voter?",
        locale="en",
        location=None,
    )
    assert result.tools_used and result.tools_used[0].name == "faq"
    assert "Form 6" in result.reply or "voters.eci.gov.in" in result.reply


@pytest.mark.asyncio
async def test_agent_falls_back_when_llm_unavailable():
    """If Gemini raises ServiceUnavailable on a non-FAQ question, the agent
    should still produce a useful answer (best-effort FAQ + graceful note)."""

    class FailingGemini:
        async def generate(self, *_args, **_kwargs):
            raise ServiceUnavailable("Gemini", "quota exceeded")

    deps = AgentDeps(gemini=FailingGemini())  # type: ignore[arg-type]
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="explain the entire history of indian democracy",
        locale="en",
        location=None,
    )
    # Either FAQ best-effort or graceful_fallback; both must mention eci.gov.in
    assert "eci.gov.in" in result.reply.lower() or "election commission" in result.reply.lower()


@pytest.mark.asyncio
async def test_polling_request_without_address_asks_user() -> None:
    """If the model emits polling tool with no address and no location hint,
    the agent should prompt the user for one rather than calling Maps with
    an empty string."""

    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"polling_locations","args":{},"say":""}'),
        maps=FakeMaps(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="find polling places near", locale="en", location=None
    )
    assert "share your city" in result.reply.lower()


@pytest.mark.asyncio
async def test_polling_handles_maps_outage() -> None:
    """When MapsClient raises ServiceUnavailable, the user gets a graceful note."""

    class FailingMaps:
        async def find_polling_places(self, address: str, radius_m: int = 5000):
            raise ServiceUnavailable("Maps", "key revoked")

    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"polling_locations","args":{"address":"MG Road"},"say":"..."}'),
        maps=FailingMaps(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="find polling near me", locale="en", location="MG Road"
    )
    assert "unavailable" in result.reply.lower()


@pytest.mark.asyncio
async def test_videos_handles_youtube_outage() -> None:
    """YouTube outages are surfaced gracefully without crashing the agent."""

    class FailingYT:
        async def search(self, *_a, **_kw):
            raise ServiceUnavailable("YouTube", "403 quota")

    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"videos","args":{"topic":"EVM"},"say":""}'),
        youtube=FailingYT(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="show me explainer videos on EVM", locale="en", location=None
    )
    assert "unavailable" in result.reply.lower()


@pytest.mark.asyncio
async def test_videos_empty_topic_uses_default() -> None:
    """If the model omits the topic, the agent falls back to 'voter registration process'."""

    captured: list[str] = []

    class CapturingYT:
        async def search(self, topic: str, *, locale: str = "en", max_results: int = 5):
            captured.append(topic)
            return []

    deps = AgentDeps(
        gemini=FakeGemini('{"tool":"videos","args":{},"say":""}'),
        youtube=CapturingYT(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    await agent.respond(user_message="show me explainer videos", locale="en", location=None)
    assert captured == ["voter registration process"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected_keys",
    [
        ('{"tool":"none","say":"hi"}', {"tool", "say"}),
        ('preamble {"tool":"videos"} trailing', {"tool"}),
        ("not json at all", None),
        ("[1,2,3]", None),  # array, not dict
        ("", None),
    ],
)
def test_extract_plan_handles_messy_outputs(raw: str, expected_keys: set[str] | None) -> None:
    """The plan extractor must be robust to model output drift."""

    plan = _extract_plan(raw)
    if expected_keys is None:
        assert plan is None
    else:
        assert plan is not None
        assert expected_keys.issubset(plan.keys())
