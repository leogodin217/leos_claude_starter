---
name: session
description: Analyze Claude Code session transcripts — search, summarize, list, or inspect how a session went.
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 ~/.claude/skills/session/analyzer.py *)
---

# Session Analysis

Analyze Claude Code session transcripts — search for sessions, summarize them, or perform ad-hoc analysis of how a session went.

## Tool

A Python analyzer is available at `~/.claude/skills/session/analyzer.py`. Run it via Bash.

### Commands

```bash
# List recent sessions (all projects) — shows custom titles from /rename
python3 ~/.claude/skills/session/analyzer.py list --recent 20

# List ALL sessions for a project (no limit)
python3 ~/.claude/skills/session/analyzer.py list --project -home-leo-projects-fabulexa-sim --all

# List sessions for a specific project
python3 ~/.claude/skills/session/analyzer.py list --project -home-leo-projects-fabulexa-sim

# Find sessions by custom title (set via /rename in Claude Code)
python3 ~/.claude/skills/session/analyzer.py find "wtf_sprint_execution"
python3 ~/.claude/skills/session/analyzer.py find "sprint" --project -home-leo-projects-fabulexa-sim

# Search sessions by keyword in transcript content (searches main JSONL + tool-results + subagents)
# Shows context snippets around each match
python3 ~/.claude/skills/session/analyzer.py search "implement-sprint" --recent 50
python3 ~/.claude/skills/session/analyzer.py search "implement-sprint" --all      # search all sessions, not just recent
python3 ~/.claude/skills/session/analyzer.py search "implement-sprint" --verbose  # also warns on unknown JSONL types

# Get just the path of the Nth search result
python3 ~/.claude/skills/session/analyzer.py search "implement-sprint" --index 5

# Summarize a session (accepts path, UUID, or custom title)
python3 ~/.claude/skills/session/analyzer.py summary /path/to/session.jsonl
python3 ~/.claude/skills/session/analyzer.py summary "wtf_sprint_execution"

# Deep summary — aggregates parent + all subagent transcripts
python3 ~/.claude/skills/session/analyzer.py summary /path/to/session.jsonl --deep
python3 ~/.claude/skills/session/analyzer.py summary --search "keyword" --index 2 --deep

# Summarize directly from search results (preferred for search-then-inspect flows)
python3 ~/.claude/skills/session/analyzer.py summary --search "implement-sprint" --index 5

# Extract conversation flow (user prompts + assistant responses)
python3 ~/.claude/skills/session/analyzer.py conversation /path/to/session.jsonl --max-chars 800
python3 ~/.claude/skills/session/analyzer.py conversation --search "keyword" --index 2

# Tool usage timeline
python3 ~/.claude/skills/session/analyzer.py tools /path/to/session.jsonl
python3 ~/.claude/skills/session/analyzer.py tools --search "keyword" --index 2

# Compare two sessions — token usage, tool counts, duration, files touched
python3 ~/.claude/skills/session/analyzer.py diff SESSION_A SESSION_B
```

### Session names

Sessions can be named via `/rename` in Claude Code. Names are stored as `{"type": "custom-title", "customTitle": "..."}` entries in the session JSONL. Named sessions appear with `[title]` prefix in `list` and `search` output, and can be looked up directly via `find` or passed to `summary`/`conversation`/`tools`.

### Search scope

Search covers three sources per session:
- **Main JSONL** — the primary transcript
- **Externalized tool results** (`<uuid>/tool-results/*.txt`) — large tool outputs stored separately from the JSONL
- **Subagent transcripts** (`<uuid>/subagents/*.jsonl`) — Agent tool invocations

Context snippets (~80 chars) are shown around each match. Source labels (`[tool-result]`, `[subagent]`) indicate where non-main matches came from.

### Deep summary

`summary --deep` aggregates across the parent session and all its subagent transcripts:
- Combined duration, total tokens (input/output/cache), total tool calls
- Per-subagent breakdown table with duration, tool count, tokens, file size

### Diff

`diff SESSION_A SESSION_B` shows side-by-side comparison of:
- Duration, file size, token usage (input, output, cache read/create)
- Tool call counts (total and per-tool breakdown)
- Files touched (Read/Write/Edit targets) — which files are in both, only A, or only B

## Session Data Location

Sessions are stored at `~/.claude/projects/<project-slug>/<session-uuid>.jsonl`. Each session may also have:
- `<session-uuid>/subagents/*.jsonl` — subagent transcripts (one per Agent tool invocation)
- `<session-uuid>/tool-results/toolu_<id>.txt` — externalized tool results (large outputs stored separately)

## JSONL Format Reference

Each line in a session JSONL is one of these types:

