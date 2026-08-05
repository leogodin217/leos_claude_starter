# Adoption Contract

How a repo adopts the starter's shared skills, agents, and context tooling.
This is the contract: what the starter provides, what the adopting repo must
provide, and the gate that verifies the handshake. If onboarding a repo
requires something this document does not say, the fix is to this document —
not a private workaround in the repo.

## The model

- **Shared bodies are symlinked, not copied.** Skills and agents listed below
  live here, once. An adopting repo symlinks them; drift is impossible.
  Accepted cost: the repo's git history no longer shows which skill version
  produced a sprint — that history lives in this repo's git.
- **Assembled files are copied, then extended.** `worker-protocol.md` and the
  custom system prompt are per-repo files built from this repo's base plus
  repo-specific sections. Copies are accepted here deliberately; keep the base
  portion byte-identical so drift is greppable.
- **Repo facts are declared, not assumed.** Shared bodies read the shape keys
  an adopting repo declares in its `understand` bundle frontmatter. A skill
  configured by a key names both branches in its own prose and keys them to
  the declared value — there is no templating engine.
- **Degrading a skill is never an option.** If a repo lacks something a shared
  skill reads (a doc section, a bundle, an agent), the repo adds it. A skill
  that quietly does less in one repo is the failure mode this design removes.

## What the starter provides

**Shared skills** (symlink targets): `arch-design`, `arch-review`,
`create-sprint`, `eval-sprint`, `implement-sprint`, `review-sprint`,
`audit-docs`, `fold-pending`, `whats-next`, `remote-sprint` — plus the
infrastructure skills `understand`, `note`, `consult`, `session`,
`remote-session`.

**Shared agents** (symlink targets): `architect`, `implementer`, `reviewer`,
`doc-auditor`, `test-reviewer`. These bodies carry no repo principle content:
repo principles reach them through the injected worker protocol and by reading
the repo's `CLAUDE.md` at task start.

**Assembled-file bases**: `.claude/worker-protocol.md` (generic sections) and
`.claude/system-prompt-base.md` (harness, operating discipline, environment,
tools, verbosity, legibility). A repo's `custom-system-prompt.md` is an intro
line naming the repo plus the base content, delivered by the launch alias.
The base file is pure prompt content — keep repo copies byte-identical to it
below the intro line so drift is greppable.

**Tools**: `tools/mdnav` (markdown outline navigation),
`tools/hooks/mdnav_first.py` (outline-first read enforcement),
`tools/hooks/grep_guard.py` (cclsp-first enforcement),
`tools/hooks/inject_worker_protocol.py` (SubagentStart protocol injection),
`tools/hooks/deny_question_tool.py` (AskUserQuestion block),
`tools/hooks/git_commit_guard.py` (subagent git-write block),
and the `understand` loader (`load.py`, `template.md`). Hooks are symlink
targets like the skills; their per-repo knobs live in the adopting repo's
`.claude/hooks-config.json`, never in the hook body.

### Symlink form

Links are committed **relative**: `../../../leos_claude_starter/...` from
`.claude/skills/`, `.claude/agents/`, and `tools/hooks/`. This assumes two
layout conventions, which the adopting machine must keep:

1. The starter is cloned as a **sibling of the repo** (both under the same
   parent directory).
2. Git worktrees are created at the **same depth** as the main checkout — or,
   if they live one level deeper (e.g. `<parent>/worktrees/<branch>`), the
   machine adds one compensating link:
   `ln -s ../leos_claude_starter <parent>/worktrees/leos_claude_starter`.

## What the adopting repo must provide

### `CLAUDE.md`

Auto-loaded repo identity. Shared bodies read it by **section name**, so these
sections must exist:

- **Core Principles** — including a config-boundary / no-invented-values
  principle stated with reject/accept precision (code examples of what fails
  and what is fine). Shared agents read this section before writing or judging
  code. Principles are cited **by name, never by number** in every shared
  body; numbering is repo-local and collides across repos.
- **Key Invariants**, **Anti-Patterns** — the reviewer's checklist points here.
- **Phase Status** — `whats-next` reads it for current phase scope.

