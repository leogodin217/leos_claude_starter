---
name: issue
description: "Create, list, and resolve review issues. Critical issues get individual files for research; warnings and gaps go to a quick-fix checklist."
argument-hint: "<command> [args]"
allowed-tools: "Bash(python3 ~/.claude/skills/issue/cli.py *)"
---

# Issue Tracker

Track findings, bugs, and improvements as text files. All operations go through the CLI at `~/.claude/skills/issue/cli.py`.

## Two-Tier Model

| Tier | Severity | Format | When |
|------|----------|--------|------|
| **Deep** | critical, significant, enhancement | Individual file in status dirs | Needs research, design decisions, multiple rounds |
| **Quick** | warning, gap | Checklist in quickfixes.md | Mechanical — clear problem, clear fix |

**Severity determines format.** Don't create a file for a one-line fix. Don't put a research problem on a checklist.

## Config

Location: `~/.config/issue-tracker/config.yaml`

```yaml
issues_root: ~/issues
default_project: fabulexa
projects:
  fabulexa:
    root: ~/projects/fabulexa_sim
    packages: [engine, abm, export]
  claude-skills:
    root: ~/claude_skills
```

All issues live under `issues_root/<project>/`. Project is resolved from cwd automatically. Use `--project <name>` to override.

## Directory Structure

```
~/issues/
├── config.yaml
├── fabulexa/
│   ├── open/
│   ├── in_progress/
│   ├── closed/
│   └── quickfixes.md
└── claude-skills/
    ├── open/
    ├── in_progress/
    ├── closed/
    └── quickfixes.md
```

## Command Reference

### init

```bash
python3 ~/.claude/skills/issue/cli.py init myproject --packages api,frontend

# With custom issues root
python3 ~/.claude/skills/issue/cli.py init myproject --issues-root ~/work/issues
```

Creates config entry and directory structure. Default issues root: `~/issues`.

### create

```bash
# Minimal
python3 ~/.claude/skills/issue/cli.py create critical "PyArrow NULL handling gap"

# With content
python3 ~/.claude/skills/issue/cli.py create significant "dict.get fallbacks mask contracts" \
  --package abm \
  --component export \
  --summary "dict.get() with defaults hides missing required keys" \
  --problem "Found in flush.py:45 — uses dict.get('key', []) which silently returns empty list" \
  --analysis "Root cause: defensive coding pattern. Affects all callers."
```

Output: `Created #034: <summary>`

### quickfix

```bash
python3 ~/.claude/skills/issue/cli.py quickfix "getattr on Actor alias properties" \
  --package abm \
  --items "types/actor.py:45=remove properties @property alias" \
          "types/actor.py:52=remove actor_type @property alias"
```

### update (reads from stdin)

```bash
python3 ~/.claude/skills/issue/cli.py update 034 --section analysis <<'EOF'
Root cause is the flush method treating nullable columns as non-nullable.
EOF
```

### list

```bash
python3 ~/.claude/skills/issue/cli.py list
python3 ~/.claude/skills/issue/cli.py list --status all
python3 ~/.claude/skills/issue/cli.py list --package abm --severity critical
```

Output:
```
fabulexa — 3 open, 1 in progress, 15 closed

  Open:
    034 [critical, abm] PyArrow array construction crashes on nullable columns
    037 [significant, abm] dict.get() fallbacks mask contract violations

  In Progress:
    033 [significant, abm] state: object type erasure remaining in 6 files

  Quick fixes: 2 open, 4 closed
```

### search

```bash
python3 ~/.claude/skills/issue/cli.py search "pyarrow"
```

Case-insensitive. Searches issue files and quickfixes.md. Capped at 20 results.

### show

```bash
python3 ~/.claude/skills/issue/cli.py show 034
python3 ~/.claude/skills/issue/cli.py show pyarrow
```

### start / close / reopen

```bash
python3 ~/.claude/skills/issue/cli.py start 034
python3 ~/.claude/skills/issue/cli.py close 034 --commit abc1234 \
  --decision "Use from_pandas=True" --fix "Changed flush.py"
python3 ~/.claude/skills/issue/cli.py reopen 034
```

For longer decision/fix content, use update first, then close without those flags.

### close-quickfix

```bash
python3 ~/.claude/skills/issue/cli.py close-quickfix "getattr on Actor"
```

## LLM Workflow

### Filing issues after a review

```bash
python3 ~/.claude/skills/issue/cli.py list
python3 ~/.claude/skills/issue/cli.py create critical "Title" --package pkg --problem "..." --analysis "..."
python3 ~/.claude/skills/issue/cli.py quickfix "Title" --package pkg --items "file:line=description"
```

### Working an issue

```bash
python3 ~/.claude/skills/issue/cli.py start 034
# ... do the work ...
python3 ~/.claude/skills/issue/cli.py close 034 --commit <hash>
```

### Adding research

```bash
python3 ~/.claude/skills/issue/cli.py update 034 --section options <<'EOF'
Option A: ...
Option B: ...
EOF
```

## Principles

- **Issues live outside the project repo.** No context pollution during codebase searches.
- **Status = directory.** Moving a file changes its status.
- **Deep issues accumulate context.** Each research round adds to Options/Analysis via `update`.
- **Quick fixes are bulk-processable.** Read the checklist, fix in one pass, close-quickfix.
- **Summary enables scanning.** One-line summaries in frontmatter power list/search.

## Integration with Other Skills

Review skills should file findings as issues:
1. Classify each finding by severity
2. Create via CLI commands above
3. Reference issue numbers in review summaries (`#034`)
