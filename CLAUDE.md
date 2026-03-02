# {Project Name}

**{One-sentence description of what the project does.}**

{Optional 2-3 sentence elaboration of the problem space.}

```
{Simple ASCII diagram showing data/control flow}
```

## LLM-Driven Project

This project uses LLM-assisted development. All documents are optimized for LLM context efficiency while maintaining comprehensive coverage.

---

## Core Principles

These principles are **non-negotiable** and guide all decisions.

<!--
CUSTOMIZATION GUIDE:
- Keep 5-9 principles (fewer = forgotten, more = ignored)
- Each principle needs: name, one-line summary, concrete examples
- Include both "what to do" and "what this prohibits"
- Principles should conflict sometimes (forces explicit tradeoffs)
-->

### 1. {User Focus Principle}

{What must be true about user experience?}

**Examples:**
- {Concrete example of this principle in action}
- {Another example}

**What this prohibits:**
- {Concrete anti-pattern}

### 2. {Configuration Philosophy}

{How configurable vs. opinionated is the system?}

### 3. {Quality Philosophy}

{What tradeoffs are acceptable?}

**Example principles:**
- "Good enough beats perfect" - Educational effectiveness > statistical accuracy
- "Correctness is non-negotiable" - All outputs must be verifiable

### 4. {Error Handling Philosophy}

{How to handle invalid input, edge cases?}

**Example principles:**
- "Fail fast" - Invalid input = error with clear message, never guess
- "Be lenient" - Accept varied input, normalize internally

### 5. No Future Scaffolding

Don't write code for functionality that doesn't exist yet. Add it when the feature is implemented, not before.

**What this prohibits:**
- Loops that iterate but do nothing (`for x in items: pass`)
- Method stubs for unimplemented features
- Parameters accepted but ignored
- `# TODO:` comments with placeholder code

**What this permits:**
- Extension points that ARE used (abstract classes with implementations)
- Comments explaining design decisions (not placeholders)

### 6. {Breaking Change Policy}

{How to handle API/schema changes?}

**Greenfield example:**
Breaking changes are acceptable. Optimize for best design, not backward compatibility. No deprecation warnings or compatibility shims.

**Mature project example:**
Backward compatibility required. Use deprecation warnings, migration paths, semantic versioning.

### 7. {Domain-Specific Principle}

{Principle unique to your problem domain}

---

## Documentation Structure

| Document | Purpose | When to Load |
|----------|---------|--------------|
| `CLAUDE.md` | Principles, invariants, navigation | Always |
| `docs/CAPABILITIES.md` | What the system does | Feature overview |
| `docs/architecture/*.md` | Design + rationale | Implementation, design questions |
| `docs/sprints/` | Sprint specs and status | Sprint work |

**Loading strategy:** See `docs/architecture/README.md` for document index and reading order.

---

## Key Invariants

Always true in this codebase:

| Invariant | Meaning |
|-----------|---------|
| Deterministic | Same inputs = identical outputs |
| Fail fast | Invalid input = error, not default |
| {Custom} | {Description} |
| {Custom} | {Description} |

---

## DO NOT

- Write code for features that don't exist yet (Principle #5)
- {Principle violation from #1}
- {Principle violation from #2}
- {Domain-specific prohibition}
- {Domain-specific prohibition}

---

## Anti-Patterns

Concrete patterns to avoid and detect during review.

### Over-Engineering

| Pattern | Example | Fix |
|---------|---------|-----|
| One-use abstractions | `class BaseX` with single subclass | Inline it |
| Impossible error handling | Validating internal inputs | Trust internal code |
| Defensive copies | `list(x)` for already-owned data | Remove copy |
| Premature helpers | `_format_x()` called once | Inline it |
| Hypothetical features | Designing for "what if" | Build for current needs |

### Dead Code

| Pattern | Detection |
|---------|-----------|
| Unused imports | Linter / grep for usage |
| Uncalled functions | Grep for function name |
| Unreachable branches | `if False:` or impossible conditions |
| Commented-out code | Delete it (git has history) |

### Test Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|--------------|-----|
| Testing framework internals | Tests the library, not our code | Test behavior instead |
| No assertions | False confidence | Add meaningful assertions |
| Implementation details | Brittle to refactoring | Test public interfaces |
| Duplicate coverage | Maintenance burden | Consolidate or delete |

### {Domain-Specific Anti-Patterns}

<!-- Add patterns specific to your domain as you discover them -->

| Pattern | Why It's Bad | Fix |
|---------|--------------|-----|
| {Pattern} | {Why} | {Fix} |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [docs/CAPABILITIES.md](docs/CAPABILITIES.md) | What the system does |
| [docs/architecture/](docs/architecture/) | Design rationale and constraints |
| [docs/sprints/](docs/sprints/) | Sprint specifications |


## Code Navigation
  - Prefer `mcp__cclsp__*` tools over reading entire files for understanding code structure.
  - **Working with pylsp:** `find_definition`, `find_references`, `get_hover`, `get_diagnostics`, `rename_symbol`. Use these freely.
  - For "who calls this function?" questions, use `find_references` or Grep.
  - LSP tools work in both the main conversation and subagents.