"""Static-HTML accessibility assertions.

We parse ``static/index.html`` and check that the structural and ARIA
guarantees promised in ``docs/ACCESSIBILITY.md`` are actually present.
This catches regressions where someone removes a label or `aria-live`
attribute by accident.

Uses only the stdlib's ``html.parser`` so no extra test dependencies.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "index.html"


class _Collector(HTMLParser):
    """Walks the document recording every element, its attributes, and any
    inline text content (used to detect buttons with visible labels)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str]]] = []
        # Map from element index to accumulated inner text (best-effort).
        self.text_for: list[str] = []
        self._stack: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, {k: (v or "") for k, v in attrs}))
        self.text_for.append("")
        self._stack.append(len(self.elements) - 1)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, {k: (v or "") for k, v in attrs}))
        self.text_for.append("")

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        for idx in self._stack:
            self.text_for[idx] += " " + text


@pytest.fixture(scope="module")
def doc() -> _Collector:
    """Parse the SPA shell once and reuse the result across tests."""

    p = _Collector()
    p.feed(_HTML_PATH.read_text(encoding="utf-8"))
    return p


def _attrs_for(doc: _Collector, tag: str) -> list[dict[str, str]]:
    return [a for t, a in doc.elements if t == tag]


def test_html_has_lang_attribute(doc: _Collector) -> None:
    """The root <html> must declare a default language for screen readers."""

    html = _attrs_for(doc, "html")[0]
    assert html.get("lang"), "<html> needs a lang attribute"


def test_skip_link_is_present(doc: _Collector) -> None:
    """A skip-to-main-content link must be the first focusable element."""

    skip_links = [a for a in _attrs_for(doc, "a") if "skip-link" in a.get("class", "")]
    assert skip_links, "skip-link <a> not found"
    assert skip_links[0].get("href") == "#main"


def test_main_landmark_present(doc: _Collector) -> None:
    """Page must have exactly one <main> landmark, with a matching id."""

    mains = _attrs_for(doc, "main")
    assert len(mains) == 1
    assert mains[0].get("id") == "main"


def test_semantic_landmarks_present(doc: _Collector) -> None:
    """Header, nav, aside, footer landmarks must all be present."""

    tag_set = {t for t, _ in doc.elements}
    for required in ("header", "nav", "aside", "footer", "main"):
        assert required in tag_set, f"<{required}> landmark missing"


def test_chat_log_has_aria_live_region(doc: _Collector) -> None:
    """The messages list must announce updates via aria-live=polite."""

    ols = _attrs_for(doc, "ol")
    msg_lists = [a for a in ols if a.get("id") == "messages"]
    assert msg_lists, "<ol id='messages'> not found"
    assert msg_lists[0].get("aria-live") == "polite"
    assert msg_lists[0].get("role") == "log"


def test_every_form_input_has_a_label(doc: _Collector) -> None:
    """Every <input>/<textarea>/<select> with an id must have a <label for=...>."""

    label_targets = {a.get("for") for a in _attrs_for(doc, "label") if a.get("for")}
    for tag in ("input", "textarea", "select"):
        for attrs in _attrs_for(doc, tag):
            input_id = attrs.get("id")
            input_type = (attrs.get("type") or "").lower()
            if input_type in {"hidden", "submit", "button"} or not input_id:
                continue
            has_label = input_id in label_targets
            has_aria_label = bool(attrs.get("aria-label"))
            assert (
                has_label or has_aria_label
            ), f"<{tag} id='{input_id}'> has no <label for=...> or aria-label"


def test_buttons_have_accessible_names(doc: _Collector) -> None:
    """Every button must carry either an aria-label or visible text content."""

    for idx, (tag, attrs) in enumerate(doc.elements):
        if tag != "button":
            continue
        has_aria_label = bool(attrs.get("aria-label", "").strip())
        has_visible_text = bool(doc.text_for[idx].strip())
        assert (
            has_aria_label or has_visible_text
        ), f"<button id={attrs.get('id')!r}> has no aria-label or visible text"


def test_locale_options_carry_lang_attr(doc: _Collector) -> None:
    """Each locale <option> must declare its own lang for TTS pronunciation."""

    options = _attrs_for(doc, "option")
    assert len(options) >= 6, "expected at least 6 locale options"
    for o in options:
        assert o.get("lang"), f"<option value='{o.get('value')}'> missing lang attr"


def test_noscript_fallback_present(doc: _Collector) -> None:
    """A <noscript> banner must explain the JS dependency."""

    noscript = _attrs_for(doc, "noscript")
    assert noscript, "<noscript> fallback missing"


def test_manifest_link_present(doc: _Collector) -> None:
    """The PWA manifest link must reference our manifest.json."""

    manifest_links = [a for a in _attrs_for(doc, "link") if a.get("rel") == "manifest"]
    assert manifest_links
    assert manifest_links[0].get("href", "").endswith("manifest.json")


def test_color_scheme_meta_present(doc: _Collector) -> None:
    """color-scheme meta lets browsers render dark-mode UI chrome correctly."""

    metas = [a for a in _attrs_for(doc, "meta") if a.get("name") == "color-scheme"]
    assert metas
    assert "light" in metas[0].get("content", "")
    assert "dark" in metas[0].get("content", "")
