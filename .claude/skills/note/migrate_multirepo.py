#!/usr/bin/env python3
"""One-shot vault migration for the note-skill multi-repo redesign.

Rewrites every note's frontmatter to the new schema:
  - stamp `repo`     (inference: area export -> forge, tales -> tales, else composite)
  - remap `area`     (old repo-identifier areas export/tales -> cross-cutting)
  - purge `tags`     (keep only `planning-*`; drop everything else)
  - promote forward  (`forward-note` tag -> `forward: true` field)
  - split findings' `discovered-in` -> `discovered-in` (context) + `batch` (slug);
    unset -> `other` / `legacy`

Standalone one-shot (NOT a cli.py subcommand): it runs BEFORE the new cli.py ships,
so it cannot depend on the new code. Kept in-tree for history after it runs.

Dry-run by default (prints per-note diff + summary, writes nothing).
Pass --apply to write.

    python3 migrate_multirepo.py            # dry run
    python3 migrate_multirepo.py --apply    # write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# --- Inline registry (script must not read the vault repos-map; that lands at cutover) ---

# Areas that were really repo identifiers, not areas.
REPO_IDENTIFIER_AREAS = {"export": "forge", "tales": "tales"}

# Widened controlled context vocabulary for discovered-in (going forward).
VALID_CONTEXTS = {"qa", "code-review", "arch-design", "arch-review", "planning", "other"}

# Canonical leading field order for readable frontmatter.
LEADING_ORDER = [
    "type", "status", "created", "updated",
    "repo", "area",
    "severity", "kind", "priority",
    "discovered-in", "batch", "forward",
    "tags", "related-notes", "related-code",
]

NOTE_FOLDERS = ["findings", "features", "questions", "retros", "decisions", "research"]


def load_vault_path() -> Path:
    cfg = json.loads((Path.home() / ".config" / "note.json").read_text())
    return Path(cfg["vault_path"])


def infer_repo(area: str | None) -> str:
    if area in REPO_IDENTIFIER_AREAS:
        return REPO_IDENTIFIER_AREAS[area]
    return "composite"


def remap_area(area: str | None) -> str | None:
    if area in REPO_IDENTIFIER_AREAS:
        return "cross-cutting"
    return area


def migrate_tags(tags: list[str]) -> tuple[list[str], bool]:
    """Return (kept_tags, had_forward). Keep only planning-* tags."""
    had_forward = "forward-note" in tags
    kept = [t for t in tags if isinstance(t, str) and t.startswith("planning-")]
    return kept, had_forward


def split_discovered_in(value: str | None) -> tuple[str, str | None]:
    """Return (context, batch). Unset -> ('other', 'legacy')."""
    if not value:
        return "other", "legacy"
    if "__" in value:
        context, batch = value.split("__", 1)
        return context, (batch or None)
    return value, None


def reorder(fm: dict) -> dict:
    out: dict = {}
    for key in LEADING_ORDER:
        if key in fm:
            out[key] = fm[key]
    for key, val in fm.items():
        if key not in out:
            out[key] = val
    return out


def split_frontmatter(text: str) -> tuple[dict | None, str, str]:
    """Return (frontmatter_dict | None, raw_fm_text, body). None if no/invalid fm."""
    if not text.startswith("---"):
        return None, "", text
    lines = text.split("\n")
    # find closing '---'
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "", text
    raw_fm = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    try:
        fm = yaml.safe_load(raw_fm)
    except yaml.YAMLError:
        return None, raw_fm, body
    if not isinstance(fm, dict):
        return None, raw_fm, body
    return fm, raw_fm, body


def migrate_note(fm: dict) -> tuple[dict, list[str]]:
    """Return (new_fm, list-of-change-descriptions)."""
    changes: list[str] = []
    new = dict(fm)

    old_area = new.get("area")
    ntype = new.get("type")

    # repo stamp
    repo = infer_repo(old_area)
    new["repo"] = repo
    changes.append(f"repo := {repo}")

    # area remap
    new_area = remap_area(old_area)
    if new_area != old_area:
        new["area"] = new_area
        changes.append(f"area {old_area!r} -> {new_area!r}")

    # tags purge + forward promotion
    raw_tags = new.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    kept, had_forward = migrate_tags(raw_tags)
    dropped = [t for t in raw_tags if t not in kept]
    if dropped:
        changes.append(f"tags drop {dropped} keep {kept}")
    if kept:
        new["tags"] = kept
    else:
        new.pop("tags", None)
    if had_forward:
        new["forward"] = True
        changes.append("forward := true (was forward-note tag)")

    # findings: discovered-in split
    if ntype == "finding":
        context, batch = split_discovered_in(new.get("discovered-in"))
        old_di = new.get("discovered-in")
        new["discovered-in"] = context
        if batch is not None:
            new["batch"] = batch
        if context not in VALID_CONTEXTS:
            changes.append(f"WARN discovered-in context {context!r} not in widened vocab")
        if old_di != context or batch is not None:
            changes.append(f"discovered-in {old_di!r} -> ctx={context!r} batch={batch!r}")

    return reorder(new), changes


def render(fm: dict, body: str) -> str:
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{dumped}---\n{body.lstrip(chr(10))}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args(argv)

    vault = load_vault_path()
    total = changed = skipped = 0
    repo_counts: dict[str, int] = {}

    for folder in NOTE_FOLDERS:
        d = vault / folder
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.md")):
            total += 1
            text = path.read_text(encoding="utf-8")
            fm, _raw, body = split_frontmatter(text)
            if fm is None:
                skipped += 1
                print(f"SKIP  {folder}/{path.name}: no/invalid frontmatter")
                continue
            new_fm, changes = migrate_note(fm)
            repo_counts[new_fm["repo"]] = repo_counts.get(new_fm["repo"], 0) + 1
            if changes:
                changed += 1
                print(f"\n{folder}/{path.name}")
                for c in changes:
                    print(f"    {c}")
            if args.apply:
                path.write_text(render(new_fm, body), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"{'APPLIED' if args.apply else 'DRY RUN'}: {total} notes, {changed} changed, {skipped} skipped")
    print(f"repo distribution: {dict(sorted(repo_counts.items()))}")
    if not args.apply:
        print("Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
