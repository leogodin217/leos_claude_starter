---
name: arch-design
description: Design architecture docs for new features, refactors, or redesigns. Produces implementation-ready docs with complete file impact analysis.
disable-model-invocation: true
argument-hint: [feature-name or issue path]
---

# Architecture Design

Design an architecture doc for a new feature, refactor, or redesign. Produces a doc in `docs/architecture/pending/` with complete file impact analysis.

## Inputs

The user provides one of:
- A feature name or concept (e.g., "behavior mutations")
- A path to an issue doc (e.g., `docs/issues/002-behavior-mutations.md`)
- A description of the problem to solve

## Process

### Checkpoint 1: Problem + Solution (wait for user approval)

1. **Load context:**
   - `docs/CAPABILITIES.md` — current capability status
   - `docs/architecture/README.md` — architecture overview + reading order
   - If user provided an issue path, read that too

2. **Write Problem and Solution sections:**
   - Problem: What's wrong or missing. Include a concrete example (config snippet, error, limitation).
   - Solution: High-level approach. One paragraph + diagram or YAML snippet.

3. **Present to user for approval.** Do not continue until they confirm the direction is right.

### Automated Phase (after direction is approved)

4. **Load relevant architecture docs** per README.md reading order for the area being designed.

5. **Read existing source code** that the design touches. Use Grep/Glob/find_references to locate all relevant files.

6. **Write remaining sections** using the template at `.claude/skills/arch-design/template.md`:
   - **Semantics** — behavioral rules, edge cases, ordering, timing
   - **Configuration** — YAML examples if the feature has educator-facing config
   - **Interface Contracts** — function signatures with full docstrings
   - **Validation Rules** — parse-time (Pydantic) and business rules
   - **Implementation Impact** — the key section (see below)
   - **What Doesn't Change** — explicit scope boundaries

7. **Build the Implementation Impact section:**
   - Use Grep to find every import of types/functions being moved or modified
   - Use find_references for symbols being renamed or relocated
   - Use Glob to find test files that cover affected modules
   - For each file: action (Create/Modify), path, one-line description of change
   - Separate into: Source Files, Test Files, Import Updates
   - The Import Updates table must show current import → new import for every file affected by moves/renames

8. **Write the complete doc** to `docs/architecture/pending/<name>.md`

9. **Present the full doc to user** with a summary of:
   - Total files affected (create/modify counts)
   - Import sites found
   - Any design decisions that could go either way (flag for user)

## Quality Rules

- **No invented scenario values** (Principle #7) — contracts must not introduce defaults for educator-specified parameters
- **No future scaffolding** (Principle #8) — design only what this feature needs, not extensibility for hypothetical future work
- **Breaking changes are fine** (Principle #9) — don't add compatibility shims
- **Complete import tracing** — every file that imports a moved/renamed symbol must appear in the Import Updates table. Use Grep for `from module import symbol` and `import module` patterns.
- **Concrete contracts** — every function signature includes Args, Returns, Raises. No `...` bodies in the doc; show the signature and docstring only.
- **Testable sections** — Semantics section should use tables (Condition | Result) so sprint specs can derive test cases directly.
- **No implementation code** — design docs contain signatures and docstrings, never implementation bodies. Describe behavior in prose and tables, not code blocks with for-loops or if-statements. Wrong: showing the literal code to insert into `processor.py`. Right: "After `execute_action()` returns non-empty decisions, apply mutations and record history if tracked."
- **No duplication with sprint specs** — the design doc provides rationale, semantics, and constraints (the WHY). The sprint spec provides contracts, phases, and test cases (the WHAT). If a sprint spec will be written from this design doc, the sprint planner extracts contracts from here — don't write content that forces the planner to duplicate or filter.

## Output Location

`docs/architecture/pending/<feature-name>.md`

The `pending/` directory holds designs that haven't been implemented yet. After sprint completion, move to `docs/architecture/` if the design becomes a permanent reference, or delete if it was consumed by the sprint spec.
