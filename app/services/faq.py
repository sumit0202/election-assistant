"""Curated election-FAQ retriever.

Provides a deterministic, LLM-free first line of defence for the most
commonly asked questions. Useful both as a latency / cost optimisation
*and* as a graceful fallback when the LLM service is unavailable
(quota, network, org policy, etc.).

Matching is intentionally simple — keyword overlap with light scoring.
For richer retrieval, swap in Vertex AI Embeddings + Matching Engine.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

_FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "faq.json"

# Tokens we never count as evidence — they appear in nearly every question.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "shall",
        "may",
        "might",
        "i",
        "you",
        "we",
        "they",
        "he",
        "she",
        "it",
        "this",
        "that",
        "these",
        "those",
        "my",
        "your",
        "our",
        "their",
        "his",
        "her",
        "its",
        "and",
        "or",
        "but",
        "so",
        "if",
        "then",
        "as",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "about",
        "from",
        "into",
        "what",
        "when",
        "where",
        "why",
        "how",
        "who",
        "which",
        "have",
        "has",
        "had",
        "be",
        "been",
        "being",
    }
)


@dataclass(frozen=True)
class FaqHit:
    """A matched FAQ entry with a relevance score."""

    id: str
    title: str
    answer: str
    score: float


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, drop stopwords, return token set."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {t for t in cleaned.split() if len(t) > 2 and t not in _STOPWORDS}


@lru_cache(maxsize=1)
def _load_faqs() -> list[dict]:
    try:
        with _FAQ_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        log.warning("FAQ file missing at %s", _FAQ_PATH)
        return []
    return list(data.get("faqs", []))


def best_match(query: str, *, threshold: float = 0.34) -> FaqHit | None:
    """Return the best-matching FAQ entry, or None below the threshold.

    Score is `keyword_overlap / max(query_tokens, 1)`. The default threshold
    of 0.34 means at least one in three meaningful query tokens must hit a
    keyword — high enough to avoid false positives, low enough to forgive
    light typos and synonym noise.
    """

    q_tokens = _tokenize(query)
    if not q_tokens:
        return None

    best: FaqHit | None = None
    for faq in _load_faqs():
        kw_tokens = _tokenize(" ".join(faq.get("keywords", [])))
        if not kw_tokens:
            continue
        # Boost: also include the title's tokens at half-weight via a union.
        title_tokens = _tokenize(faq.get("title", ""))
        evidence = q_tokens & (kw_tokens | title_tokens)
        if not evidence:
            continue
        score = len(evidence) / max(len(q_tokens), 1)
        if best is None or score > best.score:
            best = FaqHit(
                id=faq["id"],
                title=faq["title"],
                answer=faq["answer"],
                score=score,
            )

    if best is None or best.score < threshold:
        return None
    return best


def graceful_fallback(query: str) -> str:
    """Last-resort answer when neither FAQ nor LLM produced anything."""

    nearest = best_match(query, threshold=0.0)  # any non-empty match
    pointer = (
        f"\n\nThe closest topic I have on file is **{nearest.title}**. "
        "Try rephrasing your question around that, or use one of the "
        "quick tools on the right."
        if nearest is not None
        else ""
    )
    return (
        "I don't have a confident answer for that specific question right now."
        + pointer
        + "\n\nFor anything region-specific, please check the **Election "
        "Commission's official portal** at [eci.gov.in](https://eci.gov.in) "
        "or your state's Chief Electoral Officer website."
    )
