---
name: audit-docs
description: Orchestrate sequential documentation audits with checkpointing and resumption.
disable-model-invocation: true
argument-hint: package_name
---

# Audit Docs

Orchestrate sequential documentation audits with file-based checkpointing. Enables resumption across sessions.

## Context posture

**Task-scoped — the audited subsystem's docs and the code they claim.** Do NOT
run `/understand`; do NOT load repo-wide architecture. An audit asks whether
*this subsystem's* docs match *its own* code, and wider context lets the
orchestrator paper over a gap from memory instead of flagging it. The
`doc-auditor` agents load what each audit area needs, in their own contexts.

## Output Location

An audit writes beside the docs it audited. **`<audit-root>` below means an
`audits/` sibling of the `architecture/` directory the discovery step globbed**
— so findings live with the subsystem they concern, in either repo layout. In
this repo that resolves to `packages/<pkg>/docs/audits/`.

```
<audit-root>/
  YYYY-MM-DD_HHMMSS/
    manifest.yaml         # checkpoint state
    summary.md            # generated after all audits complete
    findings/
      config.md
      validation.md
      ...
```

## Process

### 1. Check for Incomplete Session

Look for existing sessions:
```
Glob: <audit-root>/*/manifest.yaml
```

For each manifest found, read it. If any has `status: auditing` or `status: summarizing`:

Ask in chat — not via the question interface (`CLAUDE.md` § Asking Questions):
name the session id and its status, and offer resuming it or starting fresh
(which abandons it).

If "Resume" → skip to Phase 2 or 3 based on manifest status.
If "Start fresh" → continue to initialization.

If no incomplete sessions found, proceed to initialization.

### 2. Initialize Session

Create session folder:
```
session_id = current timestamp as "YYYY-MM-DD_HHMMSS"
folder = <audit-root>/{session_id}/
```

Create the folder structure:
```
<audit-root>/{session_id}/
<audit-root>/{session_id}/findings/
```

Ask the repo where its subsystem docs live, rather than assuming a layout:

```bash
~/.claude/skills/understand/load.py . --field subsystem-docs
```

Glob `*.md` under what it prints — that is one directory per subsystem in a
packaged repo, and a single flat directory in a repo that keeps them together.
This one call is the whole reason this skill can run unmodified in either.

**Exclude:**
- `README.md` (index/navigation)

Write initial manifest:
```yaml
session_id: "{session_id}"
created_at: "{ISO timestamp}"
status: "auditing"
docs:
  - name: "config.md"
    path: "{discovered path}"        # repo-relative, as globbed above
    status: "pending"
    error: null
  # ... one entry per discovered doc
```

Report: "Created audit session {session_id} with {N} docs to audit."

### 3. Audit Phase (Sequential, Checkpointed)

Read manifest to find docs with `status: pending`.

For each pending doc, **one at a time**:

1. **Update manifest** - set doc `status: "auditing"`

2. **Launch doc-auditor agent** via the **Agent tool** (foreground — one doc at a time):
   ```
   Agent(
       subagent_type="doc-auditor",
       description="Audit {doc_name}",
       prompt="Audit this architecture doc against implementation.\n\ndoc_path: {doc_path}"
   )
   ```
   The call blocks until the agent finishes and returns its final message directly as the result.

3. **Write findings file** - take agent response and write to `findings/{doc_name}`:
   ```markdown
   # Audit: {doc_name}

   **Audited:** {ISO timestamp}
   **Doc path:** {doc_path}

   ## Findings

   {findings from agent, numbered list}

   ## Verified Accurate

   {verified items from agent, bullet list}
   ```

4. **Update manifest** - set doc `status: "complete"`

5. **Report progress**: "Completed {n}/{total}: {doc_name} - {X} findings"

6. **Continue to next pending doc**

**If agent returns error:** Set doc `status: "error"`, `error: "{message}"`, continue to next doc.

