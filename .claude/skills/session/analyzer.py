#!/usr/bin/env python3
"""Claude Code session analyzer. Search, summarize, and extract session data.

Usage:
    analyzer.py list [--project SLUG] [--recent N]
    analyzer.py search KEYWORD [--project SLUG] [--recent N]
    analyzer.py find NAME [--project SLUG] [--recent N]
    analyzer.py summary SESSION_PATH
    analyzer.py conversation SESSION_PATH [--max-chars N]
    analyzer.py tools SESSION_PATH
"""

import json
import os
import sys
import re
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


# --- Parsing helpers ---

def load_jsonl(path):
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return messages


def get_timestamp(msg):
    val = msg.get("timestamp")
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000 if val > 1e12 else val, tz=timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def extract_tool_uses(content):
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def extract_tool_results(content):
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]


def get_tool_target(tool_block):
    inp = tool_block.get("input", {})
    for key in ("command", "file_path", "pattern", "query", "url", "skill"):
        if key in inp:
            val = inp[key]
            if key == "pattern":
                return f"{inp.get('path', '.')} :: {val}"
            if key == "skill":
                return f"skill:{val}"
            return val[:120] if len(val) > 120 else val
    for k, v in inp.items():
        if isinstance(v, str) and v:
            return f"{k}={v[:80]}"
    return "(no target)"


def sizeof(obj):
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def format_bytes(b):
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.2f} MB"


def format_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# --- Session discovery ---

def find_all_sessions(project_slug=None, recent=20):
    """Find session JSONL files, sorted newest first."""
    sessions = []
    if project_slug:
        search_dirs = [PROJECTS_DIR / project_slug]
    else:
        search_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]

    for proj_dir in search_dirs:
        if not proj_dir.exists():
            continue
        for f in proj_dir.glob("*.jsonl"):
            stat = f.stat()
            sessions.append({
                "path": str(f),
                "project": proj_dir.name,
                "session_id": f.stem,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            })

    sessions.sort(key=lambda s: s["mtime"], reverse=True)
    return sessions[:recent]


def get_custom_title(path):
    """Extract customTitle from a session file. Returns the last title (most recent rename)."""
    title = ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if '"custom-title"' in line:
                try:
                    msg = json.loads(line.strip())
                    if msg.get("type") == "custom-title":
                        title = msg.get("customTitle", "")
                except json.JSONDecodeError:
                    pass
    return title


def get_session_preview(path):
    """Get first user prompt and basic info without full parse."""
    first_user_text = ""
    command_name = ""
    custom_title = ""
    version = ""
    model = ""
    first_ts = None
    last_ts = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = get_timestamp(msg)
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            if not version and msg.get("version"):
                version = msg["version"]

            # Pick up custom title
            if msg.get("type") == "custom-title":
                custom_title = msg.get("customTitle", "")

            inner = msg.get("message", {})
            if isinstance(inner, dict):
                if not model and inner.get("model"):
                    model = inner["model"]

            if msg.get("type") == "user":
                text = extract_text(inner.get("content", "")) if isinstance(inner, dict) else ""
                # Check for command invocation (skip /clear, /resume, /exit)
                if "<command-name>" in text:
                    m = re.search(r"<command-name>(/[^<]+)</command-name>", text)
                    if m:
                        cmd = m.group(1).strip()
                        if cmd not in ("/clear", "/resume", "/exit"):
                            if not command_name:
                                command_name = cmd
                if not first_user_text:
                    # Strip XML tags and boilerplate
                    clean = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
                    clean = re.sub(r"<[^>]+>", "", clean).strip()
                    if clean and len(clean) > 5 and "Caveat:" not in clean and "tool_result" not in text:
                        first_user_text = clean[:200]

    return {
        "first_prompt": first_user_text,
        "command": command_name,
        "custom_title": custom_title,
        "version": version,
        "model": model,
        "started": first_ts,
        "last_activity": last_ts,
    }


# --- Commands ---

