"""Agent unit tests with in-memory fakes for every Google service."""

from __future__ import annotations

from typing import Any

import pytest

from app.agent import AgentDeps, ElectionAgent
from app.schemas import PollingPlace, VideoItem


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
        gemini=FakeGemini('{"tool":"none","say":"Voter registration uses Form 6."}'),
        maps=FakeMaps(),  # type: ignore[arg-type]
        youtube=FakeYouTube(),  # type: ignore[arg-type]
    )
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="How do I register?", locale="en", location=None
    )
    assert "Form 6" in result.reply
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
    result = await agent.respond(
        user_message="explain EVM", locale="en", location=None
    )
    assert "How EVM works" in result.reply
    assert result.tools_used[0].name == "videos"


@pytest.mark.asyncio
async def test_agent_handles_invalid_json_gracefully():
    deps = AgentDeps(gemini=FakeGemini("Not JSON, just prose about elections."))
    agent = ElectionAgent(deps)
    result = await agent.respond(
        user_message="hi", locale="en", location=None
    )
    assert "elections" in result.reply.lower()
