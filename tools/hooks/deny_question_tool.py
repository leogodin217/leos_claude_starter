#!/usr/bin/env python3
"""PreToolUse hook: block the AskUserQuestion tool.

This project answers clarifying questions in chat as plain prose, never through
the structured multiple-choice question widget (see CLAUDE.md § Asking
Questions). The fixed options rarely cover the real answer, so the tool is
denied here and the model is redirected to ask in chat instead.

Fires before any AskUserQuestion call and blocks it (exit 2); every other tool
passes through untouched.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "AskUserQuestion":
        return 0

    print(
        "AskUserQuestion is disabled in this project. Ask in chat as plain "
        "prose instead: state what you're deciding between, lay out the options "
        "and trade-offs inline, and let the user reply freely.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