### `.claude/understand/` bundle(s)

At least an `architecture` bundle, with the shape keys declared in its
frontmatter. The five keys (semantics and validation in
`.claude/skills/understand/template.md`, the authority):

| Key | Values | Read by |
|---|---|---|
| `layout` | `monorepo` \| `single-package` | every consumer — decides which prose applies |
| `packages` | directory glob (monorepo only; error under single-package) | worktree bootstrap, per-package gates |
| `subsystem-docs` | directory of per-subsystem architecture docs | doc-loading skills, `audit-docs` |
| `typecheck-hook` | the repo's pre-commit typecheck hook name | `implement-sprint` gate |
| `output-judge-agent` | the repo's output-judging agent name | skills that dispatch an output judge |

`load.py <repo> --check` validates the declaration (unknown key, bad enum,
monorepo-without-packages, file-glob-where-directory-required, dangling agent
reference) and that every bundle selector resolves. **Wire it into pre-commit**
so a renamed heading or missing key fails at commit time, not mid-task.

### `.claude/worker-protocol.md`

Copy the starter base, then append repo-specific sections — at minimum a
config-boundary section restating the repo's no-invented-values principle with
its scope test and reject/accept examples, voiced for what the repo's authors
configure. The shared `reviewer` and `implementer` name this section as their
primary focus; without it their primary focus resolves to nothing.

Register `tools/hooks/inject_worker_protocol.py` as a SubagentStart hook
(matcher `*`) in `.claude/settings.json`.

### `.claude/hooks-config.json`

The per-repo knobs the shared hooks read (missing file or key = safe-empty):

```json
{
  "code_nav_exempt": ["data-analyst"],
  "git_committers": []
}
```

- `code_nav_exempt` — agents that read program OUTPUT, not source code
  (typically the output-judge agent); they receive only the general worker-
  protocol sections, not code navigation.
- `git_committers` — agents allowed to run mutating git besides the top-level
  orchestrator. Empty means orchestrator-only.

### Repo-specific agents and skills

- One **output-judge agent** (whatever `output-judge-agent` names) — the
  repo's own definition, exempt from code-navigation injection.
- Repo-specific skills stay in the repo. A sentence that cannot be written
  without naming a repo-only noun belongs in a repo-only skill, not a shared
  one.

### Docs the shared bodies read

- `docs/architecture/README.md` — architecture index (architect agent,
  architecture-posture skills).
- `docs/PROCESS.md` with a **Documentation Lifecycle** section (architect
  agent follows it).
- Source under a layout matching `':(glob)**/src/**/*.py'` — the portable
  pathspec every shared gate uses.

### Note vault binding (if using vault-integrated skills)

`fold-pending`, `whats-next`, and the QA chain track findings through the
`note` skill. The repo needs `.claude/note.json` and registration in the
vault's `meta/note-areas.md` (two-key handshake; see the note skill).

## Handling a repo difference

When a shared body reads differently in a new repo, climb this ladder — take
the **highest** rung that works, and never fork the skill:

1. **Find one expression correct everywhere** (e.g. the portable pathspec).
2. **Delete it** — a difference is usually a bug in both, not a variation.
3. **Declare a shape key** — a commitment every adopter keeps forever, so
   third choice, not first.
4. **Rewrite the prose to name the role, not the instance.** Vocabulary is
   never a knob.
5. **Accept the skill does not move** — it was repo-specific all along.

## Onboarding checklist

1. Provide the repo-side artifacts above (CLAUDE.md sections, understand
   bundle + shape keys, worker-protocol, hooks, output-judge agent, docs).
2. `python3 .claude/skills/understand/load.py <repo-root> --check` → zero
   errors.
3. Symlink the shared skills and agents from this repo.
4. Delete the repo's superseded local copies (and any retired skills this
   repo has removed — check git history here, not the repo's).
5. Run one architecture-posture skill (`/whats-next`) and one sprint skill
   end-to-end; anything that reads wrong is a defect in this contract or a
   missing repo artifact — fix it there, never by editing a shared body for
   one repo.
