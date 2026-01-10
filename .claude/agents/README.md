# Agents and Commands

## Overview

**Agents** are workers with specific expertise, tools, and constraints.
**Commands** are processes that orchestrate work.

```
.claude/
├── agents/           # Workers
│   ├── architect.md
│   └── implementer.md
│
└── commands/         # Processes
    ├── role-architect.md
    ├── plan-sprint.md
    ├── implement-sprint.md
    ├── review-sprint.md
    └── audit-docs.md
```

---

## Agents vs Commands

| Aspect | Agents | Commands |
|--------|--------|----------|
| Purpose | Do specific work | Orchestrate workflows |
| Scope | Single focused task | Multi-step processes |
| Invocation | Task tool | Skill tool (slash commands) |
| Context | Minimal, focused | Full conversation |

---

## Agents

| Agent | Tools | Purpose |
|-------|-------|---------|
| `architect` | Read, Grep, Glob, Write, Edit | System design, contracts, ADRs |
| `implementer` | Read, Write, Edit, Bash, Glob, Grep | Code, tests, demos |

### architect

Designs systems and interfaces. Produces:
- Interface contracts (signatures + docstrings)
- Architecture documents
- Design decisions with rationale

Use when: Planning features, making design decisions, creating architecture docs.

### implementer

Writes code matching specifications exactly. Produces:
- Implementation code
- Tests
- Demo scripts (if needed)

Use when: Implementing sprint phases.

---

## Commands (Slash Commands)

| Command | Purpose |
|---------|---------|
| `/get-started` | Configure project (run once at setup) |
| `/role:architect` | Switch to architecture/design mode |
| `/plan-sprint` | Plan implementation phases |
| `/implement-sprint` | Execute sprint phases |
| `/review-sprint` | Review implementation against spec |
| `/audit-docs` | Verify docs match implementation |

---

## Adding Agents

Create a new `.md` file in `.claude/agents/` with this format:

```markdown
---
name: agent-name
description: Brief description for the Task tool
tools: Tool1, Tool2, Tool3
model: sonnet
---

You are the {Role} for {Project}.

## Your Purpose

{What this agent does}

## What You Produce

{Outputs}

## What You Do NOT Do

{Explicit constraints}
```

### Agent Design Principles

1. **Minimal context** - Load only what's needed for the task
2. **Clear constraints** - Explicit "do not" section
3. **Specific outputs** - Define exactly what the agent produces
4. **Tool restrictions** - Only grant tools the agent needs

---

## Adding Domain-Specific Agents

As your project grows, consider adding:

| Agent Type | When to Add |
|------------|-------------|
| `reviewer` | When you want fresh-eyes code review |
| `data-analyst` | When you need to validate output data |
| `doc-auditor` | When documentation accuracy matters |
| `test-reviewer` | When test quality is important |

See CUSTOMIZATION.md for guidance on creating domain-specific agents.

---

## Workflow

```
/plan-sprint
    │
    ├─→ architect agent (design contracts)
    │
    └─→ Produces: sprint spec

/implement-sprint
    │
    ├─→ For each phase:
    │       │
    │       ├─→ implementer agent (code + tests)
    │       ├─→ quality gates (linter, tests)
    │       └─→ commit
    │
    └─→ Update docs when complete
```
