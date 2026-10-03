#!/usr/bin/env python3
"""Claude Code session analyzer: find, summarize, and audit session transcripts.

SESSION arguments accept a .jsonl path (subagent transcripts too), `self` (the
calling session, via $CLAUDE_CODE_SESSION_ID), a session UUID or unique prefix,
`pr:N` / `pr:owner/repo#N` (session linked to that PR), or a title (/rename
name or auto title). Session commands also take --search KEYWORD --index N.

Run `analyzer.py <command> -h` for a command's options.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
REGISTRY_DIR = CLAUDE_DIR / "sessions"

KNOWN_TYPES = {
    "user", "assistant", "attachment", "system", "progress", "summary",
    "queue-operation", "file-history-snapshot", "file-history-delta",
    "custom-title", "ai-title", "agent-name", "last-prompt", "mode",
    "permission-mode", "atis-latch", "pr-link", "bridge-session", "cost-state",
}

# Built-ins that configure a session rather than describe its work; never used as its label.
CONFIG_COMMANDS = {
    "/add-dir", "/agents", "/bashes", "/btw", "/clear", "/compact", "/config", "/context",
    "/copy", "/cost", "/doctor", "/effort", "/exit", "/export", "/fast", "/help", "/hooks",
    "/ide", "/login", "/logout", "/mcp", "/memory", "/model", "/output-style",
    "/permissions", "/plugin", "/remote-control", "/rename", "/resume", "/rewind",
    "/status", "/statusline", "/tasks", "/terminal-setup", "/theme", "/usage", "/vim",
}

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Bash commands that look like they modify files (heuristic; used with a filename match).
BASH_WRITE_RE = re.compile(
    r"sed\s+-i|perl\s+-\w*i|\btee\b|\b(?:git\s+)?(?:mv|cp|rm)\s|(?<![\d&])>>?\s*(?!&)[^\s&|]"
    r"|open\([^)]*['\"][wa]|write_text|apply_patch|\bpatch\b"
)

# Whole-word matches; a trailing * matches as a prefix.
SIGNALS = {
    "backtracking": ["actually", "wait", "wrong", "mistake*", "let me reconsider", "should have"],
    "spec-deviation": ["spec says", "not what the spec", "different approach", "intentional*", "skip*", "omit*"],
    "rework": ["revert*", "undo", "let me try", "didn't work", "failed"],
    "workaround": ["circular", "lazy import", "workaround*", "hack*"],
    "scope-creep": ["refactor*", "restructur*", "redesign*", "not implement*"],
}

NOISE_RE = re.compile(
    r"<(system-reminder|local-command-caveat|local-command-stdout|local-command-stderr|"
    r"task-notification|command-message)>.*?</\1>",
    re.S,
)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


# --- Formatting ---

def fmt_bytes(b):
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.2f} MB"


def fmt_dur(seconds):
    seconds = int(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def fmt_cost(cost_state):
    return f"${cost_state['totalCostUSD']:.2f}" if cost_state else ""


def fmt_when(ts, with_date=True):
    if ts is None:
        return "?"
    return ts.astimezone().strftime("%Y-%m-%d %H:%M" if with_date else "%H:%M:%S")


def one_line(text, n):
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    return "…" + text[-(n - 1):] if text.startswith("/") else text[: n - 1] + "…"  # paths keep their tail


# --- Entry parsing ---

def load(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(e, dict):
                entries.append(e)
    return entries


def parse_ts(val):
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000 if val > 1e12 else val, tz=timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def content_of(e):
    msg = e.get("message")
    return msg.get("content", []) if isinstance(msg, dict) else []


def extract_text(content, thinking=False):
    if isinstance(content, str):
        return content
    parts = []
    for b in content if isinstance(content, list) else []:
        if isinstance(b, str):
            parts.append(b)
        elif isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
        elif thinking and isinstance(b, dict) and b.get("type") == "thinking":
            parts.append(b.get("thinking", ""))
    return "\n".join(parts)


def blocks(content, kind):
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind] if isinstance(content, list) else []


def clean_prompt(text):
    m = re.search(r"<command-name>(/[^<]+)</command-name>", text)
    if m:
        a = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        return f"{m.group(1).strip()} {a.group(1).strip() if a else ''}".strip()
    text = NOISE_RE.sub("", text)
    return re.sub(r"<[^>]+>", "", text).strip()


def human_prompt(e):
    """Text of a prompt a person typed (or a slash command they ran), else None.

    Current versions mark the source in `origin.kind`; older transcripts lack it
    and fall back to filtering out tool results, meta entries, and notifications.
    """
    if e.get("type") != "user" or e.get("isMeta"):
        return None
    content = content_of(e)
    if blocks(content, "tool_result"):
        return None
    origin = e.get("origin")
    if isinstance(origin, dict) and origin.get("kind") != "human":
        return None
    text = extract_text(content)
    if text.lstrip().startswith("<task-notification"):
        return None
    clean = clean_prompt(text)
    if not clean or clean.startswith("Caveat:"):
        return None
    return clean


def is_notification(e):
    if e.get("type") != "user":
        return False
    origin = e.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "task-notification"
    return extract_text(content_of(e)).lstrip().startswith("<task-notification")


def tool_target(tu):
    inp = tu.get("input") or {}
    if "pattern" in inp:
        return f"{inp.get('path', '.')} :: {inp['pattern']}"
    if "skill" in inp:
        return f"skill:{inp['skill']}"
    if tu.get("name") == "Agent" and "description" in inp:
        return f"{inp.get('subagent_type', 'general-purpose')}: {inp['description']}"
    for key in ("command", "file_path", "notebook_path", "query", "url", "prompt"):
        if isinstance(inp.get(key), str):
            return one_line(inp[key], 120)
    for k, v in inp.items():
        if isinstance(v, str) and v:
            return f"{k}={one_line(v, 80)}"
    return "(no target)"


def sizeof(obj):
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


# --- Transcript analysis ---

def analyze(path):
    """Full pass over one transcript (main session or subagent)."""
    s = {
        "path": str(path), "size": os.path.getsize(path), "first_ts": None, "last_ts": None,
        "prompts": [], "command": "", "custom_title": "", "ai_title": "", "agent_name": "",
        "models": Counter(), "version": "", "cwd": "", "branch": "",
        "tokens": Counter(), "tokens_by_model": defaultdict(Counter),
        "calls": [], "tools": [], "types": Counter(), "skills": [], "recaps": [],
        "active_s": 0, "cost": None, "prs": {},
    }
    seen_msgs = set()
    tools_by_id = {}
    driver = "human"
    pending = []  # tool results that arrived since the previous API call
    turn_start = turn_last = prev_last = None  # active time: each prompt to its turn's last user/assistant entry

    for e in load(path):
        t = e.get("type", "(none)")
        s["types"][t] += 1
        ts = parse_ts(e.get("timestamp"))
        if ts:
            s["first_ts"] = s["first_ts"] or ts
            s["last_ts"] = ts
        if ts and t in ("user", "assistant"):
            prev_last, turn_last = turn_last, ts
        s["version"] = e.get("version") or s["version"]
        s["cwd"] = e.get("cwd") or s["cwd"]
        s["branch"] = e.get("gitBranch") or s["branch"]

        if t == "custom-title":
            s["custom_title"] = e.get("customTitle", "")
        elif t == "ai-title":
            s["ai_title"] = e.get("aiTitle", "")
        elif t == "agent-name":
            s["agent_name"] = e.get("agentName", "")
        elif t == "pr-link":
            s["prs"][e.get("prUrl")] = e.get("prNumber")
        elif t == "cost-state":
            s["cost"] = e
        elif t == "system" and e.get("subtype") == "away_summary":
            s["recaps"].append((ts, e.get("content", "")))
        elif t == "user":
            prompt = human_prompt(e)
            if prompt:
                s["prompts"].append((ts, prompt))
                driver = "human"
                if turn_start and prev_last:
                    s["active_s"] += (prev_last - turn_start).total_seconds()
                turn_start = ts
                cmd = prompt.split()[0]
                if cmd.startswith("/") and cmd not in CONFIG_COMMANDS and not s["command"]:
                    s["command"] = cmd
            elif is_notification(e):
                driver = "notification"
            for tr in blocks(content_of(e), "tool_result"):
                tool = tools_by_id.get(tr.get("tool_use_id"))
                if tool:
                    tool["result_bytes"] = sizeof(tr.get("content", ""))
                    pending.append(tool)
        elif t == "assistant":
            msg = e.get("message") or {}
            model = msg.get("model", "")
            usage = msg.get("usage")
            # Each content block is its own entry with the response's usage repeated; count it once.
            key = msg.get("id") or e.get("requestId") or e.get("uuid")
            if usage and key not in seen_msgs:
                seen_msgs.add(key)
                u = {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "cache_read": usage.get("cache_read_input_tokens", 0),
                    "cache_create": usage.get("cache_creation_input_tokens", 0),
                }
                s["tokens"].update(u)
                if model and model != "<synthetic>":
                    s["models"][model] += 1
                    s["tokens_by_model"][model].update(u)
                s["calls"].append({
                    "ts": ts, "context": u["input"] + u["cache_read"] + u["cache_create"],
                    "output": u["output"], "driver": driver, "after": pending,
                })
                pending = []
            for tu in blocks(msg.get("content", []), "tool_use"):
                rec = {
                    "id": tu.get("id"), "name": tu.get("name", "?"), "target": tool_target(tu),
                    "input": tu.get("input") or {}, "ts": ts, "result_bytes": 0,
                }
                s["tools"].append(rec)
                tools_by_id[rec["id"]] = rec
                if rec["name"] == "Skill":
                    s["skills"].append(rec["input"].get("skill", ""))
    if turn_start and turn_last:
        s["active_s"] += (turn_last - turn_start).total_seconds()
    return s


MARKERS = ('"type":"custom-title"', '"type":"ai-title"', '"type":"agent-name"',
           '"type":"pr-link"', '"type":"cost-state"')


def peek(path):
    """Cheap pass for listings: titles, label, PRs, cost, project. Parses only lines it needs."""
    info = {"custom_title": "", "ai_title": "", "agent_name": "", "command": "", "prompt": "",
            "prs": {}, "cost": None, "cwd": ""}
    with open(path, encoding="utf-8") as f:
        for line in f:
            is_user = '"type":"user"' in line
            wanted = (
                any(m in line for m in MARKERS)
                or not info["cwd"]
                or (is_user and not info["prompt"])
                or (is_user and not info["command"] and "<command-name>" in line)
            )
            if not wanted:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = e.get("type")
            info["cwd"] = info["cwd"] or e.get("cwd", "")
            if t == "custom-title":
                info["custom_title"] = e.get("customTitle", "")
            elif t == "ai-title":
                info["ai_title"] = e.get("aiTitle", "")
            elif t == "agent-name":
                info["agent_name"] = e.get("agentName", "")
            elif t == "pr-link":
                info["prs"][e.get("prUrl")] = e.get("prNumber")
            elif t == "cost-state":
                info["cost"] = e
            elif t == "user":
                prompt = human_prompt(e)
                cmd = prompt.split()[0] if prompt else ""
                if prompt and cmd not in CONFIG_COMMANDS:
                    info["prompt"] = info["prompt"] or prompt
                    if cmd.startswith("/") and not info["command"]:
                        info["command"] = cmd
    return info


def titles(info):
    return [t for t in (info["custom_title"], info["agent_name"], info["ai_title"]) if t]


def label(info):
    """Display name: /rename title, else auto title, else first real command, else first prompt."""
    name = (titles(info) or [""])[0]
    if name and info["command"]:
        return f"{name} ({info['command']})"
    return name or info["command"] or one_line(info["prompt"], 60)


def subagents(path):
    """Subagent transcripts of a session in start order, labeled from their .meta.json."""
    d = Path(path).with_suffix("") / "subagents"
    out = []
    for f in sorted(d.glob("*.jsonl")) if d.is_dir() else []:
        meta = {}
        meta_path = f.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        out.append({
            "path": f,
            "type": meta.get("agentType", "?"),
            "description": meta.get("description", ""),
            "label": f"{meta.get('agentType', '?')}: {meta.get('description', '')}".rstrip(": "),
            "start": json.loads(f.open(encoding="utf-8").readline() or "{}").get("timestamp", ""),
        })
    return sorted(out, key=lambda a: a["start"])


# --- Session discovery and resolution ---

def project_slug(project):
    if project == "." or "/" in project:
        return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(project))
    return project


def session_files(project=None):
    if project:
        dirs = [PROJECTS_DIR / project_slug(project)]
    else:
        dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]
    files = [f for d in dirs if d.is_dir() for f in d.glob("*.jsonl")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def windowed(files, args):
    return files if args.all or args.recent is None else files[: args.recent]


def project_name(path, info):
    return os.path.basename(info["cwd"]) if info["cwd"] else Path(path).parent.name


def mtime(path):
    return datetime.fromtimestamp(Path(path).stat().st_mtime, tz=timezone.utc)


def print_session_rows(rows, extra=None):
    """rows: [(path, info)]. `extra(i)` returns lines printed under row i."""
    print(f"{'#':<3} {'Last active':<16} {'Size':>9} {'Cost':>7}  {'Project':<24} {'ID':<8}  Label")
    for i, (path, info) in enumerate(rows):
        prs = " ".join(f"PR#{n}" for n in info["prs"].values())
        print(f"{i:<3} {fmt_when(mtime(path)):<16} {fmt_bytes(Path(path).stat().st_size):>9} "
              f"{fmt_cost(info['cost']):>7}  {one_line(project_name(path, info), 24):<24} "
              f"{Path(path).stem[:8]:<8}  {label(info) or '(empty)'}{'  ' + prs if prs else ''}")
        for line in extra(i) if extra else []:
            print(line)


def pick_one(matches, what):
    if len(matches) == 1:
        return str(matches[0][0])
    if not matches:
        die(f"No session matches {what}.")
    print(f"Multiple sessions match {what}:", file=sys.stderr)
    for path, info in matches[:20]:
        print(f"  {Path(path).stem[:8]}  {fmt_when(mtime(path))}  {label(info)}  {path}", file=sys.stderr)
    die("Use a longer ID prefix or the full path.")


def resolve(session, args):
    if getattr(args, "search", None) is not None:
        if args.index is None:
            die("--search needs --index N (see `search` output).")
        matches = run_search(args.search, windowed(session_files(args.project), args))
        if not 0 <= args.index < len(matches):
            die(f"Index {args.index} out of range ({len(matches)} matches).")
        return matches[args.index]["path"]
    if session is None:
        die("No session given. Pass a path, `self`, UUID/prefix, pr:N, title, or --search KW --index N.")

    if session == "self":
        session = os.environ.get("CLAUDE_CODE_SESSION_ID") or die(
            "`self` needs $CLAUDE_CODE_SESSION_ID (only set inside a Claude Code session).")
    if os.path.isfile(session):
        return session

    m = re.fullmatch(r"pr:(?:([\w.-]+/[\w.-]+)#)?(\d+)", session)
    if m:
        repo, number = m.group(1), int(m.group(2))
        hits = []
        for f in session_files():
            info = peek(f)
            if any(n == number and (not repo or f"/{repo}/pull/" in url) for url, n in info["prs"].items()):
                hits.append((f, info))
        return pick_one(hits, f"PR {session[3:]}")

    if re.fullmatch(r"[0-9a-f-]{4,36}", session):
        hits = sorted(PROJECTS_DIR.glob(f"*/{session}*.jsonl"))
        if hits:
            return pick_one([(f, peek(f)) for f in hits], f"ID {session}")

    needle = session.lower()
    exact, partial = [], []
    for f in session_files():
        info = peek(f)
        names = [t.lower() for t in titles(info)]
        if needle in names:
            exact.append((f, info))
        elif any(needle in n for n in names):
            partial.append((f, info))
    return pick_one(exact or partial, f'"{session}"')


# --- Commands: finding sessions ---

def registry_alive(d):
    pid = d.get("pid")
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        # Field 22 (starttime) guards against a reused pid; fields after the ")" start at 3.
        start = stat.read_text().rsplit(")", 1)[1].split()[19]
        return d.get("procStart") in (None, start)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def cmd_live(args):
    me = os.environ.get("CLAUDE_CODE_SESSION_ID")
    rows = []
    for f in REGISTRY_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if registry_alive(d):
            rows.append(d)
    if not rows:
        print("No running Claude Code sessions.")
        return
    rows.sort(key=lambda d: d.get("updatedAt", 0), reverse=True)
    now = datetime.now(timezone.utc)
    print(f"{'PID':<8} {'Status':<14} {'Name':<28} {'ID':<8}  {'Cwd':<40} Label")
    for d in rows:
        since = parse_ts(d.get("statusUpdatedAt"))
        status = d.get("status", "?") + (f" {fmt_dur((now - since).total_seconds())}" if since else "")
        if d.get("kind") not in (None, "interactive"):
            status += f" ({d['kind']})"
        hits = list(PROJECTS_DIR.glob(f"*/{d.get('sessionId')}.jsonl"))
        lbl = label(peek(hits[0])) if hits else ""
        mark = "  <- self" if d.get("sessionId") == me else ""
        print(f"{d.get('pid', '?'):<8} {status:<14} {one_line(d.get('name', ''), 28):<28} "
              f"{d.get('sessionId', '')[:8]:<8}  {one_line(d.get('cwd', ''), 40):<40} {lbl}{mark}")


def cmd_list(args):
    rows = [(f, peek(f)) for f in windowed(session_files(args.project), args)]
    shown = [(f, i) for f, i in rows if label(i)]
    if not shown:
        print("No sessions found.")
        return
    print_session_rows(shown)
    hidden = len(rows) - len(shown)
    print(f"\n{len(shown)} sessions" + (f" ({hidden} empty stubs hidden)" if hidden else "") +
          ". Pass the ID to summary/agents/efficiency/etc.")


def cmd_find(args):
    needle = args.name.lower()
    matches = []
    for f in windowed(session_files(args.project), args):
        info = peek(f)
        if any(needle in t.lower() for t in titles(info)):
            matches.append((f, info))
    if not matches:
        print(f'No session titled like "{args.name}" (checks /rename names and auto titles).')
        return
    print_session_rows(matches[:20])
    if len(matches) == 1:
        print(f"\nResume: claude --resume {Path(matches[0][0]).stem}")


def find_snippets(text, keyword, limit=3, ctx=40):
    out, low, kw, start = [], text.lower(), keyword.lower(), 0
    while len(out) < limit:
        pos = low.find(kw, start)
        if pos == -1:
            break
        a, b = max(0, pos - ctx), min(len(text), pos + len(kw) + ctx)
        snippet = text[a:b].replace("\\n", " ").replace('\\"', '"')  # raw JSONL escapes
        out.append(("..." if a else "") + one_line(snippet, 400) + ("..." if b < len(text) else ""))
        start = pos + len(kw)
    return out


def run_search(keyword, files):
    """Sessions containing keyword in the main JSONL, externalized tool results, or subagents."""
    kw = keyword.lower()
    matches = []
    for f in files:
        sources = [("", f.read_text(encoding="utf-8", errors="replace"))]
        results_dir = f.with_suffix("") / "tool-results"
        if results_dir.is_dir():
            sources += [("[tool-result]", r.read_text(encoding="utf-8", errors="replace"))
                        for r in results_dir.iterdir() if r.is_file()]
        sources += [(f"[{a['type']}]", a["path"].read_text(encoding="utf-8", errors="replace"))
                    for a in subagents(f)]
        hits, snippets = 0, []
        for tag, text in sources:
            n = text.lower().count(kw)
            if n:
                hits += n
                snippets += [(tag, s) for s in find_snippets(text, keyword)]
        if hits:
            matches.append({"path": str(f), "hits": hits, "snippets": snippets[:3]})
    matches.sort(key=lambda m: m["hits"], reverse=True)
    return matches


def cmd_search(args):
    matches = run_search(args.keyword, windowed(session_files(args.project), args))
    if not matches:
        print(f'No sessions contain "{args.keyword}".')
        return
    if args.index is not None:
        if not 0 <= args.index < len(matches):
            die(f"Index {args.index} out of range ({len(matches)} matches).")
        print(matches[args.index]["path"])
        return
    top = matches[:20]
    print(f'Sessions containing "{args.keyword}" ({len(matches)}, most hits first):\n')
    print_session_rows(
        [(m["path"], peek(m["path"])) for m in top],
        extra=lambda i: [f"      {top[i]['hits']} hits"] +
                        [f"      {tag} {snip}".rstrip() for tag, snip in top[i]["snippets"]],
    )


def cmd_provenance(args):
    target = os.path.abspath(args.file) if os.path.exists(args.file) else None
    needle = os.path.basename(args.file.rstrip("/"))

    def matches(fp):
        return fp == target if target else args.file in fp

    rows = []
    for f in windowed(session_files(args.project), args):
        transcripts = [(f, "main")] + [(a["path"], a["label"]) for a in subagents(f)]
        for tpath, who in transcripts:
            with open(tpath, encoding="utf-8") as fh:
                for line in fh:
                    if needle not in line or '"tool_use"' not in line:
                        continue
                    e = json.loads(line)
                    for tu in blocks(content_of(e), "tool_use"):
                        inp = tu.get("input") or {}
                        fp = inp.get("file_path") or inp.get("notebook_path") or ""
                        if tu.get("name") in WRITE_TOOLS and matches(fp):
                            detail = inp.get("new_string") or inp.get("content") or inp.get("new_source") or ""
                            rows.append((parse_ts(e.get("timestamp")), f, who, tu["name"], fp, detail))
                        cmd = inp.get("command") or ""
                        if tu.get("name") == "Bash" and needle in cmd and BASH_WRITE_RE.search(cmd):
                            rows.append((parse_ts(e.get("timestamp")), f, who, "Bash?", "", cmd))
    if not rows:
        print(f"No writes of {args.file} found.")
        return
    rows.sort(key=lambda r: r[0] or datetime.min.replace(tzinfo=timezone.utc))
    labels = {}
    for ts, f, who, tool, fp, detail in rows:
        if f not in labels:
            labels[f] = label(peek(f))
        print(f"{fmt_when(ts)}  {Path(f).stem[:8]}  {one_line(labels[f], 40):<40}  {one_line(who, 30):<30}  "
              f"{tool:<6} {fp if not target else ''}")
        print(f"      {one_line(detail, 110)}")
    print(f"\n{len(rows)} writes across {len(labels)} sessions. `Bash?` rows are commands naming the file "
          f"that look like writes (heuristic).")


# --- Commands: one session ---

def peak(s):
    return max((c["context"] for c in s["calls"]), default=0)


def wall(s):
    return (s["last_ts"] - s["first_ts"]).total_seconds() if s["first_ts"] else 0


def print_tokens(tokens, indent="  "):
    for k, name in (("input", "Input"), ("output", "Output"), ("cache_read", "Cache read"),
                    ("cache_create", "Cache create")):
        print(f"{indent}{name + ':':<14}{tokens[k]:>14,}")


def cmd_summary(args):
    path = resolve(args.session, args)
    s = analyze(path)
    print("=" * 70)
    print(f"SESSION {Path(path).stem}")
    print("=" * 70)
    first = next((p for _, p in s["prompts"] if p.split()[0] not in CONFIG_COMMANDS), "")
    print(f"  Label:    {label({**s, 'prompt': first}) or '(none)'}")
    print(f"  Path:     {path}  ({fmt_bytes(s['size'])})")
    print(f"  Cwd:      {s['cwd']}  [{s['branch']}]")
    print(f"  Models:   {', '.join(s['models']) or '?'}   Version: {s['version'] or '?'}")
    print(f"  Started:  {fmt_when(s['first_ts'])}   Last: {fmt_when(s['last_ts'])}")
    print(f"  Time:     {fmt_dur(wall(s))} wall-clock, {fmt_dur(s['active_s'])} active (prompt to end of each turn)")
    if s["cost"]:
        print(f"  Cost:     {fmt_cost(s['cost'])} (session total incl. subagents)")
    for url in s["prs"]:
        print(f"  PR:       {url}")

    print(f"\n--- Tokens ({len(s['calls'])} API calls, peak context {peak(s):,}) ---")
    print_tokens(s["tokens"])
    if len(s["tokens_by_model"]) > 1:
        for model, t in sorted(s["tokens_by_model"].items()):
            print(f"  {model}:")
            print_tokens(t, indent="    ")

    counts = Counter(t["name"] for t in s["tools"])
    result_bytes = Counter()
    for t in s["tools"]:
        result_bytes[t["name"]] += t["result_bytes"]
    print(f"\n--- Tools ({len(s['tools'])} calls) ---")
    for name, c in counts.most_common():
        print(f"  {name:<36} {c:>4}x  {fmt_bytes(result_bytes[name]):>10} results")
    if s["skills"]:
        print(f"\n--- Skills invoked: {', '.join('/' + k for k in s['skills'])}")
    agents = subagents(path)
    if agents:
        print(f"\n--- Subagents: {len(agents)} (`agents {Path(path).stem[:8]}` for the table) ---")

    print(f"\n--- Human prompts ({len(s['prompts'])}) ---")
    for ts, text in s["prompts"]:
        print(f"  [{fmt_when(ts, with_date=False)}] {one_line(text, 120)}")

    biggest = sorted(s["tools"], key=lambda t: t["result_bytes"], reverse=True)[:5]
    if biggest and biggest[0]["result_bytes"]:
        print("\n--- Largest tool results ---")
        for t in biggest:
            print(f"  {fmt_bytes(t['result_bytes']):>10}  {t['name']}: {one_line(t['target'], 70)}")

    if args.verbose:
        print("\n--- Entry types ---")
        for t, c in s["types"].most_common():
            print(f"  {t}: {c}{'   (unknown to analyzer)' if t not in KNOWN_TYPES else ''}")

    if s["recaps"]:
        ts, text = s["recaps"][-1]
        print(f"\n--- Latest recap ({fmt_when(ts)}) ---\n{text}")
    else:
        for e in reversed(load(path)):
            text = extract_text(content_of(e)) if e.get("type") == "assistant" else ""
            if text.strip():
                print(f"\n--- Last assistant message ---\n{text[:400]}" +
                      (f"\n... [{len(text)} chars]" if len(text) > 400 else ""))
                break

    if args.deep and agents:
        stats = [analyze(a["path"]) for a in agents]
        everything = [s] + stats
        total = Counter()
        for x in everything:
            total.update(x["tokens"])
        tools = Counter(t["name"] for x in everything for t in x["tools"])
        starts = [x["first_ts"] for x in everything if x["first_ts"]]
        ends = [x["last_ts"] for x in everything if x["last_ts"]]
        print(f"\n{'=' * 70}\nDEEP: session + {len(stats)} subagents, "
              f"{fmt_dur((max(ends) - min(starts)).total_seconds())} combined span\n{'=' * 70}")
        print_tokens(total)
        print(f"\n--- Tools across all transcripts ({sum(tools.values())} calls) ---")
        for name, c in tools.most_common():
            print(f"  {name:<36} {c:>4}x")
        print()
        print_agent_table(agents, stats)


def print_agent_table(agents, stats):
    print(f"{'#':<3} {'Start':<8} {'Agent':<46} {'Model':<18} {'Time':>7} {'Tools':>5} "
          f"{'Out tok':>9} {'Peak ctx':>9} {'Size':>9}  File")
    for n, (a, s) in enumerate(zip(agents, stats)):
        model = ",".join(m.replace("claude-", "") for m in s["models"])
        print(f"{n:<3} {fmt_when(s['first_ts'], with_date=False)[:8]:<8} {one_line(a['label'], 46):<46} "
              f"{one_line(model, 18):<18} {fmt_dur(wall(s)):>7} {len(s['tools']):>5} "
              f"{s['tokens']['output']:>9,} {peak(s):>9,} {fmt_bytes(s['size']):>9}  {a['path'].stem}")


def cmd_agents(args):
    path = resolve(args.session, args)
    agents = subagents(path)
    if not agents:
        print("No subagent transcripts for this session.")
        return
    print_agent_table(agents, [analyze(a["path"]) for a in agents])
    print(f"\nTranscripts: {Path(path).with_suffix('')}/subagents/<File>.jsonl "
          "(pass a path to summary/tools/signals/efficiency)")


def cmd_conversation(args):
    path = resolve(args.session, args)
    turn = 0
    for e in load(path):
        ts = fmt_when(parse_ts(e.get("timestamp")), with_date=False)
        prompt = human_prompt(e)
        if prompt:
            turn += 1
            print(f"\n{'─' * 60}\nUSER [{ts}] (turn {turn})\n{'─' * 60}")
            print(prompt[: args.max_chars] + (f"\n... [{len(prompt)} chars]" if len(prompt) > args.max_chars else ""))
        elif is_notification(e):
            text = extract_text(content_of(e))
            m = re.search(r"<summary>(.*?)</summary>", text, re.S)
            print(f"\n[notification {ts}] {one_line(m.group(1) if m else clean_prompt(text), 150)}")
        elif e.get("type") == "assistant":
            text = extract_text(content_of(e))
            if text.strip():
                print(f"\nASSISTANT [{ts}]")
                print(text[: args.max_chars] + (f"\n... [{len(text)} chars]" if len(text) > args.max_chars else ""))


def cmd_tools(args):
    s = analyze(resolve(args.session, args))
    print(f"Tool timeline ({len(s['tools'])} calls):\n")
    for t in s["tools"]:
        print(f"  [{fmt_when(t['ts'], with_date=False)}] {t['name']:<18} {fmt_bytes(t['result_bytes']):>9}  "
              f"{one_line(t['target'], 90)}")


def transcripts(path):
    """[(label, stats)] for a session and its subagents."""
    return [("main", analyze(path))] + [(a["label"], analyze(a["path"])) for a in subagents(path)]


def cmd_signals(args):
    path = resolve(args.session, args)
    if args.words:
        groups = {"custom": [w.strip() for w in args.words.split(",") if w.strip()]}
    else:
        groups = {k: v for k, v in SIGNALS.items() if not args.category or k in args.category}
    patterns = {
        k: re.compile("|".join(r"\b" + re.escape(w[:-1]) if w.endswith("*") else r"\b" + re.escape(w) + r"\b"
                               for w in ws), re.I)
        for k, ws in groups.items()
    }

    sources = [("main", path)] + [(a["label"], a["path"]) for a in subagents(path)]
    report = []
    for who, tpath in sources:
        found = defaultdict(list)
        for e in load(tpath):
            if e.get("type") != "assistant":
                continue
            text = extract_text(content_of(e), thinking=True)
            for cat, pat in patterns.items():
                for m in pat.finditer(text):
                    a, b = max(0, m.start() - 60), min(len(text), m.end() + 100)
                    found[cat].append((parse_ts(e.get("timestamp")), m.group(0), one_line(text[a:b], 200)))
        report.append((who, found))

    cats = list(groups)
    print(f"{'Transcript':<50} " + " ".join(f"{c[:14]:>14}" for c in cats))
    for who, found in report:
        print(f"{one_line(who, 50):<50} " + " ".join(f"{len(found[c]):>14}" for c in cats))
    for who, found in report:
        if not any(found.values()):
            continue
        print(f"\n=== {who}")
        for cat in cats:
            hits = found[cat]
            if not hits:
                continue
            print(f"  -- {cat} ({len(hits)}{', showing ' + str(args.limit) if len(hits) > args.limit else ''})")
            for ts, word, snip in hits[: args.limit]:
                print(f"    [{fmt_when(ts, with_date=False)}] «{word}» {snip}")


def cmd_efficiency(args):
    path = resolve(args.session, args)
    ts_list = transcripts(path)
    main = ts_list[0][1]

    print("--- Per transcript ---")
    print(f"{'Transcript':<46} {'Calls':>5} {'Peak ctx':>9} {'Ctx re-read':>12} {'Cache hit':>9} {'Output':>8}")
    for who, s in ts_list:
        t = s["tokens"]
        fed = t["input"] + t["cache_read"] + t["cache_create"]
        hit = f"{t['cache_read'] / fed:.0%}" if fed else "-"
        print(f"{one_line(who, 46):<46} {len(s['calls']):>5} {peak(s):>9,} "
              f"{sum(c['context'] for c in s['calls']):>12,} {hit:>9} {t['output']:>8,}")

    calls = main["calls"]
    if calls:
        print(f"\n--- Main context growth ({len(calls)} calls) ---")
        step = max(1, len(calls) // 12)
        top = peak(main) or 1
        for i in list(range(0, len(calls), step)) + ([len(calls) - 1] if (len(calls) - 1) % step else []):
            c = calls[i]
            print(f"  #{i:<5} {fmt_when(c['ts'], with_date=False)}  {c['context']:>9,}  {'█' * round(30 * c['context'] / top)}")
        spikes = sorted(
            ((calls[i]["context"] - calls[i - 1]["context"], i) for i in range(1, len(calls))), reverse=True)[:5]
        print("\n  Largest jumps (and the tool results that fed them):")
        for delta, i in spikes:
            if delta <= 0:
                break
            fed = ", ".join(f"{t['name']} {fmt_bytes(t['result_bytes'])} {one_line(t['target'], 40)}"
                            for t in sorted(calls[i]["after"], key=lambda t: -t["result_bytes"])[:2])
            print(f"  +{delta:>8,} at #{i} {fmt_when(calls[i]['ts'], with_date=False)}  {fed or '(user prompt / attachments)'}")

    print("\n--- Repeated reads within a transcript ---")
    any_dup = False
    for who, s in ts_list:
        reads = [t for t in s["tools"] if t["name"] == "Read"]
        per_path = Counter(t["input"].get("file_path") for t in reads)
        dups = [(p, n) for p, n in per_path.most_common() if n > 1]
        if dups:
            any_dup = True
            print(f"  {who}")
            for p, n in dups[:10]:
                same = [t for t in reads if t["input"].get("file_path") == p]
                ranges = len({(t["input"].get("offset"), t["input"].get("limit")) for t in same})
                kind = "same range" if ranges == 1 else f"{ranges} ranges"
                print(f"    {n}x {fmt_bytes(sum(t['result_bytes'] for t in same)):>9}  ({kind})  {p}")
    if not any_dup:
        print("  none")

    readers = defaultdict(set)
    read_bytes = Counter()
    for who, s in ts_list:
        for t in s["tools"]:
            if t["name"] == "Read":
                readers[t["input"].get("file_path")].add(who)
                read_bytes[t["input"].get("file_path")] += t["result_bytes"]
    shared = sorted((p for p in readers if len(readers[p]) > 1), key=lambda p: -read_bytes[p])
    print("\n--- Files read by several transcripts (candidates to pre-extract) ---")
    for p in shared[:15]:
        print(f"  {len(readers[p]):>2} readers {fmt_bytes(read_bytes[p]):>9}  {p}")
    if not shared:
        print("  none")

    print("\n--- Largest tool results (all transcripts) ---")
    every = [(t, who) for who, s in ts_list for t in s["tools"]]
    for t, who in sorted(every, key=lambda x: -x[0]["result_bytes"])[:10]:
        print(f"  {fmt_bytes(t['result_bytes']):>9}  {t['name']:<8} {one_line(t['target'], 55):<55}  [{one_line(who, 30)}]")

    notif = [c for c in calls if c["driver"] == "notification"]
    print(f"\n--- Notification-driven turns (main) ---\n  {len(notif)} of {len(calls)} API calls were triggered "
          f"by background-task/subagent notifications, not a prompt: {sum(c['context'] for c in notif):,} context "
          f"tokens re-read, {sum(c['output'] for c in notif):,} output tokens.\n  Expected while orchestrating; "
          f"waste once the work was already reported done.")


def cmd_diff(args):
    pa, pb = resolve(args.session_a, args), resolve(args.session_b, args)
    a, b = analyze(pa), analyze(pb)

    def row(name, va, vb, fmt=lambda v: f"{v:,}"):
        d = vb - va
        delta = "—" if not d else ("+" if d > 0 else "-") + fmt(abs(d))
        print(f"  {name:<18} {fmt(va):>14} {fmt(vb):>14} {delta:>14}")

    print(f"A: {pa}\nB: {pb}\n")
    print(f"  {'Metric':<18} {'A':>14} {'B':>14} {'Delta':>14}")
    row("Wall-clock", wall(a), wall(b), fmt_dur)
    row("Active", a["active_s"], b["active_s"], fmt_dur)
    if a["cost"] and b["cost"]:
        row("Cost (USD)", a["cost"]["totalCostUSD"], b["cost"]["totalCostUSD"], lambda v: f"{v:.2f}")
    row("API calls", len(a["calls"]), len(b["calls"]))
    row("Peak context", peak(a), peak(b))
    for k in ("input", "output", "cache_read", "cache_create"):
        row(k.replace("_", " ").capitalize(), a["tokens"][k], b["tokens"][k])
    row("Tool calls", len(a["tools"]), len(b["tools"]))
    row("Human prompts", len(a["prompts"]), len(b["prompts"]))
    row("Subagents", len(subagents(pa)), len(subagents(pb)))

    ca, cb = Counter(t["name"] for t in a["tools"]), Counter(t["name"] for t in b["tools"])
    print(f"\n  {'Tool':<18} {'A':>14} {'B':>14} {'Delta':>14}")
    for name in sorted(set(ca) | set(cb)):
        row(name, ca[name], cb[name])

    def touched(s):
        return {t["input"].get("file_path") for t in s["tools"] if t["name"] in WRITE_TOOLS | {"Read"}} - {None}

    fa, fb = touched(a), touched(b)
    for title, files in (("Both", fa & fb), ("Only A", fa - fb), ("Only B", fb - fa)):
        if files:
            print(f"\n  Files touched — {title} ({len(files)}):")
            for f in sorted(files):
                print(f"    {f}")


# --- CLI ---

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def scope(sp, recent):
        sp.add_argument("--project", help="project slug, repo path, or . for the current dir")
        sp.add_argument("--recent", type=int, default=recent, help=f"newest N sessions (default {recent or 'all'})")
        sp.add_argument("--all", action="store_true", help="no --recent limit")

    def one(name, help_, **kw):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("session", nargs="?", help="path | self | UUID/prefix | pr:N | title")
        sp.add_argument("--search", metavar="KEYWORD", help="pick the session from search results...")
        sp.add_argument("--index", type=int, help="...at this index")
        scope(sp, 50)
        return sp

    sub.add_parser("live", help="running Claude Code sessions").set_defaults(fn=cmd_live)
    sp = sub.add_parser("list", help="recent sessions, newest first")
    scope(sp, 20)
    sp.set_defaults(fn=cmd_list)
    sp = sub.add_parser("find", help="sessions by title (/rename name or auto title)")
    sp.add_argument("name")
    scope(sp, None)
    sp.set_defaults(fn=cmd_find)
    sp = sub.add_parser("search", help="sessions containing a keyword (incl. tool results, subagents)")
    sp.add_argument("keyword")
    sp.add_argument("--index", type=int, help="print only the path of match N")
    scope(sp, 50)
    sp.set_defaults(fn=cmd_search)
    sp = sub.add_parser("provenance", help="which sessions/subagents wrote or edited a file")
    sp.add_argument("file", help="path (exact match if it exists) or substring")
    scope(sp, None)
    sp.set_defaults(fn=cmd_provenance)

    sp = one("summary", "overview of one session")
    sp.add_argument("--deep", action="store_true", help="aggregate subagent transcripts too")
    sp.add_argument("--verbose", action="store_true", help="entry type counts, flag unknown types")
    sp.set_defaults(fn=cmd_summary)
    one("agents", "subagent table: type, description, time, tokens").set_defaults(fn=cmd_agents)
    sp = one("conversation", "prompts, notifications, and assistant text in order")
    sp.add_argument("--max-chars", type=int, default=500)
    sp.set_defaults(fn=cmd_conversation)
    one("tools", "tool call timeline with result sizes").set_defaults(fn=cmd_tools)
    sp = one("signals", "confusion / deviation / rework keywords in assistant text")
    sp.add_argument("--category", action="append", choices=list(SIGNALS))
    sp.add_argument("--words", help="comma-separated custom keywords (replaces the built-in set)")
    sp.add_argument("--limit", type=int, default=3, help="snippets per category per transcript")
    sp.set_defaults(fn=cmd_signals)
    one("efficiency", "context audit: growth, repeated reads, big results, notification turns").set_defaults(
        fn=cmd_efficiency)

    sp = sub.add_parser("diff", help="compare two sessions")
    sp.add_argument("session_a")
    sp.add_argument("session_b")
    sp.set_defaults(fn=cmd_diff, search=None)

    args = p.parse_args()
    try:
        args.fn(args)
    except BrokenPipeError:
        # Reader closed early (e.g. `| head`, `| grep -m1`): silence the flush at exit.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == "__main__":
    main()
