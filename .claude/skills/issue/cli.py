#!/usr/bin/env python3
"""
Issue Tracker CLI

Text-file-based issue tracker. Issues are markdown files with YAML frontmatter,
organized in directories by status (open/, in_progress/, closed/).

All projects share a single issues root (default: ~/issues/).
Config: ~/.config/issue-tracker/config.yaml
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "error: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    raise SystemExit(1)

CONFIG_PATH = Path("~/.config/issue-tracker/config.yaml").expanduser()
DEFAULT_ISSUES_ROOT = Path("~/issues").expanduser()
STATUS_DIRS = ("open", "in_progress", "closed")
SEVERITIES = ("critical", "significant", "enhancement")
SECTIONS = ("problem", "analysis", "options", "decision", "fix")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load config, creating default if missing."""
    if not CONFIG_PATH.exists():
        return {"issues_root": str(DEFAULT_ISSUES_ROOT), "default_project": None, "projects": {}}
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict) -> None:
    """Write config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def get_issues_root(config: dict) -> Path:
    """Resolve the top-level issues root directory."""
    raw = config.get("issues_root", str(DEFAULT_ISSUES_ROOT))
    return Path(raw).expanduser().resolve()


# ---------------------------------------------------------------------------
# Project resolution
# ---------------------------------------------------------------------------


def resolve_project(config: dict, override: str | None) -> tuple[str, dict]:
    """Return (project_name, project_config).

    Resolution: --project override > cwd under a root > default_project > error.
    """
    projects = config.get("projects") or {}

    if override:
        if override not in projects:
            print(f"error: unknown project '{override}'", file=sys.stderr)
            raise SystemExit(1)
        return override, projects[override]

    cwd = Path.cwd().resolve()
    for name, proj in projects.items():
        root = Path(proj["root"]).expanduser().resolve()
        try:
            cwd.relative_to(root)
            return name, proj
        except ValueError:
            pass

    default = config.get("default_project")
    if default and default in projects:
        return default, projects[default]

    print(
        "error: not in a known project. Run 'cli.py init' or pass --project <name>",
        file=sys.stderr,
    )
    raise SystemExit(1)


def project_issues_dir(config: dict, project_name: str) -> Path:
    """Return <issues_root>/<project_name>/."""
    return get_issues_root(config) / project_name


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split markdown into (frontmatter_dict, body)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break

    if end is None:
        return {}, text

    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    return yaml.safe_load(fm_text) or {}, body


def dump_frontmatter(fm: dict) -> str:
    """Render frontmatter dict as YAML."""
    return yaml.dump(fm, default_flow_style=False, allow_unicode=True).rstrip("\n")


def write_issue_file(path: Path, fm: dict, body: str) -> None:
    """Write frontmatter + body to path."""
    content = f"---\n{dump_frontmatter(fm)}\n---\n{body}"
    path.write_text(content)


# ---------------------------------------------------------------------------
# ID, slug, file finding
# ---------------------------------------------------------------------------


def next_issue_id(project_dir: Path) -> int:
    """Find max issue ID across all status dirs, return max + 1."""
    max_id = 0
    for status in STATUS_DIRS:
        d = project_dir / status
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            m = re.match(r"^(\d+)-", f.name)
            if m:
                max_id = max(max_id, int(m.group(1)))
    return max_id + 1


def make_slug(title: str) -> str:
    """Generate a filename-safe slug from title (max 50 chars)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:50].rstrip("-")


def issue_id_from_filename(name: str) -> int:
    """Extract numeric ID from filename like '034-slug.md'."""
    m = re.match(r"^(\d+)", name)
    if not m:
        print(f"error: cannot parse ID from filename '{name}'", file=sys.stderr)
        raise SystemExit(1)
    return int(m.group(1))


def find_issue_file(project_dir: Path, id_or_keyword: str) -> tuple[Path, str]:
    """Find an issue file by numeric ID or keyword substring.

    Returns (file_path, status_dir_name). Exits on not found or ambiguous.
    """
    matches: list[tuple[Path, str]] = []
    is_numeric = id_or_keyword.isdigit()

    for status in STATUS_DIRS:
        d = project_dir / status
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            if is_numeric:
                m = re.match(r"^(\d+)-", f.name)
                if m and int(m.group(1)) == int(id_or_keyword):
                    matches.append((f, status))
            elif id_or_keyword.lower() in f.name.lower():
                matches.append((f, status))

    if not matches:
        print(f"error: no issue found matching '{id_or_keyword}'", file=sys.stderr)
        raise SystemExit(1)

    if len(matches) > 1:
        print(f"error: multiple matches for '{id_or_keyword}':", file=sys.stderr)
        for f, s in matches:
            print(f"  [{s}] {f.name}", file=sys.stderr)
        raise SystemExit(1)

    return matches[0]


