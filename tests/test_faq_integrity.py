"""Schema-validate the curated FAQ dataset.

If a future contributor adds a malformed FAQ entry (missing keywords,
duplicate id, empty answer), these tests fail at CI time — long before
the issue reaches production.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_FAQ_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "faq.json"


@pytest.fixture(scope="module")
def faqs() -> list[dict]:
    """Load + parse the FAQ JSON once per module."""

    return json.loads(_FAQ_PATH.read_text(encoding="utf-8"))["faqs"]


def test_faq_file_is_non_empty(faqs: list[dict]) -> None:
    """At least 5 entries — guards against accidental file truncation."""

    assert len(faqs) >= 5


def test_every_entry_has_required_fields(faqs: list[dict]) -> None:
    """Each entry must have id, keywords, title, answer, all non-empty."""

    for entry in faqs:
        assert entry.get("id"), f"entry missing id: {entry}"
        assert isinstance(entry["keywords"], list)
        assert len(entry["keywords"]) >= 2, f"{entry['id']}: needs >=2 keywords"
        assert entry.get("title"), f"{entry['id']}: missing title"
        assert entry.get("answer"), f"{entry['id']}: missing answer"


def test_ids_are_unique(faqs: list[dict]) -> None:
    """Duplicate ids would silently shadow each other in the matcher."""

    ids = [e["id"] for e in faqs]
    assert len(ids) == len(set(ids)), "duplicate FAQ ids found"


def test_ids_are_kebab_case(faqs: list[dict]) -> None:
    """Convention: lowercase + hyphens only."""

    import re

    pat = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    for entry in faqs:
        assert pat.match(entry["id"]), f"{entry['id']!r} is not kebab-case"


def test_answers_are_substantial(faqs: list[dict]) -> None:
    """A useful answer is at least 100 chars; nudges authors to write enough."""

    for entry in faqs:
        assert len(entry["answer"]) >= 100, (
            f"{entry['id']}: answer too short ({len(entry['answer'])} chars)"
        )


def test_answers_cite_eci(faqs: list[dict]) -> None:
    """Election questions should always point to authoritative sources."""

    citing_count = sum(
        1
        for e in faqs
        if "eci.gov.in" in e["answer"].lower() or "election commission" in e["answer"].lower()
    )
    # At least half of all entries should reference the ECI to maintain
    # the project's "verify on official sources" promise.
    assert citing_count * 2 >= len(faqs), (
        f"only {citing_count}/{len(faqs)} entries cite ECI — please add citations"
    )


def test_keywords_are_lowercase(faqs: list[dict]) -> None:
    """The matcher lowercases tokens; uppercase keywords would never match."""

    for entry in faqs:
        for kw in entry["keywords"]:
            assert kw == kw.lower(), f"{entry['id']}: keyword '{kw}' is not lowercase"


def test_no_partisan_content_in_answers(faqs: list[dict]) -> None:
    """Sanity check: answers must not promote any party / candidate."""

    forbidden = (
        "vote for ",
        "best party",
        "best candidate",
        "support party",
        "favour the",
    )
    for entry in faqs:
        body = entry["answer"].lower()
        for phrase in forbidden:
            assert phrase not in body, (
                f"{entry['id']}: contains potentially partisan phrase '{phrase}'"
            )
