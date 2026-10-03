# Leo's Claude Starter

The skills, agents, hooks, and conventions I use to build software with Claude Code
across several related repos.

## Important

This is how my process evolved over time to plan and write code with CC.

What this does:

* Gives a set of repos one shared copy of the skills and agents that run the work.
* Keeps planning and tracking out of the repo, so it doesn't pollute context.
* Uses what works for me in CC.
* Hopefully, helps people get started a little quicker.

What this does not:

* Revolutionize anything. (Why does everyone "revolutionize". Let's be real, here.)
* Implement known best practices. (Do those exist?)
* Prevent you from defining your own processes or modifying these ones.

People ask how to get started and this is a resource for them. That's it. I highly
encourage everyone to learn by doing. Trial and error is unavoidable.

## How it's used

This started as a template you copy into a new project. It isn't that anymore. Repos
**adopt** the starter: they symlink its skills and agents rather than copying them,
so a fix lands everywhere at once and nothing drifts. Each repo supplies the
repo-specific parts (principles, context bundles, its own agents), and the shared bodies
read them.

There are two ways to adopt it.

| Tier | What you get | Good for |
|---|---|---|
| **Infrastructure** | `note`, `understand`, `consult`, `session`, `remote-session` | Any repo. Small projects, docs repos, a repo you only touch now and then. |
| **Full workflow** | The architecture and sprint skills, the shared agents, the worker protocol, and the hooks | Repos with real code under active development. |

The infrastructure skills are symlinked into `~/.claude/skills/` once per machine. The
full-workflow skills and agents are symlinked into each repo's `.claude/`.

**[`ADOPTION.md`](ADOPTION.md) is the contract** for the full workflow: what the starter
provides, what the repo must provide, and the `load.py --check` gate that verifies the
two line up. If adopting a repo needs something that document doesn't say, fix the
document.

## Getting started

1. **Clone the starter next to your project.** The symlinks are relative and assume the
   two checkouts share a parent directory.
   ```bash
   cd ~/projects
   git clone https://github.com/leogodin217/leos_claude_starter.git
   ```
2. **Link `/get-started` into your project.**
   ```bash
   cd ~/projects/my_project
   mkdir -p .claude/skills
   ln -s ../../../leos_claude_starter/.claude/skills/get-started .claude/skills/get-started
   ```
3. **Restart Claude Code** in your project so it picks up the new skill.
4. **Run `/get-started`.** It asks which tier you want and how you want to track work,
   then sets up the rest: symlinks, bindings, `CLAUDE.md`, and context bundles.

## Keep tracking out of the repo

Findings, plans, research, decisions, and open questions live **outside the codebase**.
When they live in the repo, every code search and doc load drags in half-finished
ideas, old plans, and resolved bugs. The repo holds code and the docs that describe it.
Everything in flight lives elsewhere.

I use an [Obsidian](https://obsidian.md) vault through the `/note` skill. **Obsidian isn't
required.** The principle is what matters. A folder of markdown files outside the repo
with a small CLI, GitHub issues, Linear, whatever you like. Ask Claude to build the one
that fits how you work.

One caveat if you swap it out: `arch-design`, `arch-review`, `fold-pending`, and
`whats-next` call `note/cli.py` directly. A replacement should support the same commands
(`new`, `list`, `status`, `set`, `path`), or those skills need editing.

### The `/note` setup

The vault holds seven note types, each with its own lifecycle:

| Type | For | Statuses |
|---|---|---|
| `finding` | Bugs, gaps, nits, design problems found in QA or review | open → resolved / deferred |
| `feature` | Things to build | proposed → scheduled → implemented |
| `plan` | Multi-step work, often spanning repos | active → complete / wont-do |
| `decision` | Choices that bind future work | active → superseded |
| `research` | Investigations | in-progress → complete / abandoned |
| `question` | Open questions, optionally blocking | open → answered |
| `retro` | Sprint retrospectives | — |

Some things that make it work:

* **One vault, many repos.** Each repo commits a pointer (`.claude/note.json`) naming
  its vault and its own name. The vault keeps a registry of admitted repos and their
  areas. Every note is stamped with the repo that created it, and links resolve across
  the whole vault.
* **Plans coordinate across repos.** A plan lists the repos it touches and holds the
  build order. A `planning-<slug>` tag groups everything in one workstream.
* **Status is a field, not a folder.** Notes don't move as they change state, so links
  never break.
* **Content flows one way.** If a note becomes load-bearing for code, its content moves
  into the repo's docs. The repo never points back into the vault for something it needs.

Setup details are in [`.claude/skills/note/SKILL.md`](.claude/skills/note/SKILL.md).

## Workflow

```
/understand <area>   →  Load context for the work at hand (start of most sessions)
/arch-design         →  Write a pending design doc for a change
/arch-review         →  Review it until an implementer could build it without guessing
/create-sprint       →  Turn the design into a sprint spec and execution plan
/eval-sprint         →  Adversarial check of the spec (optional, for big sprints)
/implement-sprint    →  Execute the plan in a worktree, phase by phase
/review-sprint       →  Mechanical audit of what shipped against the spec
/fold-pending        →  Fold the shipped design into the canonical docs; resolve notes
/whats-next          →  Diagnose project state and recommend a next step
/audit-docs          →  Periodic documentation accuracy pass
```

`arch-review` gets the most use of anything here. Most of the value is in getting the
design right before a sprint starts. I run it several times on a design, often in
fresh sessions.

### Feature lifecycle

```
1. NEED
   └── A finding, feature, or plan in the vault (or just an idea)

2. DESIGN (/arch-design, /arch-review)
   ├── docs/architecture/pending/<name>.md
   └── Binding decisions and forward notes from the vault are checked

3. SPRINT PLANNING (/create-sprint, optionally /eval-sprint)
   └── docs/sprints/<name>/spec.md + state.yaml

4. IMPLEMENTATION (/implement-sprint)
   ├── Runs in a worktree, fresh context per phase
   └── Each phase: implement → gate → review → fix → commit

5. REVIEW (/review-sprint)
   ├── Verify against the spec
   └── Findings go in the sprint's review.md; only ones you choose to defer
       become vault notes

6. FOLD (/fold-pending)
   ├── Redistribute the pending doc into the canonical architecture docs
   ├── Delete the pending doc
   └── Resolve the vault notes the sprint closed
```

## Sessions

* **Start with `/understand <area>`.** Each repo defines context bundles in
  `.claude/understand/`: which docs (or doc sections) to load for a kind of work. Run it
  with no argument to list the areas. This replaced hand-maintained "role" prompts.
* **Custom system prompt.** Each repo has `.claude/custom-system-prompt.md`: an intro
  line naming the repo, plus the shared base from `.claude/system-prompt-base.md`. I
  launch with an alias:
  ```bash
  alias claude_custom='claude --dangerously-skip-permissions --system-prompt-file .claude/custom-system-prompt.md'
  ```
* **Worker protocol.** A SubagentStart hook injects `.claude/worker-protocol.md` into
  every subagent, so agents get the repo's working rules without carrying them in their
  own definitions.
* **Hooks** enforce the habits I kept having to repeat: outline a markdown file before
  reading it (`mdnav_first`), use LSP navigation before grep (`grep_guard`), only the
  orchestrator commits (`git_commit_guard`), and clarifying questions get asked in chat
  rather than through the multiple-choice widget (`deny_question_tool`).
* **Remote sessions.** `/remote-session` spawns a named Claude session in tmux,
  registered with `/remote-control`, so I can drive it from claude.ai on my phone.
  `/remote-sprint` does the same for a sprint running in a worktree.

## Working across repos

`/consult <repo> <question>` spawns a read-only advisor grounded in another repo and
relays its answer. Use it when a question depends on another repo's intent, contracts,
or roadmap and you don't want to load its code into your own session.

* A machine registry (`~/.config/consult.json`) maps repo names to checkout paths, with
  a one-line description of each and a list of the contracts between them.
* A repo can commit `.claude/consult.json` naming a startup skill, so its advisor loads
  the right context first (for example `/understand architecture`).

Once you have more than a few repos, it helps to give one repo the job of holding the
fleet map: which repos exist, the contracts between them, and how the project got here.
It generates the consult registry and answers the "which repo should own this?"
questions. It's optional, but it's the first thing I consult when I'm not sure where
something belongs.

## Agents vs Skills

| Type | Purpose | Location |
|------|---------|----------|
| **Agents** | Workers with specific expertise | `.claude/agents/` |
| **Skills** | Processes that orchestrate work | `.claude/skills/` |

Agents do focused work. Skills define workflows that dispatch agents.

Shared agents: `architect`, `implementer`, `reviewer`, `test-reviewer`, `doc-auditor`.
Their bodies carry no repo-specific content. Repo principles reach them through the
worker protocol and the repo's `CLAUDE.md`. Each repo also has its own **output-judge**
agent that judges what the program produces rather than its code.

## Directory structure

What a full-workflow repo looks like:

```
project/
├── CLAUDE.md                     # Principles, invariants, anti-patterns, phase status
├── docs/
│   ├── CAPABILITIES.md           # What the system does (status tracking)
│   ├── PROCESS.md                # Development process, documentation lifecycle
│   ├── architecture/
│   │   ├── README.md             # Index, reading order
│   │   ├── {subsystem}.md        # Canonical design docs
│   │   └── pending/              # Designs not yet shipped
│   └── sprints/
│       └── {sprint-name}/        # spec.md, state.yaml, demos/
├── tools/hooks/                  # Symlinks to the starter's hooks
├── .claude/
│   ├── worker-protocol.md        # Starter base + repo sections (injected into subagents)
│   ├── custom-system-prompt.md   # Intro line + starter base
│   ├── settings.json             # Hook registration
│   ├── hooks-config.json         # Per-repo hook knobs
│   ├── note.json                 # Vault binding
│   ├── consult.json              # Consult binding (optional)
│   ├── understand/               # Context bundles + repo-shape keys
│   ├── agents/                   # Shared agents (symlinks) + the repo's own
│   └── skills/                   # Shared skills (symlinks) + the repo's own
└── src/
```

An infrastructure-only repo needs just `.claude/note.json`, and optionally
`.claude/consult.json` and an `understand/` bundle.

## Session Analysis

`/session` analyzes Claude Code sessions, running or past, so you can improve your
skills and processes over time. Sessions get auto titles, and `/rename` gives one a
name you choose. You can refer to a session by title, ID prefix, the PR it opened
(`pr:91`), or `self` for the one you're in.

**Things you can ask:**
- "What sessions are running right now?" / "List recent sessions for this project"
- "Summarize the last session that started with `/implement-sprint`"
- "Summarize the session that opened PR 91": cost, active time, prompts, recap
- "Show me the subagents in that sprint run": type, task, time, tokens, peak context
- "Where did the agents struggle or deviate from the spec?"
- "Where did the context go?": growth curve, repeated reads, specs read by several
  agents, oversized tool results, turns spent on late notifications
- "Which session changed `compile/scenario.py`?"
- "Compare these two sprint runs"

These are all analyzer commands, so the answers are consistent from run to run. The
signals and efficiency audits point you at the parts of the transcript worth reading.
For "why did this go wrong?", Claude still reads those parts and reasons about them.

**We all know Claude likes to self flagellate and tell us everything it did wrong. This
is not productive when improving processes. I found telling Claude that "I choose to
blame processes not people or LLMs." steers the conversation in a far more productive
direction.**

## Using CCLSP

[CCLSP](https://github.com/ktnyt/cclsp) makes finding and reading code faster and more
token efficient. The hooks and worker protocol assume it. I highly recommend installing
it. If you don't want to, ask Claude to remove the instructions and the `grep_guard`
hook.

## Philosophy

### Principles Are Guardrails

Without explicit principles, LLMs optimize locally and lose coherence across a project.
Principles enable autonomous decision-making within bounds.

Good principles:
- Are specific enough to apply ("fail fast" not "be robust")
- Sometimes conflict (forces explicit tradeoffs)
- Include concrete examples and counter-examples

Shared skills cite principles **by name, never by number**. Numbers are local to a repo
and collide across repos.

### Fresh Context per Phase

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
- Gets folded and pruned after implementation (that's what `/fold-pending` is for)

### Share, Don't Fork

When a shared skill reads wrong in one repo, fix the skill or the repo, never fork it.
A skill that quietly does less in one repo is the failure this setup exists to prevent.
`ADOPTION.md` has the ladder for handling repo differences.

## Customization

See [`CUSTOMIZATION.md`](CUSTOMIZATION.md) for writing principles, invariants,
anti-patterns, and architecture docs, and [`ADOPTION.md`](ADOPTION.md) for adopting the
shared skills and agents.
