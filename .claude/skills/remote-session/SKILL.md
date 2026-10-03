---
name: remote-session
description: Spawn a named, remote-controllable claude session in any directory — detached in tmux so it survives the session that spawned it, registered with /remote-control so the user can drive it directly from claude.ai.
argument-hint: [name] [directory]
---

# Remote Session

Spawn independent claude sessions on this machine from a remote-controlled operator session. Every command routes through `~/.claude/skills/remote-session/rsession`.

Two survivability properties, both independent of the spawning session:
- **tmux detachment** — the session runs under the tmux server, a separate process tree. The operator session dying, closing, or compacting does not touch it.
- **`/remote-control` registration** — each spawned session registers under its own name and prints a claude.ai URL. The user reaches it directly from phone/laptop; no relay through the spawner needed.

They do **not** survive a reboot (tmux dies). After a reboot, a session can be manually resumed with `cd <dir> && claude --continue`, but that is a new process the user must re-register.

## Commands

```bash
~/.claude/skills/remote-session/rsession spawn <name> <dir> [prompt...]
~/.claude/skills/remote-session/rsession peek  <name> [scrollback-lines]
~/.claude/skills/remote-session/rsession send  <name> <text...>
~/.claude/skills/remote-session/rsession state <name>
~/.claude/skills/remote-session/rsession wait  <name> [timeout-secs]
~/.claude/skills/remote-session/rsession ls
~/.claude/skills/remote-session/rsession kill  <name>
```

`spawn` launches claude in `<dir>` (with `--dangerously-skip-permissions`, plus `<dir>/.claude/*-system-prompt.md` as `--system-prompt-file` if one exists — the per-repo convention), waits for the TUI, sends `/remote-control <name>`, and prints the captured claude.ai URL. If `[prompt...]` is given it is sent after registration, so the session starts working immediately.

`state` classifies the session from the bottom of its screen:

| State | Meaning |
|---|---|
| `busy` | spinner or running tool on screen |
| `background` | turn ended, but background shells/agents will wake it (footer `· 1 shell`) |
| `dialog` | a question or permission prompt is waiting for an answer |
| `idle` | turn over, nothing pending — waiting for a message |
| `exited` / `gone` | claude exited (pane dead) / no such tmux session |

`wait` blocks until the session needs someone, then prints why and exits: `idle` 0, `dialog` 2, `exited`/`gone` 3, `timeout (<state>)` 124 (default timeout 1800s). It waits through `busy` and `background`. `idle` and `dialog` must hold for `RSESSION_SETTLE` polls (default 3, ~6s at a 2s poll), so a `wait` started right after `send` or a keypress doesn't return on the stale screen.

## Workflow

1. **Spawn** with a task: `rsession spawn forge-triage ~/projects/forge "triage the open QA findings"`.
2. **Relay the URL to the user** — that link is theirs; it outlives you.
3. **Watch with `wait`** if asked: run `rsession wait <name>` as a background Bash command (`run_in_background`) — you get one notification when the session needs input, then `peek` to read what it said. Re-run after each `send`. The user may equally drive the session directly from claude.ai — don't assume you're the only input.
4. **Relay/forward** with `send` when the user answers through you.
5. **Kill** only when the user confirms the session's work is done.

## Rules

- **Only submitted messages are real.** Text on the `❯` input line may be the TUI's dimmed ghost-text suggestion — `capture-pane -p` strips styling, so it reads exactly like typed input. Never act on input-box contents; only content rendered above the prompt is a real exchange. (`capture-pane -e` shows styling if you must distinguish.)
- **Verify before you claim.** Before telling a spawned session that some external state exists (a merge landed, a file changed), check it yourself first.
- Pick unique names; `spawn` refuses an existing `claude-<name>`. Name the session after its task, not the machine.
- Spawned sessions run with permissions bypassed — they act autonomously. Don't spawn one with a destructive task the user hasn't explicitly asked for.
- For fabulexa sprint work specifically, prefer the repo's `remote-sprint` skill (`tools/remote-claude`) — it resolves worktree targets and encodes the sprint merge workflow.
