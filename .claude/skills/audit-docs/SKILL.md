---
name: audit-docs
description: Orchestrate sequential documentation audits with checkpointing and resumption.
disable-model-invocation: true
---

# Audit Docs

Orchestrate sequential documentation audits with file-based checkpointing. Enables resumption across sessions.

## Output Location

```
docs/audits/
  YYYY-MM-DD_HHMMSS/
    manifest.yaml         # checkpoint state
    summary.md            # generated after all audits complete
    findings/
      actors.md
      behaviors.md
      ...
```

## Process

### 1. Check for Incomplete Session

Look for existing sessions:
```
Glob: docs/audits/*/manifest.yaml
```

For each manifest found, read it. If any has `status: auditing` or `status: summarizing`:

```
AskUserQuestion:
  question: "Found incomplete audit session from {session_id}. How should I proceed?"
  options:
    - "Resume the incomplete session"
    - "Start a fresh audit (abandons previous)"
```

If "Resume" → skip to Phase 2 or 3 based on manifest status.
If "Start fresh" → continue to initialization.

If no incomplete sessions found, proceed to initialization.

### 2. Initialize Session

Create session folder:
```
session_id = current timestamp as "YYYY-MM-DD_HHMMSS"
folder = docs/audits/{session_id}/
```

Create the folder structure:
```
docs/audits/{session_id}/
docs/audits/{session_id}/findings/
```

Discover architecture docs:
```
Glob: docs/architecture/*.md
```

**Exclude:**
- `README.md` (index/navigation)
- `PROCESS.md` (workflow documentation)

Write initial manifest:
```yaml
session_id: "{session_id}"
created_at: "{ISO timestamp}"
status: "auditing"
docs:
  - name: "actors.md"
    path: "docs/architecture/actors.md"
    status: "pending"
    error: null
  - name: "behaviors.md"
    path: "docs/architecture/behaviors.md"
    status: "pending"
    error: null
  # ... all discovered docs
```

Report: "Created audit session {session_id} with {N} docs to audit."

### 3. Audit Phase (Sequential, Checkpointed)

Read manifest to find docs with `status: pending`.

For each pending doc, **one at a time**:

1. **Update manifest** - set doc `status: "auditing"`

2. **Launch doc-auditor agent** (NOT in background):
   ```
   Task(
       subagent_type="doc-auditor",
       prompt="Audit this architecture doc against implementation.\n\ndoc_path: {doc_path}",
       run_in_background=false
   )
   ```

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

5. **Report**: "Audit complete. Summary written to docs/audits/{session_id}/summary.md"

### 5. Present and Ask for Approval

Display the summary to the user (read and output summary.md content).

Then ask:
```
AskUserQuestion:
  question: "How should I proceed with documentation updates?"
  options:
    - "Fix all findings"
    - "Show me the specific changes first"
    - "Skip updates for now"
```

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

After fixes, offer to re-run audit on modified docs only:
```
AskUserQuestion:
  question: "Want me to verify the fixes?"
  options:
    - "Yes, re-audit modified docs"
    - "No, I'll review manually"
```

---

## Manifest Schema

```yaml
session_id: str        # "YYYY-MM-DD_HHMMSS"
created_at: str        # ISO 8601 timestamp
status: str            # "auditing" | "summarizing" | "complete"
docs:
  - name: str          # "actors.md"
    path: str          # "docs/architecture/actors.md"
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

1. **Explicit references:** Look for `src/fabulexa/...` paths in the doc
2. **Code References section:** Many docs have a table linking topics to files
3. **Naming convention:** `{name}.md` often maps to `src/fabulexa/{name}/`

The agent should NOT rely on a hardcoded mapping.

---

## Example: Fresh Run

```
User: /audit-docs

Claude: Checking for incomplete sessions...
        No incomplete sessions found.

        Creating audit session 2025-01-21_143022 with 10 docs to audit.

        Auditing actors.md...
        Completed 1/10: actors.md - 2 findings

        Auditing behaviors.md...
        Completed 2/10: behaviors.md - 0 findings

        ...

        Audit complete. Summary written to docs/audits/2025-01-21_143022/summary.md

        # Documentation Audit Summary
        ...

        How should I proceed with documentation updates?
        [Fix all findings] [Show changes first] [Skip updates]
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

        Auditing simulation.md...
        Completed 7/10: simulation.md - 1 finding

        ...
```
