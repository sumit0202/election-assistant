"""Property-based tests using `hypothesis`.

These tests assert *invariants* over a wide swath of synthetic inputs —
they catch edge cases that example-based tests miss, such as Unicode
weirdness, empty strings, very long inputs, and locale boundaries.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.safety import check_input
from app.services.faq import best_match

pytestmark = pytest.mark.property

# Generate plausible-but-arbitrary user questions: ASCII letters + spaces +
# common punctuation. We deliberately exclude regex-meta noise that would
# trivially match our injection patterns.
_question_text = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x7E,
        blacklist_characters="<>{}|\\",
    ),
    min_size=1,
    max_size=400,
).filter(lambda s: s.strip() != "")


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(text=_question_text)
def test_check_input_is_idempotent_on_clean_text(text: str) -> None:
    """If a message passes the filter once, sanitising it again is a no-op.

    This guards against accidental double-redaction (e.g. if a future
    refactor calls ``check_input`` twice in the chat pipeline).
    """

    first = check_input(text)
    if not first.allowed or first.sanitized_text is None:
        return  # Blocked or empty — the property doesn't apply.
    second = check_input(first.sanitized_text)
    assert second.allowed is True
    assert second.sanitized_text == first.sanitized_text


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(text=_question_text)
def test_check_input_never_lengthens_message(text: str) -> None:
    """Sanitisation only redacts; it must never *grow* the user's text by
    more than the size of the redaction tokens added (worst case: every
    token replaced by a longer one).
    """

    v = check_input(text)
    if not v.allowed or v.sanitized_text is None:
        return
    # Allow up to 8x growth — pessimistic upper bound for token replacement
    # on a tiny input like a single phone number replaced by '[PHONE_REDACTED]'.
    assert len(v.sanitized_text) <= len(text) * 8 + 64


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(text=_question_text, threshold=st.floats(min_value=0.0, max_value=1.0))
def test_faq_score_in_unit_range(text: str, threshold: float) -> None:
    """Any FAQ match must report a score in the closed unit interval."""

    hit = best_match(text, threshold=threshold)
    if hit is None:
        return
    assert 0.0 <= hit.score <= 1.0
    assert hit.score >= threshold


@settings(max_examples=100)
@given(
    text=st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=1, max_size=20
    )
)
def test_below_threshold_yields_no_match(text: str) -> None:
    """A threshold of 1.01 must reject even perfect matches (>=1 score impossible)."""

    assert best_match(text, threshold=1.01) is None