**Checkpoint guarantee:** After each doc, manifest reflects current state. If context exhausts, next session resumes from manifest.

### 4. Summary Phase

Once all docs have `status: complete` or `status: error`:

1. **Update manifest** - set `status: "summarizing"`

2. **Read all findings files** from `findings/` folder

3. **Generate summary.md**:
   ```markdown
   # Documentation Audit Summary

   **Session:** {session_id}
   **Completed:** {ISO timestamp}

   ## Overview

   - Docs audited: {total}
   - Docs with findings: {count with findings}
   - Docs verified accurate: {count with no findings}
   - Docs with errors: {count with errors}

   ## Findings

   ### {doc_name}

   {copy findings section from that doc's file}

   ### {doc_name}

   ...

   ## Verified Accurate

   - {doc_name}
   - {doc_name}
   - ...

   ## Errors

   - {doc_name}: {error message}
   - ...
   ```

4. **Update manifest** - set `status: "complete"`

5. **Report**: "Audit complete. Summary written to <audit-root>/{session_id}/summary.md"

### 5. Present and Ask for Approval

Display the summary to the user (read and output summary.md content).

Then ask in chat how to proceed — fix all findings, show the specific changes
first, or skip updates for now.

### 6. Apply Fixes (If Approved)

For each finding to fix:

1. Read the doc
2. Locate the incorrect section
3. Edit to match implementation
4. Follow "Code Is Truth" principle:
   - Prune duplicated details (link to code instead)
   - Keep rationale and invariants
   - Remove stale content

Report each change made.

### 7. Verification (Optional)

After fixes, offer in chat to re-audit the modified docs only.

---

## Manifest Schema

```yaml
session_id: str        # "YYYY-MM-DD_HHMMSS"
created_at: str        # ISO 8601 timestamp
status: str            # "auditing" | "summarizing" | "complete"
docs:
  - name: str          # "config.md"
    path: str          # repo-relative path as globbed from subsystem-docs
    status: str        # "pending" | "auditing" | "complete" | "error"
    error: str | null  # error message if status=error
```

---

## Findings File Format

```markdown
# Audit: {doc_name}

**Audited:** {ISO timestamp}
**Doc path:** {path}

## Findings

1. **{title}**
   - Doc says: "{quote from doc}"
   - Code does: {actual behavior}
   - Location: {file}:{line}

2. **{title}**
   ...

## Verified Accurate

- {item verified correct}
- {item verified correct}
```

---

## Doc-to-Code Mapping

The doc-auditor agent discovers code paths from within the doc itself:

1. **Explicit references:** source paths named in the doc
2. **Code References section:** Many docs have a table linking topics to files
3. **Naming convention:** `<name>.md` often maps to a `<name>/` module in the
   subsystem's source tree

The agent should NOT rely on a hardcoded mapping.

---

## Example: Fresh Run

```
User: /audit-docs

Claude: Checking for incomplete sessions...
        No incomplete sessions found.

        Creating audit session 2025-01-21_143022 with 10 docs to audit.

        Auditing config.md...
        Completed 1/10: config.md - 2 findings

        Auditing validation.md...
        Completed 2/10: validation.md - 0 findings

        ...

        Audit complete. Summary written to <audit-root>/2025-01-21_143022/summary.md

        # Documentation Audit Summary
        ...

        How should I proceed with documentation updates — fix all findings,
        show the specific changes first, or skip updates for now?
```

## Example: Resume After Context Exhaustion

```
User: /audit-docs

Claude: Checking for incomplete sessions...
        Found incomplete audit session from 2025-01-21_143022.
        Progress: 6/10 docs complete.

        How should I proceed?
        [Resume the incomplete session] [Start a fresh audit]

User: Resume

Claude: Resuming session 2025-01-21_143022...

        Auditing pipeline.md...
        Completed 7/10: pipeline.md - 1 finding

        ...
```
