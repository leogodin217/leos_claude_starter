---
name: whats-next
description: Diagnose project state and recommend the next concrete step. Spans architecture, implementation, QA, docs, and use-case work.
---

# What's Next

Look at overall project state and recommend the next concrete step. Output a single primary recommendation with rationale, one or two alternatives, and any smell-flags worth surfacing before the user commits.

This skill is **diagnostic and advisory**. Do not start work. End by handing the choice back to the user.

---

## Context posture

**Full architecture.** Run `/understand architecture` first — it loads the
pipeline and the `docs/CAPABILITIES.md` outline, which together frame what
"next" can mean. `CLAUDE.md` is already in context.

Then read in this order, stopping early if a clear direction emerges:

1. `docs/architecture/README.md` Status table — designed vs. implemented per area.
2. `CLAUDE.md` Phase Status — current phase scope.
3. `docs/sprints/` — the most recently modified sprint directories. Each sprint is `docs/sprints/<name>/`; there is no `current/` or `archive/`, and old sprints are deleted rather than moved.
4. `docs/architecture/pending/*.md` — every pending design. There is no per-subsystem pending location. Use `tools/mdnav` first; only read sections that look relevant.
5. **Obsidian features:** `python3 ~/.claude/skills/note/cli.py list --type feature` returns proposed features by default; also run `--type feature --status scheduled` to see what is queued for next-up. Each feature carries `area`, `priority` (p0/p1/p2), `depends-on`, and `related-code`. These are explicit future-work candidates — read bodies of high-priority entries and any blocking dependencies.
6. **Obsidian forward-notes:** `python3 ~/.claude/skills/note/cli.py list --forward`. Skim titles and areas; read bodies of any whose subject relates to current work. `decision` entries are binding rules the team settled; the rest carry deferred design hypotheses, scale-roadmap context, and "may change" guidance. All of it lives out of repo.
7. `git log --oneline -20` and `git status` — what just landed, what's uncommitted.
8. `python3 ~/.claude/skills/note/cli.py list --type finding --status open` — open findings by severity.

Do not read implementation source unless a candidate recommendation requires it to assess feasibility. This skill is fast.

---

## Candidate Domains

A recommendation may live in any of these. Consider all before picking.

| Domain | What it looks like |
|---|---|
| Architecture | A pending design to start, finish, or split. |
| Implementation | A finalized design ready to sprint. |
| QA / verification | Invariants without tests; doc–code drift (run `audit-docs`); test gaps in shipped code. |
| Cleanup | Stale pending docs; paused designs to delete or mark; forward-constraint entries whose retirement trigger has been met but were not pruned post-sprint. |
| Use cases | A `CAPABILITIES.md` claim or composable-outcome that is not yet demonstrable end-to-end. |
| Process | A skill, rubric, or workflow that would unblock recurring friction. |

If the project has shipped subsystems but nothing demonstrable end-to-end, lean toward use cases. If it has many pending designs but few implementations, lean toward implementation. Bias toward whatever has been blocked the longest.

---

## Diagnostic Heuristics

Apply these to every candidate before recommending it. Each is a stop-and-rethink trigger, not a hard rule.

| Heuristic | Smell |
|---|---|
| **Foundation check** | Does the candidate's contract have all its prerequisites designed and (where required) implemented? Missing foundation → recommend the foundation instead. |
| **Consumer check** | Does the candidate ship a concrete first consumer in the same sprint or an existing one? A contract with no caller mutates indefinitely. |
| **Bundling check** | Can you name two or more independent open questions inside the candidate? If yes, recommend splitting before starting. |
| **Mutual citation** | Do two pending designs cite each other? Usually a missing layer underneath. Recommend the layer. |
| **Boundary defense** | Does a pending doc repeatedly assert "X is out of scope"? The boundary is probably wrong; the absent X is deforming the design. |
| **Cycle count** | Has any pending doc been through ≥3 review cycles without convergence? Treat as a stop-and-rethink signal, not a grind-harder signal. |
| **Test ergonomics** | Can the candidate be tested without standing up half another subsystem? If not, the contract is over-coupled. |
| **Forward-constraint rot** | Are `## Forward constraints introduced` entries, or forward `decision` notes, anticipated rather than discovered? Anticipated entries handcuff future designers; flag them. Also flag any whose retirement trigger was met by a shipped sprint but never pruned. |

---

## Output

Produce **one** response with this shape. Keep it tight; the user is choosing, not reading prose.

```
## Recommendation

<One sentence: do X next.>

**Why now.** <2–4 sentences. Cite the heuristic(s) that point here and the
specific project-state evidence — file paths, status-table rows, sprint
names, doc lengths, review-cycle count.>

**Scope guardrails.** <Bullet list of what this candidate must NOT bundle,
based on the bundling check. If none apply, omit this block.>

**First consumer.** <Name the concrete thing that will exercise this work.
If none exists, surface that as a problem, not a solution.>

## Alternatives

1. **<Alt 1>.** <One sentence why it's plausible. One sentence why it lost.>
2. **<Alt 2>.** <Same shape. Omit if there isn't a real second alternative.>

## Smells worth flagging

- <Each bullet: a smell from the heuristics table that applies to the
  current project state, regardless of whether it changed the recommendation.
  Cite file paths.>

## Decision needed from you

<One question. Usually: "proceed with <recommendation>, switch to one of the
alternatives, or push back on framing?">
```

---

## Quality Rules

- **Cite evidence.** Every claim about project state names a file, sprint, or commit. No "it seems like" without a path.
- **Recommend concrete next steps, not directions.** "Design the run-driver sprint" beats "work on the core layer."
- **One primary, max two alternatives.** Three options is a non-answer.
- **Surface smells even when they don't change the recommendation.** The user may want to act on them separately.
- **No new files.** This skill produces a recommendation, not artifacts.
- **Be willing to recommend cleanup or process.** Not every answer is a new sprint. A stale paused design that should be deleted is a valid recommendation.
- **Be willing to push back.** If the project's declared next step — an in-flight sprint, a scheduled feature note — is wrong by these heuristics, say so explicitly.

## DO NOT

- Start designing or implementing the recommended work.
- Recommend more than three things total (one primary + up to two alts).
- Use the heuristics as a checklist in the output. They're inputs to your judgment, not deliverables.
- Recommend something blocked by a missing foundation without flagging the foundation.
