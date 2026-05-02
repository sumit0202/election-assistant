"""Thin wrappers over Google APIs.

Each module exposes a small, typed surface area so the rest of the app
remains decoupled from the underlying SDK / HTTP shape. Every client is
*lazy*: missing credentials raise a `ServiceUnavailable` only when the
feature is actually invoked, so the app still boots without every key.
"""

from .errors import ServiceUnavailable

__all__ = ["ServiceUnavailable"]
