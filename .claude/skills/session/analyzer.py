#!/usr/bin/env python3
"""Claude Code session analyzer. Search, summarize, and extract session data.

Usage:
    analyzer.py list [--project SLUG] [--recent N] [--all]
    analyzer.py search KEYWORD [--project SLUG] [--recent N] [--all] [--verbose]
    analyzer.py find NAME [--project SLUG] [--recent N] [--all]
    analyzer.py summary SESSION_PATH [--deep] [--verbose]
    analyzer.py conversation SESSION_PATH [--max-chars N]
    analyzer.py tools SESSION_PATH
    analyzer.py diff SESSION_A SESSION_B
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

KNOWN_TYPES = {
    "user", "assistant", "custom-title", "progress",
    "queue-operation", "file-history-snapshot", "system",
    "last-prompt",
}


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


def get_role(msg):
    """Get the role of a message. Tries msg['type'] then msg['message']['role'].

    Works consistently regardless of whether the JSONL format stores role at
    the top level (type field) or nested under message.role.
    """
    t = msg.get("type")
    if t in ("user", "assistant"):
        return t
    inner = msg.get("message")
    if isinstance(inner, dict):
        return inner.get("role", "")
    return ""


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


def find_snippets(text, keyword, max_snippets=5, context_chars=40):
    """Find keyword matches with surrounding context (~80 chars total)."""
    snippets = []
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    start = 0
    while len(snippets) < max_snippets:
        pos = text_lower.find(keyword_lower, start)
        if pos == -1:
            break
        snippet_start = max(0, pos - context_chars)
        snippet_end = min(len(text), pos + len(keyword) + context_chars)
        snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."
        snippets.append(snippet)
        start = pos + len(keyword)
    return snippets


def get_session_aux_content(session_path):
    """Read externalized tool results and subagent transcripts for a session.

    Returns (tool_result_texts, subagent_texts) — lists of strings.
    """
    session_dir = Path(session_path).with_suffix("")

    tool_result_texts = []
    tool_results_dir = session_dir / "tool-results"
    if tool_results_dir.exists():
        for f in tool_results_dir.iterdir():
            if f.is_file():
                try:
                    tool_result_texts.append(f.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass

    subagent_texts = []
    subagents_dir = session_dir / "subagents"
    if subagents_dir.exists():
        for f in sorted(subagents_dir.glob("*.jsonl")):
            try:
                subagent_texts.append(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

    return tool_result_texts, subagent_texts


# --- Session discovery ---

def find_all_sessions(project_slug=None, recent=20, all_sessions=False):
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
    if all_sessions:
        return sessions
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

            if msg.get("type") == "custom-title":
                custom_title = msg.get("customTitle", "")

            inner = msg.get("message", {})
            if isinstance(inner, dict):
                if not model and inner.get("model"):
                    model = inner["model"]

            role = get_role(msg)
            if role == "user":
                text = extract_text(inner.get("content", "")) if isinstance(inner, dict) else ""
                if "<command-name>" in text:
                    m = re.search(r"<command-name>(/[^<]+)</command-name>", text)
                    if m:
                        cmd = m.group(1).strip()
                        if cmd not in ("/clear", "/resume", "/exit"):
                            if not command_name:
                                command_name = cmd
                if not first_user_text:
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


# --- Stats extraction (shared by summary, diff, deep) ---

def extract_session_stats(path, verbose=False):
    """Extract comprehensive stats from a session JSONL. Returns a dict."""
    messages = load_jsonl(path)
    file_size = os.path.getsize(path)

    stats = {
        "path": path,
        "file_size": file_size,
        "timestamps": [],
        "user_prompts": [],
        "tool_counts": defaultdict(int),
        "tool_result_bytes": defaultdict(int),
        "tool_use_details": [],
        "msg_type_counts": defaultdict(int),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read": 0,
        "total_cache_create": 0,
        "model": "",
        "version": "",
        "command": "",
        "custom_title": "",
        "skills_invoked": [],
        "files_touched": set(),
        "unknown_types": set(),
        "subagent_count": 0,
        "subagent_total_size": 0,
    }

    tool_use_map = {}

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        ts = get_timestamp(msg)
        if ts:
            stats["timestamps"].append(ts)

        msg_type = msg.get("type", "(none)")
        stats["msg_type_counts"][msg_type] += 1

        if msg_type not in KNOWN_TYPES and msg_type != "(none)":
            stats["unknown_types"].add(msg_type)

        if not stats["version"] and msg.get("version"):
            stats["version"] = msg["version"]

        if msg.get("type") == "custom-title":
            stats["custom_title"] = msg.get("customTitle", "")

        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue

        role = get_role(msg)
        content = inner.get("content", [])

        if not stats["model"] and inner.get("model"):
            stats["model"] = inner["model"]

        usage = inner.get("usage", {})
        if usage:
            stats["total_input_tokens"] += usage.get("input_tokens", 0)
            stats["total_output_tokens"] += usage.get("output_tokens", 0)
            stats["total_cache_read"] += usage.get("cache_read_input_tokens", 0)
            stats["total_cache_create"] += usage.get("cache_creation_input_tokens", 0)

        if role == "assistant":
            for tu in extract_tool_uses(content):
                name = tu.get("name", "unknown")
                stats["tool_counts"][name] += 1
                tid = tu.get("id", "")
                target = get_tool_target(tu)
                tool_use_map[tid] = {"name": name, "target": target}
                if name == "Skill":
                    skill_name = tu.get("input", {}).get("skill", "")
                    if skill_name:
                        stats["skills_invoked"].append(skill_name)
                # Track files touched by Read/Write/Edit
                if name in ("Read", "Write", "Edit"):
                    fp = tu.get("input", {}).get("file_path", "")
                    if fp:
                        stats["files_touched"].add(fp)

        if role == "user":
            text = extract_text(content)
            if "<command-name>" in text:
                m = re.search(r"<command-name>(/[^<]+)</command-name>", text)
                if m:
                    cmd = m.group(1).strip()
                    if cmd not in ("/clear", "/resume", "/exit") and not stats["command"]:
                        stats["command"] = cmd
            if text.strip() and "<tool_result" not in text and "tool_result" not in str(content)[:50]:
                clean = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
                clean = re.sub(r"<[^>]+>", "", clean).strip()
                if clean and len(clean) > 5 and "Caveat:" not in clean:
                    stats["user_prompts"].append({"text": clean, "ts": ts})

            for tr in extract_tool_results(content):
                tid = tr.get("tool_use_id", "")
                result_size = sizeof(tr.get("content", ""))
                if tid in tool_use_map:
                    info = tool_use_map[tid]
                    stats["tool_result_bytes"][info["name"]] += result_size
                    stats["tool_use_details"].append((info["name"], info["target"], result_size))

    # Subagent info
    session_dir = Path(path).with_suffix("") / "subagents"
    if session_dir.exists():
        agent_files = list(session_dir.glob("*.jsonl"))
        stats["subagent_count"] = len(agent_files)
        stats["subagent_total_size"] = sum(f.stat().st_size for f in agent_files)

    if verbose and stats["unknown_types"]:
        print(f"  [verbose] Unknown JSONL types in {Path(path).name}: {', '.join(sorted(stats['unknown_types']))}")

    return stats


def print_summary(stats):
    """Print a formatted summary from stats dict."""
    print("=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"  Path:     {stats['path']}")
    print(f"  Size:     {format_bytes(stats['file_size'])}")
    if stats["custom_title"]:
        print(f"  Name:     {stats['custom_title']}")
    if stats["command"]:
        print(f"  Command:  {stats['command']}")
    print(f"  Model:    {stats['model'] or '?'}")
    print(f"  Version:  {stats['version'] or '?'}")

    if stats["timestamps"]:
        first_ts = min(stats["timestamps"])
        last_ts = max(stats["timestamps"])
        duration = (last_ts - first_ts).total_seconds()
        print(f"  Started:  {first_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Ended:    {last_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Duration: {format_duration(duration)}")

    print(f"\n--- Tokens ---")
    print(f"  Input:        {stats['total_input_tokens']:>10,}")
    print(f"  Output:       {stats['total_output_tokens']:>10,}")
    print(f"  Cache read:   {stats['total_cache_read']:>10,}")
    print(f"  Cache create: {stats['total_cache_create']:>10,}")

    total_tool_calls = sum(stats["tool_counts"].values())
    print(f"\n--- Tools ({total_tool_calls} calls) ---")
    for name in sorted(stats["tool_counts"], key=lambda n: stats["tool_counts"][n], reverse=True):
        c = stats["tool_counts"][name]
        b = stats["tool_result_bytes"].get(name, 0)
        print(f"  {name:<25} {c:>4}x  {format_bytes(b):>10} results")

    if stats["skills_invoked"]:
        print(f"\n--- Skills invoked ---")
        for s in stats["skills_invoked"]:
            print(f"  /{s}")

    print(f"\n--- Message types ---")
    for mt, c in sorted(stats["msg_type_counts"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {mt}: {c}")

    if stats["subagent_count"]:
        print(f"\n--- Subagents: {stats['subagent_count']} ---")
        print(f"  Total subagent data: {format_bytes(stats['subagent_total_size'])}")

    print(f"\n--- User prompts ({len(stats['user_prompts'])}) ---")
    for p in stats["user_prompts"]:
        ts_str = p["ts"].strftime("%H:%M:%S") if p["ts"] else "?"
        text = p["text"][:120].replace("\n", " ")
        print(f"  [{ts_str}] {text}")

    # Top 5 largest tool results
    details = sorted(stats["tool_use_details"], key=lambda x: x[2], reverse=True)
    if details:
        print(f"\n--- Top 5 largest tool results ---")
        for name, target, size in details[:5]:
            target_short = target[:70] if len(target) > 70 else target
            print(f"  {format_bytes(size):>10}  {name}: {target_short}")

    print(f"\n{'=' * 70}")


# --- Commands ---

def cmd_list(args):
    project = args.get("project")
    recent = int(args.get("recent", 20))
    all_flag = args.get("all", False)
    sessions = find_all_sessions(project_slug=project, recent=recent, all_sessions=all_flag)

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
    """Run search and return sorted matches. Searches main JSONL, externalized tool results, and subagent transcripts."""
    keyword = args["keyword"]
    project = args.get("project")
    recent = int(args.get("recent", 50))
    all_flag = args.get("all", False)
    verbose = args.get("verbose", False)
    sessions = find_all_sessions(project_slug=project, recent=recent, all_sessions=all_flag)

    keyword_lower = keyword.lower()
    matches = []
    for s in sessions:
        try:
            with open(s["path"], "r", encoding="utf-8") as f:
                main_content = f.read()
        except Exception:
            continue

        # Collect text sources: (label, text)
        sources = [("main", main_content)]

        tool_result_texts, subagent_texts = get_session_aux_content(s["path"])
        for t in tool_result_texts:
            sources.append(("tool-result", t))
        for t in subagent_texts:
            sources.append(("subagent", t))

        total_hits = 0
        all_snippets = []
        for label, text in sources:
            hits = text.lower().count(keyword_lower)
            if hits:
                total_hits += hits
                snippets = find_snippets(text, keyword, max_snippets=3, context_chars=40)
                for snip in snippets:
                    all_snippets.append((label, snip))

        if total_hits:
            preview = get_session_preview(s["path"])
            if verbose:
                # Check for unknown types in main content
                for line in main_content.split("\n"):
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        t = msg.get("type")
                        if t and t not in KNOWN_TYPES:
                            print(f"  [verbose] Unknown type '{t}' in {Path(s['path']).name}")
                            break  # one warning per session
                    except (json.JSONDecodeError, AttributeError):
                        pass
            matches.append({**s, "hits": total_hits, "preview": preview, "snippets": all_snippets[:8]})

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

        # Show context snippets
        for source, snippet in m.get("snippets", [])[:3]:
            tag = f"[{source}]" if source != "main" else ""
            print(f"       {tag} {snippet}")

    print(f"\nPaths:")
    for i, m in enumerate(matches[:20]):
        print(f"  {i}: {m['path']}")

    print(f"\nTip: use 'search \"{args['keyword']}\" --index N' to get a path, or 'summary --search \"{args['keyword']}\" --index N' directly.")


def cmd_summary(args):
    path = resolve_session_path(args.get("session"), args=args)
    if not path:
        return

    verbose = args.get("verbose", False)
    deep = args.get("deep", False)

    stats = extract_session_stats(path, verbose=verbose)
    print_summary(stats)

    if not deep:
        # Show last assistant message (as before)
        _print_last_assistant_message(path)
        return

    # --deep: aggregate parent + all subagent transcripts
    session_dir = Path(path).with_suffix("") / "subagents"
    if not session_dir.exists() or not list(session_dir.glob("*.jsonl")):
        print("\nNo subagent transcripts found for --deep aggregation.")
        _print_last_assistant_message(path)
        return

    agent_files = sorted(session_dir.glob("*.jsonl"))
    subagent_stats_list = []
    for f in agent_files:
        try:
            subagent_stats_list.append(extract_session_stats(str(f), verbose=verbose))
        except Exception as e:
            if verbose:
                print(f"  [verbose] Failed to parse {f.name}: {e}")

    # Aggregated totals
    agg_input = stats["total_input_tokens"] + sum(s["total_input_tokens"] for s in subagent_stats_list)
    agg_output = stats["total_output_tokens"] + sum(s["total_output_tokens"] for s in subagent_stats_list)
    agg_cache_read = stats["total_cache_read"] + sum(s["total_cache_read"] for s in subagent_stats_list)
    agg_cache_create = stats["total_cache_create"] + sum(s["total_cache_create"] for s in subagent_stats_list)
    agg_tools = sum(stats["tool_counts"].values()) + sum(sum(s["tool_counts"].values()) for s in subagent_stats_list)

    # Combined tool counts
    combined_tools = defaultdict(int, stats["tool_counts"])
    for s in subagent_stats_list:
        for name, count in s["tool_counts"].items():
            combined_tools[name] += count

    # Combined duration across all transcripts
    all_timestamps = list(stats["timestamps"])
    for s in subagent_stats_list:
        all_timestamps.extend(s["timestamps"])
    combined_duration = 0
    if all_timestamps:
        combined_duration = (max(all_timestamps) - min(all_timestamps)).total_seconds()

    print(f"\n{'=' * 70}")
    print(f"DEEP AGGREGATION (parent + {len(subagent_stats_list)} subagents)")
    print(f"{'=' * 70}")
    print(f"  Combined duration: {format_duration(combined_duration)}")

    print(f"\n--- Aggregated tokens ---")
    print(f"  Input:        {agg_input:>10,}")
    print(f"  Output:       {agg_output:>10,}")
    print(f"  Cache read:   {agg_cache_read:>10,}")
    print(f"  Cache create: {agg_cache_create:>10,}")

    print(f"\n--- Aggregated tools ({agg_tools} calls) ---")
    for name in sorted(combined_tools, key=lambda n: combined_tools[n], reverse=True):
        print(f"  {name:<25} {combined_tools[name]:>4}x")

    print(f"\n--- Per-subagent breakdown ---")
    print(f"  {'#':<4} {'Duration':<12} {'Tools':>6} {'In tokens':>12} {'Out tokens':>12} {'Size':>10}  {'File'}")
    print(f"  {'─'*4} {'─'*12} {'─'*6} {'─'*12} {'─'*12} {'─'*10}  {'─'*30}")
    for i, s in enumerate(subagent_stats_list):
        dur = ""
        if s["timestamps"]:
            dur = format_duration((max(s["timestamps"]) - min(s["timestamps"])).total_seconds())
        tc = sum(s["tool_counts"].values())
        name = Path(s["path"]).stem[:30]
        print(f"  {i:<4} {dur:<12} {tc:>6} {s['total_input_tokens']:>12,} {s['total_output_tokens']:>12,} {format_bytes(s['file_size']):>10}  {name}")

    print(f"\n{'=' * 70}")


def _print_last_assistant_message(path):
    """Print the last assistant message from a session (used by summary)."""
    messages = load_jsonl(path)
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if get_role(msg) == "assistant":
            inner = msg.get("message", msg)
            if isinstance(inner, dict):
                text = extract_text(inner.get("content", ""))
                if text.strip():
                    print(f"\n--- Last assistant message (truncated) ---")
                    print(text[:400])
                    if len(text) > 400:
                        print(f"... [{len(text)} chars total]")
                    break


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

        role = get_role(msg)
        if not role:
            continue

        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue
        content = inner.get("content", [])
        ts = get_timestamp(msg)
        ts_str = ts.strftime("%H:%M:%S") if ts else "?"

        if role == "user":
            text = extract_text(content)
            clean = re.sub(r"<[^>]+>", "", text).strip()
            if not clean or len(clean) < 3:
                continue
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
        if get_role(msg) != "assistant":
            continue
        inner = msg.get("message", msg)
        if not isinstance(inner, dict):
            continue
        content = inner.get("content", [])
        ts = get_timestamp(msg)

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


def cmd_diff(args):
    """Compare two sessions side-by-side."""
    path_a = resolve_session_path(args.get("session_a"))
    if not path_a:
        print("Could not resolve first session.")
        return
    path_b = resolve_session_path(args.get("session_b"))
    if not path_b:
        print("Could not resolve second session.")
        return

    verbose = args.get("verbose", False)
    stats_a = extract_session_stats(path_a, verbose=verbose)
    stats_b = extract_session_stats(path_b, verbose=verbose)

    def dur(stats):
        if stats["timestamps"]:
            return (max(stats["timestamps"]) - min(stats["timestamps"])).total_seconds()
        return 0

    def delta_str(a, b, fmt_fn=None):
        d = b - a
        if d == 0:
            return "—"
        sign = "+" if d > 0 else "-"
        fn = fmt_fn or str
        return f"{sign}{fn(abs(d))}"

    dur_a = dur(stats_a)
    dur_b = dur(stats_b)
    tools_a = sum(stats_a["tool_counts"].values())
    tools_b = sum(stats_b["tool_counts"].values())

    print("=" * 80)
    print("SESSION COMPARISON")
    print("=" * 80)
    print(f"  A: {path_a}")
    print(f"  B: {path_b}")

    print(f"\n{'Metric':<22} {'A':>14} {'B':>14} {'Delta':>14}")
    print(f"{'─'*22} {'─'*14} {'─'*14} {'─'*14}")

    rows = [
        ("Duration", format_duration(dur_a), format_duration(dur_b), delta_str(dur_a, dur_b, lambda d: format_duration(abs(d)))),
        ("File size", format_bytes(stats_a["file_size"]), format_bytes(stats_b["file_size"]), delta_str(stats_a["file_size"], stats_b["file_size"], lambda d: format_bytes(abs(d)))),
        ("Input tokens", f"{stats_a['total_input_tokens']:,}", f"{stats_b['total_input_tokens']:,}", delta_str(stats_a['total_input_tokens'], stats_b['total_input_tokens'], lambda d: f"{abs(d):,}")),
        ("Output tokens", f"{stats_a['total_output_tokens']:,}", f"{stats_b['total_output_tokens']:,}", delta_str(stats_a['total_output_tokens'], stats_b['total_output_tokens'], lambda d: f"{abs(d):,}")),
        ("Cache read", f"{stats_a['total_cache_read']:,}", f"{stats_b['total_cache_read']:,}", delta_str(stats_a['total_cache_read'], stats_b['total_cache_read'], lambda d: f"{abs(d):,}")),
        ("Cache create", f"{stats_a['total_cache_create']:,}", f"{stats_b['total_cache_create']:,}", delta_str(stats_a['total_cache_create'], stats_b['total_cache_create'], lambda d: f"{abs(d):,}")),
        ("Tool calls", str(tools_a), str(tools_b), delta_str(tools_a, tools_b, lambda d: str(abs(d)))),
        ("User prompts", str(len(stats_a['user_prompts'])), str(len(stats_b['user_prompts'])), delta_str(len(stats_a['user_prompts']), len(stats_b['user_prompts']), lambda d: str(abs(d)))),
        ("Subagents", str(stats_a['subagent_count']), str(stats_b['subagent_count']), delta_str(stats_a['subagent_count'], stats_b['subagent_count'], lambda d: str(abs(d)))),
    ]

    for label, va, vb, d in rows:
        print(f"  {label:<20} {va:>14} {vb:>14} {d:>14}")

    # Tool breakdown
    all_tools = sorted(set(list(stats_a["tool_counts"].keys()) + list(stats_b["tool_counts"].keys())))
    if all_tools:
        print(f"\n{'Tool':<22} {'A':>14} {'B':>14} {'Delta':>14}")
        print(f"{'─'*22} {'─'*14} {'─'*14} {'─'*14}")
        for name in all_tools:
            ca = stats_a["tool_counts"].get(name, 0)
            cb = stats_b["tool_counts"].get(name, 0)
            print(f"  {name:<20} {ca:>14} {cb:>14} {delta_str(ca, cb, lambda d: str(abs(d))):>14}")

    # Files touched
    files_a = stats_a["files_touched"]
    files_b = stats_b["files_touched"]
    only_a = files_a - files_b
    only_b = files_b - files_a
    both = files_a & files_b

    if files_a or files_b:
        print(f"\n--- Files touched ---")
        if both:
            print(f"  Both ({len(both)}):")
            for f in sorted(both):
                print(f"    {f}")
        if only_a:
            print(f"  Only A ({len(only_a)}):")
            for f in sorted(only_a):
                print(f"    {f}")
        if only_b:
            print(f"  Only B ({len(only_b)}):")
            for f in sorted(only_b):
                print(f"    {f}")

    print(f"\n{'=' * 80}")


def find_by_name(name, project_slug=None, recent=100, all_sessions=False):
    """Find sessions matching a custom title. Returns list of (path, title) tuples."""
    sessions = find_all_sessions(project_slug=project_slug, recent=recent, all_sessions=all_sessions)
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
    all_flag = args.get("all", False)
    matches = find_by_name(name, project_slug=project, recent=recent, all_sessions=all_flag)

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
    positionals = []
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
            positionals.append(arg)
            i += 1

    # Map positionals to named args based on command
    if cmd == "search" and positionals:
        args["keyword"] = positionals[0]
    elif cmd == "find" and positionals:
        args["name"] = positionals[0]
    elif cmd == "diff":
        if len(positionals) >= 1:
            args["session_a"] = positionals[0]
        if len(positionals) >= 2:
            args["session_b"] = positionals[1]
    elif cmd in ("summary", "conversation", "tools") and positionals:
        args["session"] = positionals[0]

    if cmd == "list":
        cmd_list(args)
    elif cmd == "search":
        if "keyword" not in args:
            print("Usage: analyzer.py search KEYWORD [--project SLUG] [--recent N] [--all] [--verbose]")
            sys.exit(1)
        cmd_search(args)
    elif cmd == "find":
        if "name" not in args:
            print("Usage: analyzer.py find NAME [--project SLUG] [--recent N]")
            sys.exit(1)
        cmd_find(args)
    elif cmd == "summary":
        if "session" not in args and "search" not in args:
            print("Usage: analyzer.py summary SESSION_PATH_OR_ID [--deep] [--verbose]")
            print("       analyzer.py summary --search KEYWORD --index N [--deep]")
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
    elif cmd == "diff":
        if "session_a" not in args or "session_b" not in args:
            print("Usage: analyzer.py diff SESSION_A SESSION_B")
            sys.exit(1)
        cmd_diff(args)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