| Type | What it is |
|------|-----------|
| `user` | User messages, command invocations, tool results |
| `assistant` | Claude responses (text, thinking, tool_use blocks) |
| `custom-title` | Session name set via `/rename`. Last entry wins (renames append, don't replace) |
| `progress` | Granular execution tracking (bash, agent, hook progress) |
| `queue-operation` | Background task enqueue/dequeue |
| `file-history-snapshot` | File version tracking |
| `system` | Turn duration metrics |
| `last-prompt` | Records the last user prompt for session resume |

Use `--verbose` with `search` or `summary` to detect any types not in this known set.

### Key fields per message

```
{
  "type": "user" | "assistant" | ...,
  "uuid": "...",
  "parentUuid": "...",           // conversation threading
  "sessionId": "...",
  "timestamp": "ISO-8601",
  "cwd": "/working/dir",
  "version": "2.1.x",
  "message": {
    "role": "user" | "assistant",
    "content": [...],            // text, tool_use, tool_result blocks
    "model": "claude-opus-4-6",  // assistant messages only
    "usage": {                   // assistant messages only
      "input_tokens": N,
      "output_tokens": N,
      "cache_read_input_tokens": N,
      "cache_creation_input_tokens": N
    }
  }
}
```

### Custom title (from /rename)

```json
{"type": "custom-title", "customTitle": "my_session_name", "sessionId": "uuid"}
```

A session can have multiple `custom-title` entries (each `/rename` appends a new one). The **last** entry is the current name.

### Command invocations in user messages

Slash commands appear as XML in user message content:
```
<command-name>/implement-sprint</command-name>
<command-message>implement-sprint</command-message>
```

### Tool use blocks (assistant content)

```json
{"type": "tool_use", "id": "toolu_...", "name": "Bash", "input": {"command": "..."}}
```

### Tool result blocks (user content)

```json
{"type": "tool_result", "tool_use_id": "toolu_...", "content": "..."}
```

## Ad-Hoc Analysis Guide

When asked to analyze a session beyond what the tool provides, read the JSONL directly. Common analyses:

### How well did a /command work?

1. Run `summary --deep` to get the overview including subagent aggregation
2. Run `conversation` to see the flow
3. Check: Did the command's phases execute in order?
4. Check: Were subagents launched as expected?
5. Check: Did gates (tests, pre-commit, review) pass or fail?
6. Check: How much context was consumed vs. the budget?
7. Read specific messages for deeper investigation

### Confusion and spec deviation signals

Search assistant messages for keywords that indicate an agent struggled or deviated from its instructions. Use inline Python to scan the JSONL:

**Keywords to search for:**
- Backtracking: `"actually"`, `"wait"`, `"wrong"`, `"mistake"`, `"let me reconsider"`, `"should have"`
- Spec deviation: `"spec says"`, `"not what the spec"`, `"different approach"`, `"intentional"`, `"skip"`, `"omit"`
- Rework: `"revert"`, `"undo"`, `"let me try"`, `"didn't work"`, `"failed"`
- Workarounds: `"circular"`, `"lazy import"`, `"workaround"`, `"hack"`
- Scope creep: `"refactor"`, `"restructur"`, `"redesign"`, `"not implement"`

Search both the main session and all subagent transcripts. Extract ~60 chars before and 100 chars after each match for context.

### Context efficiency audit

Analyze where context tokens were wasted. Key metrics:

1. **Duplicate reads within an agent**: Count how many times each `file_path` appears in `Read` tool_use blocks per agent. Any file read 2+ times is waste.
2. **Cross-agent file duplication**: Track which files were read by multiple agents. Expected for some files (spec, config models), but the total KB reveals whether the command should pre-extract relevant sections.
3. **Per-turn token growth**: Plot `cache_read_input_tokens` + `input_tokens` + `cache_creation_input_tokens` per assistant turn. Look for spikes (large tool results) and plateaus (agent spinning).
4. **Late notification waste**: After the main task completes, count how many turns were spent processing late-arriving subagent notifications. Each burns a full context re-read for trivial output.
5. **Tool result sizes**: Rank all `tool_result` blocks by byte size. The top 5 largest results often reveal unnecessary full-file reads or verbose command output.
6. **Spec reads**: Count how many agents read the full spec. If N agents each read a 30KB spec, that's N*30KB consumed. Extracting phase-specific sections before dispatch saves ~(N-1)*30KB.

### File provenance

Find which session created or modified a specific file:

```python
# Search for Write tool_use blocks with matching file_path
python3 -c "
import json
path = '/path/to/session.jsonl'
target = 'path/to/file.py'
with open(path) as f:
    for line in f:
        if target in line and 'tool_use' in line:
            msg = json.loads(line)
            # check for Write/Edit tool calls
"
```

Or use `search` to find sessions mentioning the filename, then inspect the matching session's tool timeline.

### Subagent identification

Subagent filenames (`agent-a589d2e5...`) don't describe their purpose. To map them:

1. In the main session, find `Task` tool_use blocks — the `description` field names the subagent (e.g., "Implement Phase 1: Config + Types")
2. The `id` returned in the tool_result matches the subagent filename suffix
3. Cross-reference with `TaskOutput` blocks to see what each subagent returned

```bash
# List all subagents with their sizes and durations
for f in /path/to/session-uuid/subagents/*.jsonl; do
    python3 ~/.claude/skills/session/analyzer.py summary "$f" 2>&1 | grep -E "(Path|Size|Duration)"
done
```

### Session efficiency

1. Compare `cache_read_input_tokens` vs `cache_creation_input_tokens` — high cache reads = good reuse
2. Check tool result sizes — large results waste context
3. Count how many times the same file was read (violation of "never read twice" rules)
4. Look at the progress message count — very high counts may indicate spinning

## What the analyzer does NOT do

The tool handles listing, searching (with context snippets), summarizing (with --deep aggregation), conversation extraction, tool timelines, and session comparison (diff). For these analyses, read the JSONL directly:

- **Per-turn token breakdown** — the tool shows totals, not per-turn growth curves
- **Cross-agent duplication** — use `diff` for two sessions, but not for duplication *within* a session's subagents
- **Confusion/deviation signals** — requires keyword search through assistant message text (see recipe above)
- **File provenance** — requires searching tool_use blocks for Write/Edit calls with specific file paths
