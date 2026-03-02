# Agents and Skills

## Overview

**Agents** are workers with specific expertise, tools, and constraints.
**Skills** are processes that orchestrate work.

```
.claude/
├── agents/           # Workers
│   ├── architect.md
│   └── implementer.md
│
└── skills/           # Processes
    ├── get-started/
    ├── arch-design/
    ├── arch-review/
    ├── create-sprint/
    ├── eval-sprint/
    ├── implement-sprint/
    ├── review-sprint/
    ├── verify-sprint/
    ├── audit-docs/
    ├── review-tests/
    ├── role-architect/
    └── role-educator/
```

---

## Agents vs Skills

| Aspect | Agents | Skills |
|--------|--------|--------|
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

## Skills (Slash Commands)

| Skill | Purpose |
|-------|---------|
| `/get-started` | Configure project (run once at setup) |
| `/arch-design` | Design interfaces, create architecture docs |
| `/arch-review` | Review architecture decisions |
| `/create-sprint` | Plan implementation phases |
| `/eval-sprint` | Evaluate sprint spec before implementation |
| `/implement-sprint` | Execute sprint phases |
| `/review-sprint` | Review implementation against spec |
| `/verify-sprint` | Final verification of sprint deliverables |
| `/audit-docs` | Verify docs match implementation |
| `/review-tests` | Review test quality |
| `/role-architect` | Switch to architecture/design mode |
| `/role-educator` | Switch to educator persona |

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
/create-sprint
    │
    ├─→ architect agent (design contracts)
    │
    └─→ Produces: sprint spec

/eval-sprint
    │
    └─→ Evaluate spec completeness

/implement-sprint
    │
    ├─→ For each phase:
    │       │
    │       ├─→ implementer agent (code + tests)
    │       ├─→ quality gates (linter, tests)
    │       └─→ commit
    │
    └─→ Update docs when complete

/review-sprint
    │
    └─→ Review implementation against spec

/verify-sprint
    │
    └─→ Final verification of deliverables
```
