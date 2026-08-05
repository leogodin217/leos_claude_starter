# Agents and Skills

**Agents** are workers with specific expertise, tools, and constraints,
invoked via the Task tool. **Skills** are processes that orchestrate work,
invoked via the Skill tool (slash commands). Skills dispatch agents.

## Shared agents (symlinked into adopting repos)

| Agent | Purpose |
|-------|---------|
| `architect` | System design, interface contracts, ADRs |
| `implementer` | Code, tests, demos matching a sprint spec exactly |
| `reviewer` | Fresh-eyes review: principle compliance, anti-patterns |
| `doc-auditor` | Docs-vs-code discrepancy audit |
| `test-reviewer` | Test value, quality, and gap review |

These bodies are repo-neutral by contract:

- **No repo principle content.** Repo principles reach agents two ways: the
  SubagentStart hook injects the repo's `worker-protocol.md` (which carries
  the repo's config-boundary section), and agents read the repo's `CLAUDE.md`
  § Core Principles at task start.
- **No principle citations by number.** Numbering is repo-local and collides
  across repos; shared bodies cite principles by name only.
- **No repo vocabulary.** Prose names roles (author, source tree, output
  judge), never one repo's instances.

Each adopting repo adds its own **output-judge agent** (named by the
`output-judge-agent` shape key) — an agent that reads program output rather
than source, listed in the inject hook's `CODE_NAV_EXEMPT`.

See `ADOPTION.md` at the repo root for the full contract.

## Adding an agent

Create `.claude/agents/<name>.md`:

```markdown
---
name: agent-name
description: Brief description for the Task tool
tools: Tool1, Tool2, Tool3
model: sonnet
---

You are the {Role}. {One-sentence job.}

## What You Produce
## What You Do NOT Do
```

Design rules: minimal context, explicit "do not" constraints, exact output
format, only the tools the agent needs. If the agent is general — useful to
any adopting repo — it belongs here and must meet the repo-neutral contract
above. If a sentence in it cannot be written without naming one repo's nouns,
it is a repo agent; keep it in that repo.
