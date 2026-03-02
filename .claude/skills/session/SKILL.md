---
name: session
description: Analyze Claude Code session transcripts — search, summarize, list, or inspect how a session went.
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 .claude/skills/session/analyzer.py *)
---

# Session Analysis

Analyze Claude Code session transcripts — search for sessions, summarize them, or perform ad-hoc analysis of how a session went.

## Tool

A Python analyzer is available at `.claude/skills/session/analyzer.py`. Run it via Bash.

### Commands

```bash
# List recent sessions (all projects) — shows custom titles from /rename
python3 .claude/skills/session/analyzer.py list --recent 20

# List sessions for a specific project
python3 .claude/skills/session/analyzer.py list --project -home-leo-projects-fabulexa-sim

# Find sessions by custom title (set via /rename in Claude Code)
python3 .claude/skills/session/analyzer.py find "wtf_sprint_execution"
python3 .claude/skills/session/analyzer.py find "sprint" --project -home-leo-projects-fabulexa-sim

# Search sessions by keyword in transcript content (shows paths for each result)
python3 .claude/skills/session/analyzer.py search "implement-sprint" --recent 50

# Get just the path of the Nth search result
python3 .claude/skills/session/analyzer.py search "implement-sprint" --index 5

# Summarize a session (accepts path, UUID, or custom title)
python3 .claude/skills/session/analyzer.py summary /path/to/session.jsonl
python3 .claude/skills/session/analyzer.py summary "wtf_sprint_execution"

# Summarize directly from search results (preferred for search-then-inspect flows)
python3 .claude/skills/session/analyzer.py summary --search "implement-sprint" --index 5

# Extract conversation flow (user prompts + assistant responses)
python3 .claude/skills/session/analyzer.py conversation /path/to/session.jsonl --max-chars 800
python3 .claude/skills/session/analyzer.py conversation --search "keyword" --index 2

# Tool usage timeline
python3 .claude/skills/session/analyzer.py tools /path/to/session.jsonl
python3 .claude/skills/session/analyzer.py tools --search "keyword" --index 2
```

### Session names

Sessions can be named via `/rename` in Claude Code. Names are stored as `{"type": "custom-title", "customTitle": "..."}` entries in the session JSONL. Named sessions appear with `[title]` prefix in `list` and `search` output, and can be looked up directly via `find` or passed to `summary`/`conversation`/`tools`.

## Session Data Location

Sessions are stored at `~/.claude/projects/<project-slug>/<session-uuid>.jsonl`. Subagent transcripts live in `<session-uuid>/subagents/`.

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

1. Run `summary` to get the overview
2. Run `conversation` to see the flow
3. Check: Did the command's phases execute in order?
4. Check: Were subagents launched as expected?
5. Check: Did gates (tests, pre-commit, review) pass or fail?
6. Check: How much context was consumed vs. the budget?
7. Read specific messages for deeper investigation

### Session efficiency

1. Compare `cache_read_input_tokens` vs `cache_creation_input_tokens` — high cache reads = good reuse
2. Check tool result sizes — large results waste context
3. Count how many times the same file was read (violation of "never read twice" rules)
4. Look at the progress message count — very high counts may indicate spinning

### Subagent analysis

Subagent transcripts are full session files. Apply the same analysis recursively:
```bash
python3 .claude/skills/session/analyzer.py summary /path/to/subagents/agent-xxx.jsonl
```