def cmd_list(args):
    project = args.get("project")
    recent = int(args.get("recent", 20))
    sessions = find_all_sessions(project_slug=project, recent=recent)

    if not sessions:
        print("No sessions found.")
        return

    print(f"{'#':<4} {'Date':<20} {'Size':>8}  {'Project':<40} {'Command/Prompt'}")
    print(f"{'─'*4} {'─'*20} {'─'*8}  {'─'*40} {'─'*40}")

    for i, s in enumerate(sessions):
        preview = get_session_preview(s["path"])
        date_str = s["mtime"].strftime("%Y-%m-%d %H:%M")
        size_str = format_bytes(s["size"])
        title = preview["custom_title"]
        label = title or preview["command"] or preview["first_prompt"][:50] or "(empty)"
        if title and preview["command"]:
            label = f"[{title}] {preview['command']}"
        proj = s["project"]
        if len(proj) > 40:
            proj = "..." + proj[-37:]
        print(f"{i:<4} {date_str:<20} {size_str:>8}  {proj:<40} {label}")

    print(f"\n{len(sessions)} sessions shown. Use 'summary <path>' for details.")
    print(f"Session dir: {PROJECTS_DIR}/")


def run_search(args):
    """Run search and return sorted matches. Shared by cmd_search and resolve_search_index."""
    keyword = args["keyword"]
    project = args.get("project")
    recent = int(args.get("recent", 50))
    sessions = find_all_sessions(project_slug=project, recent=recent)

    matches = []
    for s in sessions:
        try:
            with open(s["path"], "r", encoding="utf-8") as f:
                content = f.read()
            if keyword.lower() in content.lower():
                count = content.lower().count(keyword.lower())
                preview = get_session_preview(s["path"])
                matches.append({**s, "hits": count, "preview": preview})
        except Exception:
            continue

    matches.sort(key=lambda m: m["hits"], reverse=True)
    return matches


def resolve_search_index(args):
    """Resolve --search KEYWORD --index N to a session path."""
    index = int(args["index"])
    matches = run_search(args)
    if not matches:
        print(f'No sessions containing "{args["keyword"]}".')
        return None
    if index < 0 or index >= len(matches):
        print(f"Index {index} out of range (0-{len(matches)-1}).")
        return None
    return matches[index]["path"]


def cmd_search(args):
    matches = run_search(args)

    if not matches:
        print(f'No sessions containing "{args["keyword"]}".')
        return

    # --index N: print just the path of the Nth result
    if "index" in args:
        index = int(args["index"])
        if index < 0 or index >= len(matches):
            print(f"Index {index} out of range (0-{len(matches)-1}).")
            return
        print(matches[index]["path"])
        return

    print(f'Sessions matching "{args["keyword"]}" ({len(matches)} found):\n')
    print(f"{'#':<4} {'Hits':>5} {'Date':<20} {'Size':>8}  {'Command/Prompt'}")
    print(f"{'─'*4} {'─'*5} {'─'*20} {'─'*8}  {'─'*40}")

    for i, m in enumerate(matches[:20]):
        date_str = m["mtime"].strftime("%Y-%m-%d %H:%M")
        size_str = format_bytes(m["size"])
        title = m["preview"]["custom_title"]
        label = title or m["preview"]["command"] or m["preview"]["first_prompt"][:50] or "(empty)"
        if title and m["preview"]["command"]:
            label = f"[{title}] {m['preview']['command']}"
        print(f"{i:<4} {m['hits']:>5} {date_str:<20} {size_str:>8}  {label}")

    print(f"\nPaths:")
    for i, m in enumerate(matches[:20]):
        print(f"  {i}: {m['path']}")

    print(f"\nTip: use 'search \"{args['keyword']}\" --index N' to get a path, or 'summary --search \"{args['keyword']}\" --index N' directly.")


