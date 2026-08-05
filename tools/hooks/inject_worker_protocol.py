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
given commands) should not receive code-navigation rules — they are noise. List
such agents in CODE_NAV_EXEMPT; they get only the sections in GENERAL_SECTIONS.
CODE_NAV_EXEMPT is per-repo configuration: each adopting repo edits it to name
its own output-reading agents.

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

# Per-repo: agents whose job is to read program OUTPUT, not source code. They
# still get the reporting and response-style rules — just not code navigation
# or the repo's code-principle sections.
CODE_NAV_EXEMPT: frozenset[str] = frozenset()

# Sections a code-nav-exempt agent still receives, by `## ` heading prefix.
GENERAL_SECTIONS = ("Reporting", "File Reading", "Response Style")


def _project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split on level-2 headings, returning (heading-text, section-including-heading)."""
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

    try:
        text = (_project_dir() / PROTOCOL_RELPATH).read_text()
    except OSError:
        return 0

    if payload.get("agent_type") in CODE_NAV_EXEMPT:
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
