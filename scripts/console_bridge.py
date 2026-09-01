#!/usr/bin/env python3
"""
Tauri bridge for shared console routing.

Routes one command through formslab.console.console_router.ConsoleRouter and prints
exactly one JSON object to stdout:
{
  "ok": true/false,
  "handled": true/false,
  "tab": "ctrl",
  "tab_changed": false,
  "should_exit": false,
  "echo_input": false,
  "clear": false,
  "suppress_prompt": false,
  "text": "...",
  "error": "..."
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
import sys

from rich.console import Console
from rich.text import Text


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _prepare_runtime() -> None:
    """Nothing to prepare any more.

    This used to insert the checkout on sys.path, call `setenv.setup_environment()`
    and chdir into it. `formslab` is an installed package now, and it resolves its
    own config and output directories, so the bridge inherits the environment its
    caller chose instead of rewriting it.
    """


def _render_plain(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, Text):
        return content.plain

    console = Console(record=True, force_terminal=False, color_system=None, width=120)
    console.begin_capture()
    console.print(content)
    text = console.end_capture()
    return _ANSI_ESCAPE.sub("", text).strip()


def _parse_payload(raw: str | None) -> dict | None:
    """Parse the optional structured input channel. Tolerant of None / blank /
    invalid JSON (returns None) so a malformed payload never crashes the bridge."""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--tab", default="ctrl")
    parser.add_argument("--payload", default=None)
    args = parser.parse_args()

    _prepare_runtime()

    try:
        from formslab.console.console_router import ConsoleRouter

        router = ConsoleRouter(initial_tab=args.tab)
        routed = router.route(args.command, _parse_payload(args.payload))

        payload = {
            "ok": True,
            "handled": bool(routed.result is not None or routed.should_exit or routed.tab_changed),
            "tab": router.current_tab,
            "tab_changed": bool(routed.tab_changed),
            "should_exit": bool(routed.should_exit),
            "echo_input": bool(routed.echo_input),
            "clear": False,
            "suppress_prompt": False,
            "text": "",
            "data": None,
        }

        if routed.result is not None:
            payload["clear"] = bool(routed.result.clear)
            payload["suppress_prompt"] = bool(routed.result.suppress_prompt)
            payload["text"] = _render_plain(routed.result.content)
            payload["data"] = routed.result.data

        print(json.dumps(payload, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
