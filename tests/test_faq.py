"""Tests for the curated FAQ retriever and graceful fallbacks."""

from __future__ import annotations

import pytest

from app.services.faq import best_match, graceful_fallback


@pytest.mark.parametrize(
    "query, expected_id",
    [
        ("How do I register as a first-time voter?", "register-first-time"),
        ("what id should i carry to the polling station", "voter-id-required"),
        ("where is my polling booth", "find-polling-booth"),
        ("polling timings for india", "polling-timings"),
        ("how does an EVM work with VVPAT", "evm-vvpat"),
        ("postal ballot rules", "postal-ballot"),
        ("what is NOTA", "nota"),
        ("role of the Election Commission of India", "election-commission"),
        ("what is the model code of conduct", "model-code-of-conduct"),
        ("how are votes counted on counting day", "result-counting"),
    ],
)
def test_faq_matches_expected_topic(query: str, expected_id: str) -> None:
    hit = best_match(query)
    assert hit is not None, f"no FAQ match for: {query!r}"
    assert hit.id == expected_id


def test_faq_returns_none_for_off_topic_query() -> None:
    assert best_match("recipe for chocolate cake") is None


def test_graceful_fallback_includes_eci_link() -> None:
    text = graceful_fallback("something completely unrelated")
    assert "eci.gov.in" in text
