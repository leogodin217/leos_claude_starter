#!/usr/bin/env python3
"""PreToolUse hook: enforce mdnav-first reads on large markdown files.

Fires before any Read tool call. Lets the call through unless ALL of:
  - file ends in .md
  - no offset/limit set (so it would be a full-file read)
  - file is large (>= SMALL_FILE_THRESHOLD lines)
  - file is not on the pass-through allowlist (basename or directory segment)
  - no recent mdnav invocation for this file in the transcript

Pending architecture docs (any path under a `pending/` directory) are
authored and reviewed end-to-end as work product rather than referenced by
section, so the outline-first rule does not apply to them.

When blocked, runs mdnav itself and returns the outline as the block message.
The agent then re-issues Read with offset/limit, or proceeds without re-reading.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SMALL_FILE_THRESHOLD = 200
LOOKBACK_MESSAGES = 10
PASSTHROUGH_BASENAMES = {"CLAUDE.md"}
PASSTHROUGH_DIR_SEGMENTS = {"pending"}

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MDNAV = REPO_ROOT / "tools" / "mdnav"


def recent_mdnav_basenames(transcript_path: Path, limit: int) -> set[str]:
    """Return basenames of .md files mdnav was recently invoked on."""
    if not transcript_path.is_file():
        return set()
    assistants: list[dict] = []
    with transcript_path.open() as f:
        for line in f:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "assistant":
                assistants.append(msg)
    found: set[str] = set()
    for msg in assistants[-limit:]:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use" or block.get("name") != "Bash":
                continue
            cmd = block.get("input", {}).get("command", "")
            if "mdnav" not in cmd:
                continue
            for token in cmd.split():
                if token.endswith(".md"):
                    found.add(Path(token).name)
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "Read":
        return 0

    tool_input = payload.get("tool_input", {})
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str.endswith(".md"):
        return 0

    if "offset" in tool_input or "limit" in tool_input:
        return 0

    file_path = Path(file_path_str)
    if file_path.name in PASSTHROUGH_BASENAMES:
        return 0
    if PASSTHROUGH_DIR_SEGMENTS.intersection(file_path.parts):
        return 0

    if not file_path.is_file():
        return 0

    try:
        n_lines = sum(1 for _ in file_path.open())
    except OSError:
        return 0
    if n_lines < SMALL_FILE_THRESHOLD:
        return 0

    transcript_path = Path(payload.get("transcript_path", ""))
    recent = recent_mdnav_basenames(transcript_path, LOOKBACK_MESSAGES)
    if file_path.name in recent:
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(MDNAV), str(file_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return 0
    if result.returncode != 0:
        return 0

    print(
        f"Read of {file_path} ({n_lines} lines) was intercepted: this project "
        f"requires outline-first reads on large markdown files to keep context "
        f"lean. mdnav was run for you — outline below. Re-issue Read with "
        f"offset/limit for the section you need, or proceed with what you "
        f"learned from the outline.\n\n"
        f"{result.stdout}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
