# Claude Code Project Template

A template for LLM-assisted software development with structured planning, implementation, and review workflow.

## Important

This is how my process evolved over time to plan and write code wiith CC. 

What thiis does:

* Defines processes for starting and maintaining a new product. 
* Uses what works for me in CC
* Hopefully, helps people get started a little quicker. 

What this does not:

* Revolutionize anything. (Why does everyone "revolutionize". Let's be real, here.)
* Implement known best practices. (Do those exist?)
* Prevent you from defining your own processes or modifying these ones. 

People ask how to get started and this is a resource for them. That's it. I highly encourage everyone to learn by doing. Trial and error in unavoidable.  


## Quick Start

1. Copy this template to your project
2. Run `/get-started` to configure your project interactively
3. Start designing with `/arch-design`

The `/get-started` skill walks you through:
- Defining your project identity
- Choosing your core principles
- Setting up initial capabilities
- Configuring invariants

Or customize manually - see `CUSTOMIZATION.md` for detailed guidance.

## Workflow

```
/get-started       →  Configure project (run once)
/arch-design       →  Design interfaces, create architecture docs
/create-sprint     →  Plan implementation phases
/eval-sprint       →  Evaluate sprint spec before implementation
/implement-sprint  →  Execute the plan
/review-sprint     →  QA and verify
/verify-sprint     →  Final verification of sprint deliverables
/audit-docs        →  Keep documentation accurate
```

## Directory Structure

```
project/
├── CLAUDE.md                    # Principles, invariants, navigation
├── docs/
│   ├── CAPABILITIES.md          # What the system does (status tracking)
│   ├── SCRATCHPAD.md            # Temporary context used during or between sessions.
│   ├── architecture/
│   │   ├── README.md            # Index, reading order
│   │   ├── PROCESS.md           # Development process
│   │   └── {feature}.md         # Design docs per subsystem
│   └── sprints/
│       └── sprint-{N}.md        # Sprint specifications
├── .claude/
│   ├── agents/                  # Worker definitions (architect, implementer)
│   └── skills/                  # Process definitions (slash commands)
└── src/                         # Your source code
```

## Agents vs Skills

| Type | Purpose | Location |
|------|---------|----------|
| **Agents** | Workers with specific expertise | `.claude/agents/` |
| **Skills** | Processes that orchestrate work | `.claude/skills/` |

Agents do focused work (design, implement). Skills define workflows that may use agents.

## SCRATCHPAD Pattern

`docs/SCRATCHPAD.md` Temporary context that doesn't fit into established docs.  
- Create temporary in-between session context. 
- Write plans when not in plan mode. 

**Important: ** Claude never writes to this file unless instructed. This is for the end user to manage. 

## Philosophy

### Principles Are Guardrails

Without explicit principles, LLMs optimize locally and lose coherence across a project. Principles enable autonomous decision-making within bounds.

Good principles:
- Are specific enough to apply ("fail fast" not "be robust")
- Sometimes conflict (forces explicit tradeoffs)
- Include concrete examples and counter-examples

### Three-Phase Workflow

| Phase | Catches |
|-------|---------|
| **Architect** | Design issues, missing requirements |
| **Implement** | Execution errors |
| **Review** | Drift from spec, principle violations |

Each phase uses a fresh context, preventing accumulated assumptions from hiding problems.

### Code Is Truth

After implementation, code is the specification. Documentation:
- Links to code, doesn't duplicate it
- Captures rationale (why X over Y)
- Gets pruned after implementation

### Specialized Agents

Each role loads minimal context and stays focused:
- **Architect**: Design only, no implementation
- **Implementer**: Execute spec, no design changes
- **Reviewer**: Fresh eyes, loads spec not implementation context

## Customization Guide

See `CUSTOMIZATION.md` for detailed guidance on:
- Writing effective principles
- Structuring architecture docs
- Creating sprint specs
- Adding domain-specific agents

## Feature Lifecycle

```
1. NEED IDENTIFIED
   └── User request or roadmap item

2. ARCHITECTURE (/arch-design)
   ├── Create docs/architecture/{feature}.md
   └── Update docs/CAPABILITIES.md (status: Not Started)

3. SPRINT PLANNING (/create-sprint)
   ├── Reference architecture doc
   └── Create docs/sprints/sprint-N.md

4. SPRINT EVALUATION (/eval-sprint)
   └── Review spec for completeness before implementation

5. IMPLEMENTATION (/implement-sprint)
   ├── Execute phases in order
   └── Update CAPABILITIES.md (status: In Progress)

6. REVIEW (/review-sprint)
   ├── Verify against sprint spec
   └── Check principle compliance

7. VERIFICATION (/verify-sprint)
   └── Final verification of sprint deliverables

8. DOCUMENTATION (/audit-docs)
   ├── Prune architecture doc, link to code
   └── Update CAPABILITIES.md (status: Complete)
```

## Credits

This template is based on the development process used in [Fabulexa](https://github.com/leogodin217/fabulexa_sim), a configuration-driven simulation engine for educational data generation.
