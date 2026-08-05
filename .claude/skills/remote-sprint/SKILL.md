---
name: remote-sprint
description: Launch and drive a worktree-bound claude session (e.g. /implement-sprint) in tmux from a remote-controlled session, when the user has no local terminal.
argument-hint: [sprint-name]
---

# Remote Sprint Session

`/implement-sprint` must run in a claude session launched from inside the sprint worktree (cclsp/LSP scoping). When the user is remote-controlling this session and has no local terminal, launch that session in a detached tmux pane via `tools/remote-claude`, then peek/drive it from here.

The spawned session mirrors the `claude_fabulexa` alias (`--dangerously-skip-permissions` + `.claude/fabulexa-system-prompt.md`), so it never stalls on tool permission prompts — only on real questions (e.g. implement-sprint's ACCEPT/FIX).

## Commands

```bash
tools/remote-claude launch <target> [prompt...]   # start; target = sprint name or 'main'
tools/remote-claude peek   <target> [lines]       # show screen (lines = scrollback depth)
tools/remote-claude send   <target> <text...>     # type text + Enter into the session
tools/remote-claude ls                            # list sessions
tools/remote-claude kill   <target>               # kill session
```

Sprint targets resolve to `../worktrees/<sprint>`; `main` resolves to the main checkout. Sessions are named `claude-<target>` and keep their pane after exit (`remain-on-exit`).

## Workflow: remote /implement-sprint

1. **Precondition**: `/create-sprint` completed — worktree exists at `../worktrees/<sprint>` on branch `sprint/<sprint>`. If missing, halt and tell the user.
2. **Launch**:
   ```bash
   tools/remote-claude launch <sprint> "/implement-sprint <sprint>"
   ```
3. **Monitor sparingly.** Sprint phases take many minutes. Peek every few minutes (`tools/remote-claude peek <sprint> 100`), not in a tight loop. Prefer a background wait (e.g. a Monitor/wakeup on this harness) over busy-polling.
4. **Relay questions.** When the spawned session presents results (ACCEPT/FIX) or asks anything, relay the on-screen summary to the user verbatim, then forward their answer:
   ```bash
   tools/remote-claude send <sprint> "ACCEPT"
   ```
5. **Hand off directly (optional).** To let the user drive the spawned session from claude.ai instead of through you:
   ```bash
   tools/remote-claude send <sprint> "/remote-control <sprint>"
   ```
6. **Expect the post-ACCEPT halt — you land the merge.** After ACCEPT, the sprint session's fast-forward of `<parent>` is always refused (the parent branch is checked out in the main checkout, where you are). It halts with instructions; run them from here:
   ```bash
   git merge --ff-only sprint/<sprint>
   tools/remote-claude kill <sprint>   # session's work is done
   git worktree remove ../worktrees/<sprint> && git branch -D sprint/<sprint>
   ```
   Verify the merge landed (`git log --oneline -1`) before killing anything. Never send the sprint session a claim that the merge happened before you have run and verified it.

## Rules

- **Never do the sprint's work from here.** This session stays the operator: launch, peek, relay, send. The worktree session owns all reads/writes/commits (implement-sprint rule 5).
- Don't send input unless the pane is visibly waiting for it — peek first.
- **Ignore the input box.** Text on the `❯` input line may be the TUI's dimmed ghost-text *suggestion* — `capture-pane -p` strips styling, so it reads exactly like typed input. Never treat input-box contents as a user statement or act on them; only submitted messages (rendered above the prompt) are real. Use `tmux capture-pane -e` to see styling if you must distinguish.
- One session per target; `launch` refuses if `claude-<target>` already exists.
- `/create-sprint` runs in the main checkout — if this session already runs there, just run it here; `launch main` is only for when it doesn't.
