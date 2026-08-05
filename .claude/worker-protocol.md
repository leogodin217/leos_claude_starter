# Worker Protocol

Rules for the duration of your task. This is the subagent counterpart to the
main session's system prompt — a subagent inherits neither that prompt nor
`CLAUDE.md`, so everything a spawned agent must know is here.

<!-- STARTER BASE. An adopting repo copies this file and appends its own
     repo-specific sections — at minimum a config-boundary section stating the
     repo's no-invented-values principle with reject/accept examples, which the
     shared reviewer and implementer agents name as their primary focus.
     See ADOPTION.md § worker-protocol.md. -->

## Reporting (MANDATORY)

- Report outcomes faithfully. If tests fail, say so and include the output. If
  you skipped a step, say so. Say "done" only when you verified it.
- Don't write scaffolding for functionality that doesn't exist yet — no stub
  methods, no loops that iterate and do nothing, no `# Future:` placeholders.
- Match the surrounding code's style, naming, and comment density.
- Never edit a file outside the working directory you were given.

## File Reading

- Never re-read a file you have already read in this session.
- Use offset/limit for any file over 500 lines. Grep or LSP to find the relevant
  section first.
- Grep before Read: before reading a large file, use Grep to locate the specific
  section you need.
- Run `tools/mdnav FILE.md` before reading unfamiliar markdown, then Read only
  the section by line range.

## Code Navigation — cclsp first for any named symbol

For any question about a symbol the language defines (function, class, method,
variable), call `mcp__cclsp__*` first — never grep or read whole files for it.
It's exact (no false hits from comments, strings, tests) and cheaper than
reading. Backend is basedpyright; every tool below works.

Don't know which file the symbol is in? `find_workspace_symbols` (name only) is
the entry point — not grep.

| You want… | Call |
|---|---|
| where a symbol is defined | `find_definition` |
| every use / who references it | `find_references` |
| who calls a function | `get_incoming_calls` |
| what a function calls (trace a chain outward) | `get_outgoing_calls` |
| locate a symbol when you don't know its file | `find_workspace_symbols` |
| implementations of a protocol / ABC | `find_implementation` |
| type / signature / docstring | `get_hover` |
| errors / warnings in a file | `get_diagnostics` |

Call-hierarchy, hover, and implementation take a `line:character` — get it from
`find_definition` or `find_workspace_symbols` output first. Grep/Read are for
non-symbol text only (concepts, strings, YAML, regex). A timeout just after the
server (re)starts means the index is warming — retry once; it is not broken.

The shell is not an exemption: `grep`/`rg` run through Bash counts as grep. A
PreToolUse hook (`tools/hooks/grep_guard.py`) hard-blocks symbol-shaped grep/rg
over `.py` files — bare identifiers (or `|`-alternations of them) and `def`/`class`
searches — and points you back here. Genuine text search (a regex metacharacter,
a quoted multi-word string, or a non-`.py` target) passes untouched.

**Stale paths across worktrees.** cclsp indexes from the directory the session
launched in. A session launched inside a worktree indexes that worktree and its
results are correct. But if a result points at a path **outside your working
directory** — the main checkout while you are working in `../worktrees/<sprint>`
— that path is wrong; re-resolve it against your working directory before you
Read or Edit.

## Response Style

- No narration ("Let me read...", "Now I'll..."). Just call tools directly.
- No echoing file contents back — whoever spawned you can read them.
- Answer with outcomes, not process.
