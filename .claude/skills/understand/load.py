#!/usr/bin/env python3
"""Render a named context bundle for the /understand skill.

A bundle is a markdown file at <project>/.claude/understand/<area>.md. Its
frontmatter names the documents that orient an agent working in that area; its
body carries prose that lives nowhere else. This script is invoked from
SKILL.md at skill-load time via `!` substitution, so its stdout becomes the
skill's context.

    load.py <project_dir>            list available bundles
    load.py <project_dir> <area>     render one bundle
    load.py <project_dir> --field K  print the value of repo-shape key K

Design constraints:
  * Stdlib only. A repo adopting /understand installs nothing.
  * Paths come from argv, never from the process cwd — the shell that runs
    this inherits an ambient working directory that drifts during a session.
  * A missing document is rendered as a visible error, never silently omitted.
"""

from __future__ import annotations

import os
import re
import sys

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RANGE = re.compile(r"^(\d+)-(\d+)$")

# Frontmatter keys describing the repo's shape rather than an area's reading
# list. A bundle declaring one states a fact about where this repo keeps things,
# so a skill can be written once and run against repos laid out differently.
# Rendered with the bundle, and readable on its own via `--field` by skills whose
# context posture forbids loading a whole bundle.
SHAPE_FIELDS = {
    "subsystem-docs": "Per-subsystem architecture docs live at",
}


def bundles_dir(project_dir: str) -> str:
    return os.path.join(project_dir, ".claude", "understand")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split leading `---` frontmatter from the body.

    Supports `key: value` and block scalars (`key: |`) whose indented lines
    are returned as a list of stripped strings. Deliberately not a YAML parser
    — the format is constrained so adopters need no dependency.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        return {}, text

    head, body = lines[1:close], "\n".join(lines[close + 1 :])
    meta: dict[str, object] = {}
    i = 0
    while i < len(head):
        line = head[i]
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value in ("|", ">"):
            block = []
            i += 1
            while i < len(head) and (not head[i].strip() or head[i][:1] in (" ", "\t")):
                if head[i].strip():
                    block.append(head[i].strip())
                i += 1
            meta[key] = block
        else:
            meta[key] = value
            i += 1
    return meta, body.strip("\n")


def parse_entry(line: str) -> tuple[str, bool, list[tuple[int, int]], list[str]]:
    """Parse one context line: `path [outline] [#anchor ...] [N-M ...]`."""
    tokens = line.split()
    path, outline, ranges, anchors = tokens[0], False, [], []
    for token in tokens[1:]:
        if token == "outline":
            outline = True
            continue
        if token.startswith("#"):
            anchors.append(token[1:])
            continue
        match = RANGE.match(token)
        if not match:
            raise ValueError(f"unrecognised modifier {token!r} on context entry {path!r}")
        start, end = int(match.group(1)), int(match.group(2))
        if start > end:
            raise ValueError(f"inverted range {token!r} on context entry {path!r}")
        ranges.append((start, end))
    return path, outline, ranges, anchors