def cmd_summary(args):
    path = resolve_session_path(args.get("session"), args=args)
    if not path:
        return

    messages = load_jsonl(path)
    file_size = os.path.getsize(path)

    # Classify messages
    timestamps = []
    user_prompts = []
    tool_counts = defaultdict(int)
    tool_result_bytes = defaultdict(int)
    tool_use_map = {}
    tool_use_details = []
    msg_type_counts = defaultdict(int)
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read = 0
    total_cache_create = 0
    model_used = ""
    version = ""
    command_name = ""
    custom_title = ""
    skills_invoked = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        ts = get_timestamp(msg)
        if ts:
            timestamps.append(ts)

        msg_type_counts[msg.get("type", "(none)")] += 1
        if not version and msg.get("version"):
            version = msg["version"]

        # Pick up custom title
        if msg.get("type") == "custom-title":
            custom_title = msg.get("customTitle", "")

        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue
        role = inner.get("role", "")
        content = inner.get("content", [])

        if not model_used and inner.get("model"):
            model_used = inner["model"]

        # Token usage
        usage = inner.get("usage", {})
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
            total_cache_read += usage.get("cache_read_input_tokens", 0)
            total_cache_create += usage.get("cache_creation_input_tokens", 0)

        if role == "assistant":
            for tu in extract_tool_uses(content):
                name = tu.get("name", "unknown")
                tool_counts[name] += 1
                tid = tu.get("id", "")
                target = get_tool_target(tu)
                tool_use_map[tid] = {"name": name, "target": target}
                if name == "Skill":
                    skill_name = tu.get("input", {}).get("skill", "")
                    if skill_name:
                        skills_invoked.append(skill_name)

        if role == "user":
            text = extract_text(content)
            # Detect command invocation
            if "<command-name>" in text:
                m = re.search(r"<command-name>(/[^<]+)</command-name>", text)
                if m:
                    cmd = m.group(1).strip()
                    if cmd not in ("/clear", "/resume", "/exit") and not command_name:
                        command_name = cmd
            # Collect meaningful user prompts
            if text.strip() and "<tool_result" not in text and "tool_result" not in str(content)[:50]:
                clean = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
                clean = re.sub(r"<[^>]+>", "", clean).strip()
                if clean and len(clean) > 5 and "Caveat:" not in clean:
                    user_prompts.append({"text": clean, "ts": ts})

            for tr in extract_tool_results(content):
                tid = tr.get("tool_use_id", "")
                result_size = sizeof(tr.get("content", ""))
                if tid in tool_use_map:
                    info = tool_use_map[tid]
                    tool_result_bytes[info["name"]] += result_size
                    tool_use_details.append((info["name"], info["target"], result_size))

    # Subagents
    session_dir = Path(path).with_suffix("") / "subagents"
    subagent_count = 0
    subagent_total_size = 0
    if session_dir.exists():
        agent_files = list(session_dir.glob("*.jsonl"))
        subagent_count = len(agent_files)
        subagent_total_size = sum(f.stat().st_size for f in agent_files)

    # --- Output ---
    print("=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"  Path:     {path}")
    print(f"  Size:     {format_bytes(file_size)}")
    if custom_title:
        print(f"  Name:     {custom_title}")
    if command_name:
        print(f"  Command:  {command_name}")
    print(f"  Model:    {model_used or '?'}")
    print(f"  Version:  {version or '?'}")

    if timestamps:
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        duration = (last_ts - first_ts).total_seconds()
        print(f"  Started:  {first_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Ended:    {last_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Duration: {format_duration(duration)}")

    print(f"\n--- Tokens ---")
    print(f"  Input:        {total_input_tokens:>10,}")
    print(f"  Output:       {total_output_tokens:>10,}")
    print(f"  Cache read:   {total_cache_read:>10,}")
    print(f"  Cache create: {total_cache_create:>10,}")

    total_tool_calls = sum(tool_counts.values())
    print(f"\n--- Tools ({total_tool_calls} calls) ---")
    for name in sorted(tool_counts, key=lambda n: tool_counts[n], reverse=True):
        c = tool_counts[name]
        b = tool_result_bytes.get(name, 0)
        print(f"  {name:<25} {c:>4}x  {format_bytes(b):>10} results")

    if skills_invoked:
        print(f"\n--- Skills invoked ---")
        for s in skills_invoked:
            print(f"  /{s}")

    print(f"\n--- Message types ---")
    for mt, c in sorted(msg_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {mt}: {c}")

    if subagent_count:
        print(f"\n--- Subagents: {subagent_count} ---")
        print(f"  Total subagent data: {format_bytes(subagent_total_size)}")

    print(f"\n--- User prompts ({len(user_prompts)}) ---")
    for i, p in enumerate(user_prompts):
        ts_str = p["ts"].strftime("%H:%M:%S") if p["ts"] else "?"
        text = p["text"][:120].replace("\n", " ")
        print(f"  [{ts_str}] {text}")

    # Top 5 largest tool results
    tool_use_details.sort(key=lambda x: x[2], reverse=True)
    if tool_use_details:
        print(f"\n--- Top 5 largest tool results ---")
        for name, target, size in tool_use_details[:5]:
            target_short = target[:70] if len(target) > 70 else target
            print(f"  {format_bytes(size):>10}  {name}: {target_short}")

    # Last assistant message
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message", msg)
        if isinstance(inner, dict) and inner.get("role") == "assistant":
            text = extract_text(inner.get("content", ""))
            if text.strip():
                print(f"\n--- Last assistant message (truncated) ---")
                print(text[:400])
                if len(text) > 400:
                    print(f"... [{len(text)} chars total]")
                break

    print(f"\n{'=' * 70}")


def cmd_conversation(args):
    """Extract the conversation flow (user prompts + assistant text responses)."""
    path = resolve_session_path(args.get("session"), args=args)
    if not path:
        return

    max_chars = int(args.get("max_chars", 500))
    messages = load_jsonl(path)

    turn = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue
        role = inner.get("role", "")
        content = inner.get("content", [])
        ts = get_timestamp(msg)
        ts_str = ts.strftime("%H:%M:%S") if ts else "?"

        if role == "user":
            text = extract_text(content)
            clean = re.sub(r"<[^>]+>", "", text).strip()
            # Skip tool results and empty messages
            if not clean or len(clean) < 3:
                continue
            # Skip messages that are just tool results
            if isinstance(content, list) and all(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            turn += 1
            print(f"\n{'─' * 60}")
            print(f"USER [{ts_str}] (turn {turn})")
            print(f"{'─' * 60}")
            truncated = clean[:max_chars]
            print(truncated)
            if len(clean) > max_chars:
                print(f"... [{len(clean)} chars]")

        elif role == "assistant":
            text = extract_text(content)
            if not text.strip():
                continue
            # Also show tool calls briefly
            tools = extract_tool_uses(content)
            tool_summary = ""
            if tools:
                names = [t.get("name", "?") for t in tools]
                tool_summary = f" [tools: {', '.join(names)}]"

            print(f"\nASSISTANT [{ts_str}]{tool_summary}")
            truncated = text[:max_chars]
            print(truncated)
            if len(text) > max_chars:
                print(f"... [{len(text)} chars]")


def cmd_tools(args):
    """Detailed tool usage timeline."""
    path = resolve_session_path(args.get("session"), args=args)
    if not path:
        return

    messages = load_jsonl(path)
    tool_timeline = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue
        role = inner.get("role", "")
        content = inner.get("content", [])
        ts = get_timestamp(msg)

        if role == "assistant":
            for tu in extract_tool_uses(content):
                tool_timeline.append({
                    "ts": ts,
                    "name": tu.get("name", "?"),
                    "target": get_tool_target(tu),
                    "id": tu.get("id", ""),
                })

    print(f"Tool usage timeline ({len(tool_timeline)} calls):\n")
    for t in tool_timeline:
        ts_str = t["ts"].strftime("%H:%M:%S") if t["ts"] else "?"
        target = t["target"][:80] if len(t["target"]) > 80 else t["target"]
        print(f"  [{ts_str}] {t['name']:<20} {target}")


def find_by_name(name, project_slug=None, recent=100):
    """Find sessions matching a custom title. Returns list of (path, title) tuples."""
    sessions = find_all_sessions(project_slug=project_slug, recent=recent)
    matches = []
    name_lower = name.lower()
    for s in sessions:
        title = get_custom_title(s["path"])
        if title and name_lower in title.lower():
            matches.append({**s, "custom_title": title})
    return matches


def cmd_find(args):
    """Find sessions by custom title (set via /rename)."""
    name = args["name"]
    project = args.get("project")
    recent = int(args.get("recent", 100))
    matches = find_by_name(name, project_slug=project, recent=recent)

    if not matches:
        print(f'No sessions with title matching "{name}".')
        print("Titles are set via /rename in Claude Code.")
        return

    print(f'Sessions matching title "{name}" ({len(matches)} found):\n')
    print(f"{'#':<4} {'Date':<20} {'Size':>8}  {'Title':<30} {'Session ID'}")
    print(f"{'─'*4} {'─'*20} {'─'*8}  {'─'*30} {'─'*36}")

    for i, m in enumerate(matches[:20]):
        date_str = m["mtime"].strftime("%Y-%m-%d %H:%M")
        size_str = format_bytes(m["size"])
        title = m["custom_title"][:30]
        print(f"{i:<4} {date_str:<20} {size_str:>8}  {title:<30} {m['session_id']}")

    print(f"\nPaths:")
    for i, m in enumerate(matches[:20]):
        print(f"  {i}: {m['path']}")

    if len(matches) == 1:
        print(f"\nResume: claude --resume {matches[0]['session_id']}")


def resolve_session_path(session_arg=None, args=None):
    """Resolve a session argument to a full path.

    Accepts:
      - A file path
      - A session UUID
      - A custom title (from /rename)
      - --search KEYWORD --index N (via args dict)
    """
    # Handle --search + --index combo
    if args and "search" in args and "index" in args:
        search_args = {**args, "keyword": args["search"]}
        return resolve_search_index(search_args)

    if session_arg is None:
        print("No session specified. Provide a path, UUID, name, or --search KEYWORD --index N.")
        return None

    if os.path.isfile(session_arg):
        return session_arg

    # Try as session UUID
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        candidate = proj_dir / f"{session_arg}.jsonl"
        if candidate.exists():
            return str(candidate)

    # Try as custom title
    matches = find_by_name(session_arg)
    if len(matches) == 1:
        return matches[0]["path"]
    if len(matches) > 1:
        print(f'Multiple sessions match title "{session_arg}":')
        for i, m in enumerate(matches):
            print(f"  {i}: [{m['custom_title']}] {m['path']}")
        print("Be more specific or use a full path.")
        return None

    print(f"Session not found: {session_arg}")
    print("Provide a full path, session UUID, custom title, or --search KEYWORD --index N.")
    return None


# --- CLI ---

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = {}

    # Parse remaining args
    i = 2
    positional_given = False
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                args[key] = sys.argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            if not positional_given:
                if cmd == "search":
                    args["keyword"] = arg
                elif cmd == "find":
                    args["name"] = arg
                elif cmd in ("summary", "conversation", "tools"):
                    args["session"] = arg
                positional_given = True
            i += 1

    if cmd == "list":
        cmd_list(args)
    elif cmd == "search":
        if "keyword" not in args:
            print("Usage: analyzer.py search KEYWORD [--project SLUG]")
            sys.exit(1)
        cmd_search(args)
    elif cmd == "find":
        if "name" not in args:
            print("Usage: analyzer.py find NAME [--project SLUG] [--recent N]")
            sys.exit(1)
        cmd_find(args)
    elif cmd == "summary":
        if "session" not in args and "search" not in args:
            print("Usage: analyzer.py summary SESSION_PATH_OR_ID")
            print("       analyzer.py summary --search KEYWORD --index N")
            sys.exit(1)
        cmd_summary(args)
    elif cmd == "conversation":
        if "session" not in args and "search" not in args:
            print("Usage: analyzer.py conversation SESSION_PATH [--max-chars N]")
            print("       analyzer.py conversation --search KEYWORD --index N")
            sys.exit(1)
        cmd_conversation(args)
    elif cmd == "tools":
        if "session" not in args and "search" not in args:
            print("Usage: analyzer.py tools SESSION_PATH")
            print("       analyzer.py tools --search KEYWORD --index N")
            sys.exit(1)
        cmd_tools(args)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
