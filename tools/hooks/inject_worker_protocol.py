#!/usr/bin/env python3
"""SubagentStart hook: inject the worker protocol into subagents.

Subagents inherit neither CLAUDE.md nor the main session's system prompt. A
spawned agent (especially a built-in like Explore) therefore starts blind to
the repo's rules — it defaults to grep instead of cclsp, and it has none of the
reporting discipline the main session gets. This hook injects
`.claude/worker-protocol.md` as `additionalContext` at the start of every
subagent's run, so the rules ride along regardless of how the agent was spawned
or what its spawn prompt says.

The protocol file is the single source: this hook reads it rather than restating
it. The main session's equivalent is the custom system prompt delivered by the
launch alias; the two share content but are deliberately separate documents,
because a subagent has no user to address and no session to configure.

Opt-out by design: an agent whose job is to read program OUTPUT rather than
source code (a data analyst judging emitted artifacts, an ops gate running
given commands) should not receive code-navigation rules — they are noise.
Which agents those are is per-repo configuration: the adopting repo lists them
under `code_nav_exempt` in `.claude/hooks-config.json` (the hook body stays
shared and symlinked). Missing file or key = no exemptions, everyone gets the
full protocol. Exempt agents get only the sections in GENERAL_SECTIONS.

SubagentStart is context-only (it cannot block). It prints a
hookSpecificOutput.additionalContext JSON object and exits 0; on any failure to
read the protocol it exits 0 silently rather than breaking the subagent.
Register with matcher "*".
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROTOCOL_RELPATH = ".claude/worker-protocol.md"
CONFIG_RELPATH = ".claude/hooks-config.json"

# Sections a code-nav-exempt agent still receives, by `## ` heading prefix.
GENERAL_SECTIONS = ("Reporting", "File Reading", "Response Style")


def _project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    # No .resolve(): this file may be a symlink into the starter, and resolving
    # it would anchor the fallback in the starter's tree, not the adopting repo's.
    return Path(os.path.abspath(__file__)).parent.parent.parent


def _code_nav_exempt(root: Path) -> frozenset[str]:
    """Per-repo: agents that read program OUTPUT, not source code. They still
    get the reporting and response-style rules — just not code navigation."""
    try:
        config = json.loads((root / CONFIG_RELPATH).read_text())
    except (OSError, json.JSONDecodeError):
        return frozenset()
    return frozenset(config.get("code_nav_exempt", []))


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split on level-2 headings into (heading-text, section-with-heading)."""
    parts = re.split(r"^(## .+)$", text, flags=re.MULTILINE)
    out: list[tuple[str, str]] = []
    # parts[0] is the preamble (title + intro); keep it under an empty heading.
    if parts[0].strip():
        out.append(("", parts[0]))
    for heading, body in zip(parts[1::2], parts[2::2]):
        out.append((heading[3:].strip(), heading + body))
    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    root = _project_dir()
    try:
        text = (root / PROTOCOL_RELPATH).read_text()
    except OSError:
        return 0

    if payload.get("agent_type") in _code_nav_exempt(root):
        sections = _split_sections(text)
        text = "".join(
            body
            for heading, body in sections
            if heading == "" or heading.startswith(GENERAL_SECTIONS)
        )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": text,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
