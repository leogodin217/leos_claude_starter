#!/usr/bin/env python3
"""PreToolUse hook: redirect symbol-shaped grep/rg over Python source to cclsp.

This project is cclsp-first for code navigation (see CLAUDE.md, the system
prompt, and .claude/worker-protocol.md § Code Navigation). That guidance
was wording-only, and the shell was a side door: an agent can ignore "never
grep" by shelling `grep`/`rg` through Bash, which no hook covered. This hook
closes that door for the highest-confidence case — searching Python source for a
symbol — while leaving genuine text/regex search untouched.

Fires before Bash and Grep calls. Blocks (exit 2) when a grep/rg/egrep/fgrep/
ripgrep invocation BOTH:

  1. targets Python source — a path argument ending in .py/.pyi, or
     --include=*.py, or (rg) -g *.py / -t py; for the Grep tool, glob=*.py or
     type=py or a .py path; AND

  2. searches for a symbol shape —
       * the pattern contains the word `def` or `class` (a definition search), OR
       * the pattern is a bare identifier, or a `|`-alternation of bare
         identifiers, with no regex metacharacters.

Everything else passes (the escape hatch): regex/metacharacter patterns, quoted
multi-word strings, and any search that does not name a .py target (YAML, logs,
docs, or a bare recursive directory). A real text search naturally carries a
metacharacter or a non-.py target.

Known, deliberate gaps (kept simple per Principle #6): a recursive grep over a
bare directory that never names a .py file (`grep -rn foo packages/src/`) and a
piped `cat file.py | grep foo` both pass — the .py target is not in the grep
invocation itself.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

GREP_COMMANDS = {"grep", "egrep", "fgrep", "rg", "ripgrep"}

# Flags that consume the following token as their value (so it is not the
# pattern or a path). Union of common grep + rg spellings.
VALUE_FLAGS = {
    "-e",
    "--regexp",
    "-f",
    "--file",
    "-m",
    "--max-count",
    "-A",
    "--after-context",
    "-B",
    "--before-context",
    "-C",
    "--context",
    "-d",
    "--directories",
    "--include",
    "--exclude",
    "--exclude-dir",
    "--color",
    "--colour",
    "--group-separator",
    "-g",
    "--glob",
    "-t",
    "--type",
}

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFCLASS = re.compile(r"\b(?:def|class)\b")
PUNCT_CHARS = set("();<>|&")


def _glob_is_python(glob: str) -> bool:
    return glob.endswith((".py", ".pyi"))


def _path_is_python(path: str) -> bool:
    return path.endswith((".py", ".pyi"))


def is_symbol_pattern(pattern: str) -> bool:
    """True if the pattern is a symbol lookup cclsp should own.

    A `def`/`class` definition search, or a bare identifier (or `|`-alternation
    of bare identifiers) with no regex metacharacters. Anything carrying a
    metacharacter, space, or quote is treated as genuine text search.
    """
    if not pattern:
        return False
    if DEFCLASS.search(pattern):
        return True
    # Treat both ERE `|` and BRE `\|` as alternation separators.
    normalized = pattern.replace("\\|", "|")
    alts = [a.strip() for a in normalized.split("|")]
    alts = [a for a in alts if a]
    if not alts:
        return False
    return all(IDENT.match(a) for a in alts)


def analyze_grep_args(args: list[str]) -> tuple[str, bool] | None:
    """Extract (pattern, targets_python) from a grep/rg invocation's args.

    Returns None if no pattern can be determined.
    """
    e_patterns: list[str] = []
    includes: list[str] = []
    positional: list[str] = []
    rg_type_python = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            positional.extend(args[i + 1 :])
            break
        if a.startswith("--") and "=" in a:
            key, val = a.split("=", 1)
            if key in ("--include", "--glob"):
                includes.append(val)
            elif key == "--regexp":
                e_patterns.append(val)
            elif key == "--type" and val in ("py", "python"):
                rg_type_python = True
            i += 1
            continue
        if a in VALUE_FLAGS:
            val = args[i + 1] if i + 1 < len(args) else ""
            if a in ("--include", "-g", "--glob"):
                includes.append(val)
            elif a in ("-e", "--regexp"):
                e_patterns.append(val)
            elif a in ("-t", "--type") and val in ("py", "python"):
                rg_type_python = True
            i += 2
            continue
        if a.startswith("-e") and len(a) > 2:  # -ePATTERN
            e_patterns.append(a[2:])
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:  # boolean flag(s), e.g. -rn, -i
            i += 1
            continue
        positional.append(a)
        i += 1

    if e_patterns:
        pattern = "|".join(e_patterns)
        paths = positional
    elif positional:
        pattern = positional[0]
        paths = positional[1:]
    else:
        return None

    targets_python = (
        rg_type_python
        or any(_glob_is_python(g) for g in includes)
        or any(_path_is_python(p) for p in paths)
    )
    return pattern, targets_python


def split_segments(command: str) -> list[list[str]]:
    """Quote-aware split of a shell command into per-invocation token lists.

    Uses shlex with punctuation_chars so quotes are respected (a `\\|` inside a
    quoted grep pattern is NOT a command separator) and shell operators
    (`| || && ; & ( )`) become standalone tokens that delimit segments.
    """
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return []
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(c in PUNCT_CHARS for c in token):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def offending_pattern_in_command(command: str) -> str | None:
    """Return the first symbol-over-Python grep pattern in a shell command."""
    for tokens in split_segments(command):
        grep_idx = next(
            (i for i, t in enumerate(tokens) if Path(t).name in GREP_COMMANDS),
            None,
        )
        if grep_idx is None:
            continue
        result = analyze_grep_args(tokens[grep_idx + 1 :])
        if result is None:
            continue
        pattern, targets_python = result
        if targets_python and is_symbol_pattern(pattern):
            return pattern
    return None


def offending_pattern_in_grep_tool(tool_input: dict) -> str | None:
    """Return the pattern if a Grep-tool call is a symbol-over-Python search."""
    pattern = tool_input.get("pattern", "")
    glob = tool_input.get("glob", "") or ""
    file_type = tool_input.get("type", "") or ""
    path = tool_input.get("path", "") or ""
    targets_python = (
        file_type in ("py", "python") or _glob_is_python(glob) or _path_is_python(path)
    )
    if targets_python and is_symbol_pattern(pattern):
        return pattern
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})

    if tool_name == "Bash":
        pattern = offending_pattern_in_command(tool_input.get("command", ""))
    elif tool_name == "Grep":
        pattern = offending_pattern_in_grep_tool(tool_input)
    else:
        return 0

    if pattern is None:
        return 0

    print(
        f"Blocked: grep/rg over Python source for symbol pattern {pattern!r}. "
        f"This project is cclsp-first for code navigation — the shell is not an "
        f"exemption. Use the language server instead:\n"
        f"  - where it's defined        → mcp__cclsp__find_definition\n"
        f"  - locate by name (any file) → mcp__cclsp__find_workspace_symbols\n"
        f"  - every use / who calls it  → mcp__cclsp__find_references / "
        f"get_incoming_calls\n"
        f"cclsp is exact (no hits in comments, strings, or tests) and cheaper "
        f"than grep+read. If you genuinely need a text search, grep a non-.py "
        f"target or include a regex metacharacter.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
