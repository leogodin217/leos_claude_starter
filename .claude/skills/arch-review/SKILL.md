---
name: arch-review
description: Review pending architecture docs. Judge whether the design will deliver the change it describes and whether an implementer could build it without inventing semantics.
agent: architect
---

# Architecture Review

Review a pending architecture doc — a doc that describes a specific change we
want to make to the system (a new feature, a refactor, or a redesign).

**Review the change, not the doc.** Your job is to judge whether the design
delivers what the `Problem` section says it should, and whether the contracts,
semantics, and invariants are complete enough that an implementer could build
it without inventing things. Document hygiene, section ordering, and prose
partition are not the point.

**The doc is a draft.** Nothing in it is settled. You can recommend adding
sections, removing sections, or rescoping the design. But every recommendation
must trace back to a concrete implementation risk, not aesthetic preference.

**The design talks about the system, not about docs.** Review the system the
design specifies — its code, contracts, semantics, invariants, reasoning.
Findings about which sibling docs will go stale, who updates them, whether a
section is "superseded," or which doc sections drift after implementation are
out of scope. If you see the pending doc itself talking about sibling-doc
updates — "X doc must be updated," "this supersedes section Y of Z," "today's
W doc says..." in diff voice — flag it as drift.

This is pre-implementation work. Do not mention sprints, file inventories,
line ranges, or import rewrites — those are sprint-planning mechanics. If the
doc contains them, flag it as drift.

---

## The primary lens

For every finding, ask: *would an implementer have to invent semantics, a
contract, or an invariant to build this?* If yes, the design has a real gap.
If no, you may be reviewing the doc rather than the design.

A solid pending design is **implementable as written**: a competent
implementer could build it without inventing semantics, and the resulting
code would not contradict shipped code, sibling subsystems, or the principles
in `CLAUDE.md`.

Concretely, check:

- **Does the design deliver the Problem?** Read `Problem`, then read
  `Semantics` + `Interface Contracts`. If you can't trace each part of the
  problem to a part of the solution, the design has a gap.
- **Semantic completeness** — every behavior the design introduces is
  specified. No hand-waving.
- **Contract completeness** — every function signature has Args, Returns,
  Raises. Every model has fields with types. No `...` bodies.
- **Invariant coverage** — invariants the design relies on are stated.
  New invariants the design introduces are stated.
- **Principle compliance** — every principle in `CLAUDE.md` § Core Principles,
  and its vocabulary. The ones a design most often trips: no defaulting of
  author-specified values, no future scaffolding, no compatibility shims, and
  whatever architectural rule the repo states about how components compose.
  Cite principles by name; the numbering is local to each repo.
- **Internal consistency** — Semantics, Contracts, and Validation Rules
  agree. The doc doesn't contradict itself.

---

## Feature completeness (the scope check that matters)

The one scope question worth asking: **is this design usable end-to-end after
implementation, or does it need a sibling design to land first?**

A design is incomplete when:

- The implementer would have to invent load-bearing semantics.
- An invariant the design relies on isn't stated anywhere — not here, not in
  a shipped sibling doc.
- The "feature" isn't usable end-to-end after implementation. A verb is
  introduced without its companion verb. A writer is designed without a
  reader. A new contract depends on an interface a sibling package lacks and
  the design doesn't specify how that interface is added.

If part of the feature is genuinely separable and deferred, that should be
called out explicitly in the doc. Silent omission is the failure mode.

What is **not** worth a finding:

- Whether the doc "owns" the right set of packages (no `owns` field exists).
- Whether sections could be split across multiple pending docs.
- Whether the doc's section ordering matches a template.
- Prose wording, voice, or tense — unless it causes ambiguity an implementer
  would have to resolve by inventing.

---

## Context posture

**Full architecture.** Run `/understand architecture` first — it loads the
pipeline boundaries and `docs/PROCESS.md` a pending doc is judged against.
`CLAUDE.md` is already in context. On top of the bundle, load:

1. Forward constraints binding this design — `## Forward constraints introduced` in the architecture docs of the subsystems it touches, plus `python3 ~/.claude/skills/note/cli.py list --forward --area <area>` (`decision` entries are binding)
2. The pending doc(s) under review
3. Sibling architecture docs the design references — load only as needed

---

## Phase 1: Find issues

Think hard. Read with the framing above. Categorize each issue:

| Category | Meaning |
|---|---|
| **Missing spec** | Behavior referenced but not defined. The implementer would have to invent it. |
| **Contract gap** | Signature, type, or invariant absent or incomplete. |
| **Feature incomplete** | The design doesn't deliver the Problem end-to-end; a load-bearing piece is missing or silently deferred. |
| **Inconsistency** | The doc contradicts itself, or contradicts shipped code or a sibling doc in a region the design is *not* intending to change. A sibling doc describing today's behavior that the pending doc proposes to change is the delta, not an inconsistency. |
| **Principle violation** | Conflicts with a principle in `CLAUDE.md`. |
| **Drift** | Doc contains implementation mechanics (file lists, line ranges, helper names) that don't belong in architecture. |
| **Design question** | Multiple valid approaches; needs a decision. |

### Severity

**`high` is reserved for findings that would block implementation.** Use it
only when:

- An implementer would have to invent a contract, semantics, or an invariant.
- A principle in `CLAUDE.md` is violated.
- The design contradicts shipped code, or contradicts a sibling architecture
  doc in a region the design is not intending to change, in a way that would
  cause incorrect behavior. (Divergence from a sibling doc that the design
  exists to update is *not* a contradiction — it's the change.)
- A load-bearing piece of the feature is missing.

**`medium`** — a real problem the implementer can work around but shouldn't
have to (an unstated edge case, an ambiguous return value, a validation rule
that's described but not specified).

**`low`** — a fixable issue that doesn't change what gets built (a typo in a
signature, a missing example, an obvious clarification).

**Do not report** — doc wording, section ordering, prose tense, partition
aesthetics, or anything that wouldn't change what an implementer produces.

---

## Phase 2: Present findings

Present all findings in a single summary table with columns: severity,
category, description. Include enough context (doc section, snippets) for the
user to understand each issue without reading further.

Then ask: **"Do you want to discuss any of these, or should I just fix them?"**

## Phase 3: Resolution

- **Design questions** with multiple valid approaches → present options and wait for user decision.
- **Feature-incomplete findings** → present as a design question. Lay out options (extend the design, defer with explicit call-out) and wait for user decision before changing the doc.
- **Missing spec, contract gap, inconsistency, principle, drift findings** → fix directly if the user says "fix them."
- **User wants to discuss specific items** → discuss, then fix after agreement.

## Phase 4: Completion

Summarize what changed. If significant issues remain, the user may request another round.

## Output

After each round, summarize:
- Issues found: N (by severity)
- Resolved: N
- Remaining: N (with brief list)
