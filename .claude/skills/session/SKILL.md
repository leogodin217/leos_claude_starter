---
name: session
description: Analyze Claude Code session transcripts — list running or past sessions, find one by title/PR/keyword, summarize it, audit its subagents and context use, or find which session wrote a file.
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 ~/.claude/skills/session/analyzer.py *)
---

# Session Analysis

All analysis goes through `python3 ~/.claude/skills/session/analyzer.py <command>` (`-h` on any command for options). Reach for inline Python over the JSONL only when no command answers the question.

## Naming a session

Any `SESSION` argument accepts:

| Form | Example |
|---|---|
| `self` | the session you are running in (`$CLAUDE_CODE_SESSION_ID`) |
| UUID or unique prefix | `d8ba5f0a` (the ID column of `list`/`live`) |
| `pr:N` / `pr:owner/repo#N` | the session that opened or linked that PR |
| title | `/rename` name or auto title, exact match first, then substring |
| path | any `.jsonl`, including a subagent transcript |
| `--search KW --index N` | row N of `search KW` |

`--project` takes a slug, a repo path, or `.` for the current directory.

## Which command

| Question | Command |
|---|---|
| What sessions are running right now? | `live` |
| What ran recently (here)? | `list [--project .] [--recent N \| --all]` |
| Where's the session called X? | `find X` |
| Which sessions mention X? | `search X` (main transcript, tool results, subagents) |
| What happened in it? | `summary SESSION` (`--deep` adds subagent totals + table) |
| What did each subagent do? | `agents SESSION` |
| How did the conversation go? | `conversation SESSION [--max-chars N]` |
| What tools ran, in order? | `tools SESSION` |
| Where did agents struggle or deviate? | `signals SESSION [--category C] [--words a,b] [--limit N]` |
| Where did context go? | `efficiency SESSION` |
| Who wrote/edited this file? | `provenance PATH [--project P]` |
| How do two runs compare? | `diff A B` |

## Reading the output

- **Tokens** are counted once per API response. Transcripts split a response into one entry per content block, each repeating its usage.
- **Cost** comes from the transcript's last `cost-state` and covers the whole session including subagents. Sessions that predate it show none.
- **Active time** sums each human prompt to the last user/assistant entry of its turn. Wall-clock includes idle time between turns.
- **Human prompts** use `origin.kind == "human"`, so task notifications, skill bodies and local-command output are excluded. Older transcripts fall back to filtering by content.
- **Labels** prefer the `/rename` title, then the auto title, then the first non-config slash command, then the first prompt. `list` hides stub sessions that have none of these.
- **`signals`** matches whole words in assistant text and thinking. Categories: backtracking, spec-deviation, rework, workaround, scope-creep. A hit is a lead to read, not a verdict.
- **`efficiency`** includes the following. Read each section against the session's job.
  - Per-transcript table: calls, peak context, total context re-read, cache-hit rate.
  - Main context-growth curve, with the largest jumps and the tool results behind them.
  - Repeated reads. "same range" is waste; distinct ranges are usually paging.
  - Files read by several transcripts, which are candidates to pre-extract before dispatch.
  - Largest results.
  - Notification-driven turns. These are normal while orchestrating and waste after the work is done.
- **`provenance`** lists Write/Edit/NotebookEdit calls, plus `Bash?` rows: commands that name the file and look like writes (`sed -i`, redirects, `open(..., 'w')`, `mv`). Bash-first agents edit mostly through Bash, so expect those rows, and expect some false positives.

## Evaluating how a /command run went

1. `summary SESSION --deep`: cost, time, token totals, the subagent table, and the latest recap.
2. `conversation SESSION`: did the phases run in order, and where did the user intervene?
3. `agents SESSION`: were the expected subagents launched, and did any run long or blow up context?
4. `signals SESSION`: then read the surrounding transcript for the hits that matter.
5. `efficiency SESSION`: repeated reads, shared spec reads, oversized results.
6. Check gates (tests, pre-commit, review) with `search` on their names, or with `tools` on the relevant subagent transcript.

## Data on disk

| Path | Contents |
|---|---|
| `~/.claude/projects/<slug>/<uuid>.jsonl` | main transcript (slug = cwd with non-alphanumerics → `-`) |
| `<uuid>/subagents/agent-<id>.jsonl` + `.meta.json` | subagent transcript; meta has `agentType`, `description`, `toolUseId` |
| `<uuid>/tool-results/*.txt` | large tool outputs; the transcript holds a short stub |
| `~/.claude/sessions/<pid>.json` | live registry: sessionId, cwd, name, status. Files for dead pids remain, and `live` filters them out |

Entry types useful for ad-hoc work are `user`/`assistant` (`message.content` blocks: text, thinking, tool_use, tool_result) and `system` (subtypes `away_summary` = recap, `turn_duration`). Also `ai-title`/`custom-title`/`agent-name`, `pr-link`, and `cost-state`. `attachment` entries are the system-reminders and context injected into each turn. `summary --verbose` lists the entry types in a transcript and flags any the analyzer doesn't know.
