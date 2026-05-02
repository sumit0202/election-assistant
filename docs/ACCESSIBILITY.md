# Accessibility (WCAG 2.2 AA)

CivicGuide is designed to be usable by **every citizen**, including people
who navigate the web with a keyboard, screen reader, magnifier, or in a
high-contrast environment. This document is a checklist of the
accessibility decisions in the SPA — and what we deliberately defer.

## WCAG 2.2 AA conformance summary

| Principle | How we satisfy it |
|---|---|
| **Perceivable** | Sufficient colour contrast; honours `prefers-color-scheme`, `prefers-contrast`, `forced-colors`; semantic landmarks; `<noscript>` fallback. |
| **Operable** | Keyboard-first interaction; visible focus rings (3 px); skip-link; no keyboard traps; `prefers-reduced-motion` respected; minimum 44×44 px touch targets. |
| **Understandable** | Plain-language UI strings; `<html lang>` updates dynamically per locale; per-`<option lang>` for screen-reader pronunciation; consistent navigation. |
| **Robust** | Valid HTML5; ARIA used only where native semantics aren't enough; tested against axe DevTools and Lighthouse. |

## Specific commitments

### Keyboard

- `Tab` cycles through every interactive element in a logical order.
- `Enter` submits the chat composer.
- `Shift + Enter` inserts a newline in the textarea (announced via
  `aria-describedby` on the form).
- The skip-link is the very first focusable element on the page.
- All focusable elements receive a 3 px `outline` (`outline-offset: 3px`).

### Screen readers

- Chat region uses `<ol role="log" aria-live="polite" aria-relevant="additions text">`
  so each new message is announced without re-reading earlier messages.
- The Send button toggles its `aria-label` between `"Send message"` and
  `"Sending… please wait"` so the state change is announced.
- `<html lang>` is kept in sync with the locale picker on every change.
- Each `<option>` carries its own `lang=""` so language switches are
  pronounced correctly mid-sentence.
- All form fields have explicit `<label>` (visually hidden) plus
  `aria-label` and (where helpful) `aria-describedby`.

### Visual

- Dark + light themes via `prefers-color-scheme`; both pass WCAG AA contrast.
- `prefers-contrast: more` toggles a higher-contrast palette.
- `forced-colors: active` (Windows High Contrast) uses system colours.
- `prefers-reduced-motion: reduce` disables all transitions and the typing
  blink.
- `theme-color` meta varies by colour scheme so Android browser UI matches.

### Motor

- Buttons are at least 44×44 px on touch (WCAG 2.5.5 / 2.5.8).
- No drag-only interactions.
- Forms accept paste, autofill, and password-manager input.

### Internationalisation

- 6 starter locales: English, Hindi, Tamil, Bengali, Marathi, Telugu.
- Adding a locale: append an `<option>` to `static/index.html`'s locale
  picker. Replies are translated server-side via Cloud Translation.
- `dir="rtl"` is supported by the layout (no fixed left/right offsets).

## What we deferred

| Feature | Why deferred | Mitigation |
|---|---|---|
| Speech input | Browser API isn't available in all geographies / locales | Composer accepts pasted text |
| Live captions for video | YouTube already serves auto-captions | Linked videos open on YouTube where captions are user-controlled |
| Custom font-size slider | OS-level zoom works correctly (no `vw` lock) | Document uses relative units |

## Test plan

- **Manual**: `Tab` through every page; verify focus visible at every step.
- **Automated**: axe DevTools — 0 violations on the deployed page.
- **Lighthouse**: Accessibility score >= 95.
- **NVDA + Firefox**: each chat reply announced; tool results announced via
  `aria-live` regions.
- **VoiceOver + Safari iOS**: form fields read correct labels; `lang`
  switching works after locale change.

## Reporting an accessibility issue

We treat accessibility regressions as **bugs**. Open a GitHub issue with:

1. The browser + assistive technology you used
2. Steps to reproduce
3. What you expected vs. what happened
