# Customization Guide

How to adapt this template for your specific project.

---

## Step 1: Define Your Principles

Principles are the most important customization. They guide all decisions.

### Characteristics of Good Principles

| Good | Bad |
|------|-----|
| Specific and actionable | Vague and aspirational |
| Include examples | Abstract only |
| Sometimes conflict | Always harmonious |
| Say what NOT to do | Only positive statements |

### Principle Categories

Consider one principle from each category:

1. **User Focus** - What must be true about user experience?
   - "Users succeed without code"
   - "Power users can customize everything"
   - "Sensible defaults, full control available"

2. **Configuration Philosophy** - How flexible vs. opinionated?
   - "All behavior is configurable"
   - "Convention over configuration"
   - "Minimal configuration, smart defaults"

3. **Quality Philosophy** - What tradeoffs are acceptable?
   - "Good enough beats perfect"
   - "Correctness is non-negotiable"
   - "Fast iteration over careful planning"

4. **Error Handling** - How to handle problems?
   - "Fail fast with clear errors"
   - "Be lenient and recover gracefully"
   - "Degrade gracefully, never crash"

5. **Change Policy** - How stable is the interface?
   - "Breaking changes are acceptable" (greenfield)
   - "Backward compatibility required" (mature)
   - "Semver strictly enforced"

### How Many Principles?

- **Minimum:** 5 (fewer = gaps in guidance)
- **Maximum:** 9 (more = can't remember them)
- **Sweet spot:** 6-7

### Writing Principle Examples

Each principle should have:

```markdown
### {Principle Name}

{One sentence explanation}

**What this means:**
- {Concrete behavior}
- {Another behavior}

**What this prohibits:**
- {Specific anti-pattern}
- {Another anti-pattern}

**Example:**
{Code or config showing principle in action}
```

---

## Step 2: Define Your Invariants

Invariants are properties that must ALWAYS hold. They're stricter than principles.

### Good Invariants

| Invariant | Why It's Good |
|-----------|---------------|
| "Timestamps never decrease" | Testable, always true |
| "All IDs are unique" | Testable, always true |
| "Config errors fail before processing" | Clear timing guarantee |

### Bad Invariants

| Invariant | Why It's Bad |
|-----------|--------------|
| "Code is clean" | Subjective |
| "Errors are handled" | Vague |
| "Performance is good" | Not measurable as invariant |

### How to Find Invariants

Ask:
- What would break everything if violated?
- What do all tests assume is true?
- What would users rely on being always true?

---

## Step 3: Define Anti-Patterns

Anti-patterns are concrete mistakes to avoid. Add them as you discover them.

### Starting Anti-Patterns

The template includes universal anti-patterns:
- Over-engineering patterns
- Dead code patterns
- Test anti-patterns

### Adding Domain-Specific Anti-Patterns

When you catch a mistake during review, ask:
- Is this likely to recur?
- Can I describe it concretely?
- Is the fix clear?

If yes to all three, add it to CLAUDE.md:

```markdown
### {Domain} Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|--------------|-----|
| {Specific pattern} | {Consequence} | {Solution} |
```

---

## Step 4: Structure Your Capabilities

CAPABILITIES.md tracks what the system does.

### Capability Granularity

- **Too coarse:** "Backend" - not useful
- **Too fine:** "Parse JSON field X" - too detailed
- **Right level:** "User Authentication", "Data Export", "Search"

Each capability should be:
- Independently understandable
- Worth tracking status for
- Large enough to need architecture doc

### Status Values

| Status | Meaning |
|--------|---------|
| Not Started | May have architecture doc, no code |
| In Progress | Active sprint implementing |
| Complete | Implemented, tested, documented |

---

## Step 5: Create Architecture Docs

Create one architecture doc per major subsystem.

### When to Create

Create an architecture doc when:
- Feature is non-trivial (multiple components)
- Design decisions need rationale
- Multiple people will work on it
- Implementation isn't obvious

### What to Include

**Before implementation:**
- Overview and key concepts
- Design decisions with rationale
- Invariants
- Interface sketches

**After implementation (prune):**
- Keep: rationale, constraints, invariants
- Remove: details now in code
- Add: links to implementation

---

## Step 6: Skills and Agents — the Adoption Contract

Skills and agents are no longer customized per repo. The shared bodies live in
this repo and are **symlinked** into adopting repos; repo differences are
handled by declared shape keys, per-repo assembled files (`worker-protocol.md`,
the system prompt), and repo-only skills/agents — never by editing a shared
body for one repo.

**Read `ADOPTION.md`** for the full contract: what the starter provides, the
repo-side artifacts you must add (CLAUDE.md sections, the `understand` bundle
with shape keys, a worker-protocol with your config-boundary section, an
output-judge agent), the `load.py --check` gate, and the ladder for handling a
repo difference without forking a skill.

Genuinely repo-specific skills and agents stay in your repo, in the same
formats — see `.claude/agents/README.md` for the agent format and design
rules; a skill is a directory under `.claude/skills/` with a `SKILL.md`.

---


## Step 7: Use the SCRATCHPAD

`docs/SCRATCHPAD.md` tracks current work across sessions.

### When to Use

Reset the SCRATCHPAD for each major effort:
- New feature implementation
- QA cycle
- Major refactoring
- Migration

### What to Track

| Section | Purpose |
|---------|---------|
| Goal | What we're trying to accomplish |
| Exit Criteria | When this work is done |
| Decisions | Choices made with rationale |
| Phases | Work breakdown with status |
| Context Management | Notes for agent invocations |

### SCRATCHPAD vs Sprint Specs

| SCRATCHPAD | Sprint Spec |
|------------|-------------|
| Working document | Formal specification |
| Updated frequently | Written once, tracked |
| Decisions and notes | Phases and acceptance criteria |
| One per major effort | One per sprint |

Use SCRATCHPAD for informal tracking alongside formal sprint specs.

---

## Maintenance

### Weekly

- Update CAPABILITIES.md status
- Run `/audit-docs` on completed features

### After Each Sprint

- Prune architecture docs
- Add discovered anti-patterns
- Update invariants if needed

### Quarterly

- Review principles - still relevant?
- Clean up unused skills
- Archive old sprint specs

---

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Too many principles | Can't remember them | Consolidate to 5-9 |
| Vague principles | No guidance | Add concrete examples |
| No anti-patterns | Same mistakes repeat | Add as discovered |
| Stale docs | Misleading | Regular audits |
| Skipping architecture | Implementation drift | Require arch doc before sprint |
