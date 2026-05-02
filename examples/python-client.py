"""Minimal async Python client for CivicGuide.

Run:
    BASE_URL=http://localhost:8080 python3 examples/python-client.py
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")


async def chat(client: httpx.AsyncClient, message: str, *, locale: str = "en") -> dict:
    """Send a single chat message and return the parsed response."""

    r = await client.post(
        f"{BASE_URL}/api/chat",
        json={
            "message": message,
            "session_id": "demo-cli-session",
            "locale": locale,
        },
        headers={"X-Request-ID": "py-client-demo"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


async def main() -> int:
    """Tiny REPL-style demo — Ctrl+D to exit."""

    print(f"CivicGuide @ {BASE_URL}")
    print("Type a question (Ctrl+D to quit):")
    async with httpx.AsyncClient() as client:
        try:
            while True:
                msg = input("> ").strip()
                if not msg:
                    continue
                resp = await chat(client, msg)
                print(resp["reply"])
                if resp.get("tools_used"):
                    print(f"   (tools: {[t['name'] for t in resp['tools_used']]})")
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