def slugify(title: str) -> str:
    """`## Snapshot / Resume` → `snapshot-resume`."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")


def heading_spans(text: str) -> list[tuple[int, int, str, int]]:
    """Return (line, level, title, end_line) for every heading outside fenced code.

    A heading's span runs to the line before the next heading of the same or
    higher level, so selecting one selects its subsections too.
    """
    lines = text.split("\n")
    headings: list[tuple[int, int, str]] = []
    fence = ""
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = ""
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            continue
        match = HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2).strip()))

    total = len(lines)
    spans = []
    for index, (number, level, title) in enumerate(headings):
        end = total
        for next_number, next_level, _ in headings[index + 1 :]:
            if next_level <= level:
                end = next_number - 1
                break
        spans.append((number, level, title, end))
    return spans


def resolve_anchors(text: str, anchors: list[str], path: str) -> list[tuple[int, int]]:
    """Map `#heading-slug` selectors onto line ranges.

    Raises ValueError naming the offending anchor when it matches no heading or
    more than one — a renamed heading must fail loudly, not silently load the
    wrong text.
    """
    spans = heading_spans(text)
    resolved = []
    for anchor in anchors:
        matches = [(s, e, t) for s, _, t, e in spans if slugify(t) == anchor]
        if not matches:
            matches = [(s, e, t) for s, _, t, e in spans if slugify(t).startswith(anchor)]
        if not matches:
            raise ValueError(
                f"anchor #{anchor} matches no heading in {path} — it was renamed or removed"
            )
        if len(matches) > 1:
            names = ", ".join(f"#{slugify(t)} (line {s})" for s, _, t in matches)
            raise ValueError(f"anchor #{anchor} is ambiguous in {path}: matches {names}")
        resolved.append((matches[0][0], matches[0][1]))
    return resolved


def build_outline(text: str) -> str:
    """Emit `START-END  ## Heading` for every heading outside fenced code."""
    rendered = []
    for number, level, title, end in heading_spans(text):
        indent = "  " * (level - 1)
        rendered.append(f"{number:>5}-{end:<5} {indent}{'#' * level} {title}")
    return "\n".join(rendered)


def slice_lines(text: str, ranges: list[tuple[int, int]]) -> str:
    lines = text.split("\n")
    chunks = []
    for start, end in ranges:
        chunks.append("\n".join(lines[start - 1 : end]))
    return "\n\n".join(chunks)


def load_entry(project_dir: str, line: str) -> tuple[str, bool, list[tuple[int, int]], str, str]:
    """Resolve one context entry against disk.

    Returns (path, outline, spans, text, error). A non-empty error means the
    entry could not be resolved and nothing should be rendered from it.
    """
    try:
        path, outline, ranges, anchors = parse_entry(line)
    except ValueError as exc:
        return line.split()[0] if line.split() else line, False, [], "", str(exc)

    absolute = os.path.join(project_dir, path)
    try:
        with open(absolute, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        return path, False, [], "", f"could not read this document: {exc}"

    try:
        spans = resolve_anchors(text, anchors, path) + ranges
    except ValueError as exc:
        return path, outline, [], text, str(exc)
    return path, outline, spans, text, ""


def render_entry(project_dir: str, line: str) -> tuple[str, str]:
    """Render one context entry. Returns (rendered_text, withheld_note)."""
    path, outline, spans, text, error = load_entry(project_dir, line)
    if error:
        return f"===== {path} =====\nERROR: {error}\n", ""

    total = len(text.split("\n"))
    sections = []
    withheld = ""

    if spans:
        shown = ", ".join(f"{s}-{e}" for s, e in spans)
        sections.append(f"===== {path} (lines {shown} of {total}) =====\n{slice_lines(text, spans)}")
    if outline:
        sections.append(
            f"===== {path} (OUTLINE ONLY — {total} lines, not loaded) =====\n"
            "Read a section by its line range. An anchor for a bundle is its heading "
            "lowercased\nwith every run of non-alphanumerics replaced by `-` "
            "(`## Status legend` → `#status-legend`).\n\n" + build_outline(text)
        )
        withheld = path
    if not spans and not outline:
        sections.append(f"===== {path} ({total} lines) =====\n{text.rstrip()}")

    return "\n\n".join(sections) + "\n", withheld


def check_bundles(project_dir: str) -> int:
    """Resolve every selector in every bundle. Exit non-zero on any failure."""
    areas = available_areas(project_dir)
    if not areas:
        print(f"No context bundles in {bundles_dir(project_dir)} — nothing to check.")
        return 0

    failures = 0
    for area in areas:
        with open(os.path.join(bundles_dir(project_dir), f"{area}.md"), encoding="utf-8") as fh:
            meta, _ = parse_frontmatter(fh.read())
        entries = meta.get("context", [])
        if isinstance(entries, str):
            entries = [entries]
        if not entries:
            print(f"FAIL {area}: bundle declares no `context:` block")
            failures += 1
            continue
        for entry in entries:
            path, _, _, _, error = load_entry(project_dir, str(entry))
            if error:
                print(f"FAIL {area}: {path}: {error}")
                failures += 1
            else:
                print(f"ok   {area}: {path}")

    print(f"\n{failures} failure(s) across {len(areas)} bundle(s).")
    return 1 if failures else 0


def declared_shape(project_dir: str, key: str) -> str:
    """Return the value of repo-shape key `key`, or "" if no bundle declares it.

    Shape keys are repo-level facts, so the first bundle declaring one wins and
    the rest are not consulted. Two bundles disagreeing is a lint concern for
    `--check`, not a resolution rule here.
    """
    for area in available_areas(project_dir):
        path = os.path.join(bundles_dir(project_dir), f"{area}.md")
        with open(path, encoding="utf-8") as handle:
            meta, _ = parse_frontmatter(handle.read())
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def print_field(project_dir: str, key: str) -> int:
    """Print one repo-shape value. The lookup for skills that load no bundle."""
    if key not in SHAPE_FIELDS:
        known = ", ".join(sorted(SHAPE_FIELDS))
        print(f"ERROR: {key!r} is not a repo-shape key. Known keys: {known}")
        return 1
    value = declared_shape(project_dir, key)
    if not value:
        print(f"ERROR: no context bundle in this repo declares {key!r}.")
        return 1
    print(value)
    return 0


def available_areas(project_dir: str) -> list[str]:
    directory = bundles_dir(project_dir)
    if not os.path.isdir(directory):
        return []
    return sorted(f[:-3] for f in os.listdir(directory) if f.endswith(".md"))


def resolve_area(project_dir: str, requested: str) -> tuple[str, str]:
    """Map a requested area onto a defined one.

    Returns (resolved_area, note). An exact match resolves silently. A unique
    prefix or substring match resolves with a note saying so — a near-miss is a
    typo, not a reason to make the caller start over. Ambiguous or absent
    matches return ("", "").
    """
    areas = available_areas(project_dir)
    if requested in areas:
        return requested, ""

    lowered = requested.lower()
    for rule in (lambda a: a.lower().startswith(lowered), lambda a: lowered in a.lower()):
        matches = [a for a in areas if rule(a)]
        if len(matches) == 1:
            return matches[0], f"(no bundle named {requested!r} — loaded {matches[0]!r})"
    return "", ""


def list_bundles(project_dir: str) -> int:
    directory = bundles_dir(project_dir)
    if not os.path.isdir(directory):
        print(
            f"No context bundles in this repo — {directory} does not exist.\n\n"
            "To add one, create that directory and copy the template at\n"
            f"{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.md')}\n"
            "to `<area>.md`, then edit its `context:` block."
        )
        return 0

    names = sorted(f for f in os.listdir(directory) if f.endswith(".md"))
    if not names:
        print(f"No context bundles defined in {directory}.")
        return 0

    print("Available context bundles — invoke with `/understand <area>`:\n")
    for name in names:
        area = name[:-3]
        meta, _ = parse_frontmatter(open(os.path.join(directory, name), encoding="utf-8").read())
        description = meta.get("description", "")
        print(f"  {area:<20} {description}")
    print(
        "\nNOTHING HAS BEEN LOADED. No context for any area is in your context yet.\n"
        "Invoke `/understand <area>` again with one of the names above. Do NOT load\n"
        "these documents by hand — this skill decides which parts of which files to\n"
        "load, and reading them yourself defeats that."
    )
    return 0


def render_bundle(project_dir: str, requested: str) -> int:
    area, note = resolve_area(project_dir, requested)
    if not area:
        print(f"No context bundle named {requested!r}.\n")
        return list_bundles(project_dir)

    path = os.path.join(bundles_dir(project_dir), f"{area}.md")
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    if note:
        print(note + "\n")

    meta, body = parse_frontmatter(raw)
    entries = meta.get("context", [])
    if isinstance(entries, str):
        entries = [entries]

    print(f"# Context loaded: {area}\n")
    for key, label in SHAPE_FIELDS.items():
        value = meta.get(key)
        if isinstance(value, str) and value:
            print(f"{label} `{value}`.\n")
    if body:
        print(body + "\n")

    withheld = []
    for line in entries:
        rendered, held = render_entry(project_dir, str(line))
        print(rendered)
        if held:
            withheld.append(held)

    print("---\n")
    print(
        "That is your orientation for this area. It is context, not instruction — it "
        "says\nwhat this repo is and where things live. What you may produce, and how, "
        "comes from\nthe task you were asked to do.\n\n"
        "Everything above is already in your context. Do not re-read these files."
    )
    if withheld:
        print(
            "\nThe documents below were loaded as OUTLINES ONLY — their content is NOT "
            "in your\ncontext:\n"
        )
        for path in withheld:
            print(f"  - {path}")
        print(
            "\nEach outline lists every section with its line range. Before designing "
            "against\nanything one of those sections covers, Read that range. Do not "
            "assume a section's\ncontent from its heading, and do not read the whole "
            "file."
        )
    return 0


def main() -> int:
    argv = [a for a in sys.argv[1:] if a != "--check"]
    if not argv:
        print("ERROR: /understand loader requires a project directory argument.")
        return 1
    project_dir = argv[0]
    if "--check" in sys.argv:
        return check_bundles(project_dir)
    if len(argv) > 1 and argv[1] == "--field":
        if len(argv) < 3 or not argv[2].strip():
            print("ERROR: --field requires a key.")
            return 1
        return print_field(project_dir, argv[2].strip())
    area = argv[1].strip() if len(argv) > 1 and argv[1].strip() else ""
    return render_bundle(project_dir, area) if area else list_bundles(project_dir)


if __name__ == "__main__":
    sys.exit(main())
