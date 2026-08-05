#!/usr/bin/env python3
"""PreToolUse hook: deny mutating git verbs to non-committer subagents.

Background. During `/implement-sprint` an *implementer* subagent ran `git add` +
`git commit` itself (a role it never holds — the orchestrator commits after
gates pass) and, because subagents inherit the orchestrator's cwd (the main
checkout, not the worktree), the commit landed on the protected parent branch.
Two failures compounded: a role violation and a location violation. Prose rules
could not stop it — an implementer legitimately needs `Bash` (pytest, formatters,
demos), and `Bash` includes `git`, so an over-eager agent rationalizes past
"binding rule" wording. The fix has to be structural.

This hook keys on `agent_type` (the harness field also used by
`inject_worker_protocol.py`): absent ⇒ the top-level orchestrator; present ⇒ a
subagent. Only an allow-list of committers may run mutating git; every other
subagent is blocked from git-write while read-only git still passes.

  - ALLOW (no git restriction): the top-level orchestrator (`agent_type` absent)
    and any agent named under `git_committers` in `.claude/hooks-config.json` —
    per-repo configuration; the hook body stays shared and symlinked. Missing
    file or key = no subagent may mutate git.
  - DENY: any other subagent (implementer, reviewer, Explore, …) invoking a
    mutating git verb — commit, add, merge, rebase, cherry-pick, reset, push,
    stash, notes, tag, worktree, and siblings (see MUTATING_VERBS).
    `branch` is denied only with a destructive/move flag (-d/-D/-m/-M/-f).
  - PASS (read-only orientation, per the finding's settled decision — this is a
    mutating-verb *denylist*, not an all-git block): status, log, diff, show,
    rev-parse, ls-files, and any verb not on the denylist.

Fires before Bash. Blocks with exit 2 (the deny signal) and a message routing
the agent to its real job; otherwise exits 0. Fails open on unparseable
commands (rare shlex errors) — the planned worktree seam-guard is the backstop.

Register on the Bash PreToolUse matcher alongside grep_guard.py.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

CONFIG_RELPATH = ".claude/hooks-config.json"


def _project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    # No .resolve(): this file may be a symlink into the starter, and resolving
    # it would anchor the fallback in the starter's tree, not the adopting repo's.
    return Path(os.path.abspath(__file__)).parent.parent.parent


def _git_committers() -> frozenset[str]:
    """Per-repo: agents permitted to run mutating git. Top-level orchestrator is
    handled separately (it carries no agent_type)."""
    try:
        config = json.loads((_project_dir() / CONFIG_RELPATH).read_text())
    except (OSError, json.JSONDecodeError):
        return frozenset()
    return frozenset(config.get("git_committers", []))

# git subcommands that mutate the index, working tree, refs, or remote. Denied
# for non-committer subagents. `branch` is handled separately (destructive flags
# only). Unlisted verbs pass — this is a denylist, preserving read-only git.
MUTATING_VERBS = frozenset(
    {
        "commit",
        "add",
        "rm",
        "mv",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "reset",
        "restore",
        "checkout",
        "switch",
        "push",
        "pull",
        "fetch",
        "am",
        "apply",
        "stash",
        "notes",
        "tag",
        "worktree",
        "clean",
        "gc",
        "prune",
        "update-ref",
        "update-index",
        "commit-tree",
        "write-tree",
        "fast-import",
        "filter-branch",
        "reflog",
        "replace",
        "remote",
        "config",
        "init",
        "clone",
        "submodule",
    }
)

# `git branch` lists branches (read) with no args; it mutates only with these.
BRANCH_DESTRUCTIVE_FLAGS = frozenset(
    {
        "-d",
        "-D",
        "--delete",
        "-m",
        "-M",
        "--move",
        "-c",
        "-C",
        "--copy",
        "-f",
        "--force",
    }
)

# git global options that consume the FOLLOWING token as their value, so that
# token is not the subcommand. `--opt=value` forms are single tokens and need no
# special handling.
GLOBAL_VALUE_FLAGS = frozenset(
    {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--exec-path",
        "--super-prefix",
        "--config-env",
    }
)

PUNCT_CHARS = set("();<>|&")


def split_segments(command: str) -> list[list[str]]:
    """Quote-aware split of a shell command into per-invocation token lists.

    Mirrors grep_guard.split_segments: shell operators (`| || && ; & ( )`) become
    standalone tokens that delimit segments, so `git status && git commit` yields
    two segments and each git invocation is analyzed on its own.
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


def git_subcommand(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Return (subcommand, remaining_args) for a git invocation, else None.

    `tokens` is one shell segment. Returns None if the segment is not a git
    invocation. Skips git global options (consuming the value of -C/-c/etc.) to
    find the first positional token, which is the subcommand.
    """
    if not tokens or Path(tokens[0]).name != "git":
        return None

    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in GLOBAL_VALUE_FLAGS:
            i += 2  # flag + its value
            continue
        if tok.startswith("-"):
            i += 1  # boolean global flag or `--opt=value`
            continue
        return tok, tokens[i + 1 :]
    return None


def offending_git_verb(command: str) -> str | None:
    """Return the first mutating git verb in a shell command, else None."""
    for tokens in split_segments(command):
        parsed = git_subcommand(tokens)
        if parsed is None:
            continue
        verb, rest = parsed
        if verb in MUTATING_VERBS:
            return verb
        if verb == "branch" and any(f in BRANCH_DESTRUCTIVE_FLAGS for f in rest):
            return "branch"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    agent_type = payload.get("agent_type")
    # Top-level orchestrator carries no agent_type.
    if not agent_type or agent_type in _git_committers():
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    verb = offending_git_verb(command)
    if verb is None:
        return 0

    print(
        f"Blocked: agent '{agent_type}' may not run `git {verb}`. In this "
        f"project's sprint protocol, only the top-level orchestrator (and any "
        f"agent listed under git_committers in .claude/hooks-config.json) "
        f"commits or mutates git — every other agent writes files (Edit/Write) "
        f"and runs tests/formatters, nothing more. Mutating git from a "
        f"subagent risks committing to the wrong branch (subagents inherit "
        f"the orchestrator's cwd, not the worktree). Hand the commit back to "
        f"the orchestrator. Read-only git (status, log, diff, show, "
        f"rev-parse, ls-files) still passes.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