# ---------------------------------------------------------------------------
# Section replacement
# ---------------------------------------------------------------------------


def replace_section(body: str, section_name: str, new_content: str) -> str:
    """Replace content of a ## Section. Everything between the heading and the next ## or EOF."""
    pattern = re.compile(
        r"(^## " + re.escape(section_name.title()) + r"\n)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    replacement = f"## {section_name.title()}\n\n{new_content.strip()}\n\n"
    result, count = pattern.subn(replacement, body)
    if count == 0:
        print(f"error: section '{section_name}' not found in issue", file=sys.stderr)
        raise SystemExit(1)
    return result


# ---------------------------------------------------------------------------
# Issue template
# ---------------------------------------------------------------------------


def issue_template(
    issue_id: int,
    severity: str,
    title: str,
    package: str | None,
    component: str | None,
    summary: str,
    problem: str,
    analysis: str,
) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_str) for a new issue."""
    fm: dict = {
        "id": issue_id,
        "severity": severity,
        "package": package,
        "component": component,
        "summary": summary,
        "created": datetime.date.today().isoformat(),
        "closed": None,
        "commit": None,
    }
    body = f"""
# {title}

## Problem

{problem}

## Analysis

{analysis}

## Options

## Decision

## Fix
"""
    return fm, body


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize config and directory structure for a project."""
    config = load_config()

    name = args.name or Path.cwd().name

    if args.issues_root:
        config["issues_root"] = str(Path(args.issues_root).expanduser().resolve())

    issues_root = get_issues_root(config)

    packages: list[str] = []
    if args.packages:
        packages = [p.strip() for p in args.packages.split(",") if p.strip()]

    # Create project directory structure under issues_root
    proj_dir = issues_root / name
    for status in STATUS_DIRS:
        (proj_dir / status).mkdir(parents=True, exist_ok=True)

    qf_path = proj_dir / "quickfixes.md"
    if not qf_path.exists():
        qf_path.write_text("# Quick Fixes\n\n## Open\n\n## Closed\n")

    # Update config
    if "projects" not in config or config["projects"] is None:
        config["projects"] = {}

    proj_entry: dict = {"root": str(Path.cwd())}
    if packages:
        proj_entry["packages"] = packages

    config["projects"][name] = proj_entry
    save_config(config)

    print(f"Initialized project '{name}'")
    print(f"  Issues dir: {proj_dir}")
    print(f"  Issues root: {issues_root}")
    if packages:
        print(f"  Packages: {', '.join(packages)}")
    print(f"  Config: {CONFIG_PATH}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new issue file in open/."""
    severity = args.severity
    if severity not in SEVERITIES:
        print(f"error: severity must be one of: {', '.join(SEVERITIES)}", file=sys.stderr)
        raise SystemExit(1)

    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    issue_id = next_issue_id(proj_dir)
    slug = make_slug(args.title)
    filename = f"{issue_id:03d}-{slug}.md"

    fm, body = issue_template(
        issue_id=issue_id,
        severity=severity,
        title=args.title,
        package=args.package,
        component=args.component,
        summary=args.summary or args.title,
        problem=args.problem or "",
        analysis=args.analysis or "",
    )

    out_path = proj_dir / "open" / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_issue_file(out_path, fm, body)

    print(f"Created #{issue_id:03d}: {fm['summary']}")
    return 0


def cmd_quickfix(args: argparse.Namespace) -> int:
    """Add a quickfix section to quickfixes.md."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)
    qf_path = proj_dir / "quickfixes.md"

    if not qf_path.exists():
        print(f"error: quickfixes.md not found at {qf_path}", file=sys.stderr)
        raise SystemExit(1)

    checklist_lines: list[str] = []
    for item in args.items:
        if "=" not in item:
            print(f"error: item format must be 'file:line=description', got: {item}", file=sys.stderr)
            raise SystemExit(1)
        location, description = item.split("=", 1)
        checklist_lines.append(f"- [ ] `{location.strip()}` — {description.strip()}")

    header = f"### [{args.package}] {args.title}" if args.package else f"### {args.title}"
    section_text = header + "\n" + "\n".join(checklist_lines) + "\n"

    content = qf_path.read_text()
    open_marker = "## Open\n"
    idx = content.find(open_marker)
    if idx == -1:
        print("error: quickfixes.md missing '## Open' section", file=sys.stderr)
        raise SystemExit(1)

    insert_pos = idx + len(open_marker)
    content = content[:insert_pos] + "\n" + section_text + content[insert_pos:]
    qf_path.write_text(content)

    print(f"Added quickfix: {args.title}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update a section in an issue file, reading new content from stdin."""
    section = args.section.lower()
    if section not in SECTIONS:
        print(f"error: section must be one of: {', '.join(SECTIONS)}", file=sys.stderr)
        raise SystemExit(1)

    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    file_path, _ = find_issue_file(proj_dir, args.id)
    new_content = sys.stdin.read()

    text = file_path.read_text()
    fm, body = parse_frontmatter(text)
    body = replace_section(body, section, new_content)
    write_issue_file(file_path, fm, body)

    issue_id = issue_id_from_filename(file_path.name)
    print(f"Updated #{issue_id:03d} section: {section}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List issues filtered by status, package, severity."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    status_filter = args.status or "open"
    if status_filter == "all":
        dirs_to_scan = list(STATUS_DIRS)
    elif status_filter == "open":
        dirs_to_scan = ["open", "in_progress"]
    else:
        dirs_to_scan = [status_filter]

    issues_by_status: dict[str, list[dict]] = {s: [] for s in dirs_to_scan}

    for status in dirs_to_scan:
        d = proj_dir / status
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            text = f.read_text()
            fm, _ = parse_frontmatter(text)
            if not fm:
                continue
            if args.package and fm.get("package") != args.package:
                continue
            if args.severity and fm.get("severity") != args.severity:
                continue
            issues_by_status[status].append({
                "id": fm.get("id", 0),
                "severity": fm.get("severity", ""),
                "package": fm.get("package") or "",
                "summary": fm.get("summary", ""),
            })

    # Counts across all dirs for header
    all_counts: dict[str, int] = {}
    for s in STATUS_DIRS:
        d = proj_dir / s
        all_counts[s] = len(list(d.glob("*.md"))) if d.exists() else 0

    # Quickfix counts
    qf_path = proj_dir / "quickfixes.md"
    qf_open = 0
    qf_closed = 0
    if qf_path.exists():
        qf_text = qf_path.read_text()
        qf_open = qf_text.count("- [ ]")
        qf_closed = qf_text.count("- [x]")

    print(
        f"{proj_name} — {all_counts['open']} open, "
        f"{all_counts['in_progress']} in progress, "
        f"{all_counts['closed']} closed"
    )

    label_map = {"open": "Open", "in_progress": "In Progress", "closed": "Closed"}
    for status in dirs_to_scan:
        items = issues_by_status[status]
        if not items:
            continue
        print(f"\n  {label_map[status]}:")
        for iss in items:
            pkg = iss["package"]
            sev = iss["severity"]
            tag = f"{sev}, {pkg}" if pkg else sev
            print(f"    {iss['id']:03d} [{tag}] {iss['summary']}")

    print(f"\n  Quick fixes: {qf_open} open, {qf_closed} closed")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search issues and quickfixes for a query string."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    query = args.query.lower()
    results: list[str] = []

    for status in STATUS_DIRS:
        d = proj_dir / status
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            text = f.read_text()
            if query in text.lower():
                fm, _ = parse_frontmatter(text)
                issue_id = fm.get("id", "?")
                sev = fm.get("severity", "")
                pkg = fm.get("package") or ""
                summary = fm.get("summary", "")
                tag = f"{sev}, {pkg}" if pkg else sev
                results.append(f"{issue_id:03d} [{tag}, {status}] {summary}")

    # Search quickfixes
    qf_path = proj_dir / "quickfixes.md"
    if qf_path.exists():
        current_header = ""
        for line in qf_path.read_text().splitlines():
            if line.startswith("### "):
                current_header = line
            elif query in line.lower():
                results.append(f"[quickfix] {current_header}: {line.strip()}")

    if not results:
        print("No results found.")
        return 0

    cap = 20
    for r in results[:cap]:
        print(r)
    if len(results) > cap:
        print(f"... {len(results) - cap} more results. Narrow your query.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display the full content of an issue."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    matches: list[tuple[Path, str]] = []
    is_numeric = args.id_or_keyword.isdigit()

    for status in STATUS_DIRS:
        d = proj_dir / status
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            if is_numeric:
                m = re.match(r"^(\d+)-", f.name)
                if m and int(m.group(1)) == int(args.id_or_keyword):
                    matches.append((f, status))
            elif args.id_or_keyword.lower() in f.name.lower():
                matches.append((f, status))

    if not matches:
        print(f"error: no issue found matching '{args.id_or_keyword}'", file=sys.stderr)
        raise SystemExit(1)

    if len(matches) > 1:
        print("Multiple matches:")
        for f, s in matches:
            print(f"  [{s}] {f.name}")
        return 0

    print(matches[0][0].read_text())
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Move an issue from open/ to in_progress/."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    file_path, status = find_issue_file(proj_dir, args.id_or_keyword)
    issue_id = issue_id_from_filename(file_path.name)

    if status == "in_progress":
        print(f"#{issue_id:03d} is already in progress")
        return 0
    if status == "closed":
        print(f"error: #{issue_id:03d} is closed. Use reopen first.", file=sys.stderr)
        raise SystemExit(1)
    if status != "open":
        print(f"error: #{issue_id:03d} is in '{status}', expected open", file=sys.stderr)
        raise SystemExit(1)

    dest = proj_dir / "in_progress" / file_path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    file_path.rename(dest)

    print(f"#{issue_id:03d} now in progress")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    """Move an issue to closed/ and update frontmatter."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    file_path, status = find_issue_file(proj_dir, args.id_or_keyword)
    issue_id = issue_id_from_filename(file_path.name)

    if status == "closed":
        print(f"#{issue_id:03d} is already closed")
        return 0

    text = file_path.read_text()
    fm, body = parse_frontmatter(text)

    fm["closed"] = datetime.date.today().isoformat()
    if args.commit:
        fm["commit"] = args.commit
    if args.decision:
        body = replace_section(body, "decision", args.decision)
    if args.fix:
        body = replace_section(body, "fix", args.fix)

    dest = proj_dir / "closed" / file_path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_issue_file(dest, fm, body)
    file_path.unlink()

    print(f"Closed #{issue_id:03d}")
    return 0


def cmd_close_quickfix(args: argparse.Namespace) -> int:
    """Check all items in a quickfix section and move it to Closed."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    qf_path = proj_dir / "quickfixes.md"
    if not qf_path.exists():
        print(f"error: quickfixes.md not found at {qf_path}", file=sys.stderr)
        raise SystemExit(1)

    content = qf_path.read_text()
    keyword = args.keyword.lower()

    open_marker = "## Open"
    closed_marker = "## Closed"
    open_idx = content.find(open_marker)
    closed_idx = content.find(closed_marker)

    if open_idx == -1:
        print("error: quickfixes.md missing '## Open' section", file=sys.stderr)
        raise SystemExit(1)
    if closed_idx == -1:
        print("error: quickfixes.md missing '## Closed' section", file=sys.stderr)
        raise SystemExit(1)

    open_block = content[open_idx + len(open_marker) : closed_idx]
    closed_block = content[closed_idx + len(closed_marker) :]

    section_pattern = re.compile(r"(### [^\n]+\n(?:(?!### ).*\n?)*)", re.MULTILINE)
    sections = section_pattern.findall(open_block)
    preamble_end = open_block.find("###") if "###" in open_block else len(open_block)
    preamble = open_block[:preamble_end]

    matched: list[str] = []
    remaining: list[str] = []
    for sec in sections:
        if keyword in sec.split("\n")[0].lower():
            matched.append(sec)
        else:
            remaining.append(sec)

    if not matched:
        print(f"error: no open quickfix section matching '{args.keyword}'", file=sys.stderr)
        raise SystemExit(1)

    today = datetime.date.today().isoformat()
    checked: list[str] = []
    for sec in matched:
        lines = sec.replace("- [ ]", "- [x]").splitlines()
        new_lines = []
        for line in lines:
            if line.strip().startswith("- [x]") and f"({today})" not in line:
                line = f"{line} ({today})"
            new_lines.append(line)
        checked.append("\n".join(new_lines))

    new_content = (
        content[:open_idx]
        + open_marker
        + preamble
        + "".join(remaining)
        + closed_marker
        + "\n"
        + "".join(checked)
        + closed_block
    )
    qf_path.write_text(new_content)

    for sec in matched:
        header = sec.split("\n")[0].strip("# ").strip()
        print(f"Closed quickfix: {header}")
    return 0


def cmd_reopen(args: argparse.Namespace) -> int:
    """Move an issue from closed/ to open/."""
    config = load_config()
    proj_name, _ = resolve_project(config, args.project)
    proj_dir = project_issues_dir(config, proj_name)

    # Only look in closed/
    closed_dir = proj_dir / "closed"
    matches: list[Path] = []
    is_numeric = args.id_or_keyword.isdigit()

    if closed_dir.exists():
        for f in closed_dir.glob("*.md"):
            if is_numeric:
                m = re.match(r"^(\d+)-", f.name)
                if m and int(m.group(1)) == int(args.id_or_keyword):
                    matches.append(f)
            elif args.id_or_keyword.lower() in f.name.lower():
                matches.append(f)

    if not matches:
        print(f"error: no closed issue found matching '{args.id_or_keyword}'", file=sys.stderr)
        raise SystemExit(1)
    if len(matches) > 1:
        print(f"error: multiple matches for '{args.id_or_keyword}':", file=sys.stderr)
        for f in matches:
            print(f"  {f.name}", file=sys.stderr)
        raise SystemExit(1)

    file_path = matches[0]
    text = file_path.read_text()
    fm, body = parse_frontmatter(text)
    fm["closed"] = None

    dest = proj_dir / "open" / file_path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_issue_file(dest, fm, body)
    file_path.unlink()

    issue_id = issue_id_from_filename(file_path.name)
    print(f"Reopened #{issue_id:03d}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Text-file-based issue tracker",
    )
    parser.add_argument("--project", metavar="NAME", help="Override project resolution")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # init
    p_init = sub.add_parser("init", help="Initialize a new project")
    p_init.add_argument("name", nargs="?", help="Project name (default: cwd basename)")
    p_init.add_argument("--issues-root", metavar="PATH", help="Top-level issues directory")
    p_init.add_argument("--packages", metavar="LIST", help="Comma-separated package names")

    # create
    p_create = sub.add_parser("create", help="Create a new issue")
    p_create.add_argument("severity", choices=SEVERITIES, help="Issue severity")
    p_create.add_argument("title", help="Issue title")
    p_create.add_argument("--package", "-p", metavar="PKG")
    p_create.add_argument("--component", "-c", metavar="COMP")
    p_create.add_argument("--summary", "-s", metavar="TEXT", help="One-line summary (default: title)")
    p_create.add_argument("--problem", metavar="CONTENT")
    p_create.add_argument("--analysis", metavar="CONTENT")

    # quickfix
    p_qf = sub.add_parser("quickfix", help="Add a quickfix entry")
    p_qf.add_argument("title", help="Quickfix title")
    p_qf.add_argument("--package", "-p", metavar="PKG")
    p_qf.add_argument("--items", nargs="+", required=True, metavar="ITEM",
                       help="Items as 'file:line=description'")

    # update
    p_upd = sub.add_parser("update", help="Update an issue section (reads stdin)")
    p_upd.add_argument("id", metavar="ID", help="Issue number or keyword")
    p_upd.add_argument("--section", required=True, choices=SECTIONS)

    # list
    p_list = sub.add_parser("list", help="List issues")
    p_list.add_argument("--status", choices=("open", "in_progress", "closed", "all"))
    p_list.add_argument("--package", "-p", metavar="PKG")
    p_list.add_argument("--severity", choices=SEVERITIES)

    # search
    p_search = sub.add_parser("search", help="Search across all issues")
    p_search.add_argument("query", help="Search query (case-insensitive)")

    # show
    p_show = sub.add_parser("show", help="Show full issue content")
    p_show.add_argument("id_or_keyword", metavar="ID")

    # start
    p_start = sub.add_parser("start", help="Move issue to in_progress")
    p_start.add_argument("id_or_keyword", metavar="ID")

    # close
    p_close = sub.add_parser("close", help="Close an issue")
    p_close.add_argument("id_or_keyword", metavar="ID")
    p_close.add_argument("--commit", metavar="HASH")
    p_close.add_argument("--decision", metavar="CONTENT")
    p_close.add_argument("--fix", metavar="CONTENT")

    # close-quickfix
    p_cqf = sub.add_parser("close-quickfix", help="Close a quickfix section")
    p_cqf.add_argument("keyword")

    # reopen
    p_reopen = sub.add_parser("reopen", help="Reopen a closed issue")
    p_reopen.add_argument("id_or_keyword", metavar="ID")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "init": cmd_init,
    "create": cmd_create,
    "quickfix": cmd_quickfix,
    "update": cmd_update,
    "list": cmd_list,
    "search": cmd_search,
    "show": cmd_show,
    "start": cmd_start,
    "close": cmd_close,
    "close-quickfix": cmd_close_quickfix,
    "reopen": cmd_reopen,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        print(f"error: unknown command '{args.command}'", file=sys.stderr)
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
