#!/usr/bin/env python3
"""Add / remove / edit / list volante epic Specs + the journal/goals.md index row.

Backs `/volante-epic` (issue #24). Two files move together per epic:
  - journal/specs/<slug>.json   (Spec schema v1.2, see skills/volante/templates/spec-template.json)
  - journal/goals.md            (index row; primary key here is the `session (役割名)` cell,
                                  which this tool always sets to the slug verbatim so add/edit/
                                  remove can find the row unambiguously)

Validation is schema-driven (reads skills/volante/templates/spec-template.json directly) but is a
minimal hand-rolled subset of JSON Schema draft2020 (type/required/additionalProperties/properties/
minLength/minItems/items only) — no `jsonschema` package is installed in this environment, and the
spec schema only uses that subset. Not a general-purpose validator.

This script only writes files; it does not `git add`/`commit`/`push` (the caller — SKILL.md's
conversational flow — does that, matching the convention used by dashboard-generate.py).

Usage:
    epic_tool.py add --slug SLUG --repo REPO --goal GOAL --criteria C [--criteria C ...] \
        --kpi-gid GID --kpi-name NAME --source SOURCE [--epic-label LABEL] [--repo-root PATH]
    epic_tool.py remove SLUG [--repo-root PATH]
    epic_tool.py edit SLUG [--repo REPO] [--source SOURCE] [--goal GOAL] \
        [--criteria C [--criteria C ...]] [--kpi-gid GID] [--kpi-name NAME] \
        [--epic-label LABEL] [--clear-epic-label] [--repo-root PATH]
    epic_tool.py list [--repo-root PATH]
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

GOALS_HEADER_CELLS = ["repo", "正本", "session (役割名)", "ゴール 1 行", "優先度 (konuma 所有)", "登録日"]
UNSET_PRIORITY = "未指定"


# ===== repo root / paths =====

def find_repo_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / "journal").is_dir() and (p / ".claude-plugin").is_dir():
            return p
    return None


def resolve_root(arg_root: Path | None) -> Path:
    root = arg_root or find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not locate volante repo root (need journal/ + .claude-plugin/); pass --repo-root")
    return root


def spec_path(root: Path, slug: str) -> Path:
    return root / "journal" / "specs" / f"{slug}.json"


def archive_path(root: Path, slug: str) -> Path:
    return root / "journal" / "specs" / "_archive" / f"{slug}.json"


def schema_path(root: Path) -> Path:
    return root / "skills" / "volante" / "templates" / "spec-template.json"


def goals_path(root: Path) -> Path:
    return root / "journal" / "goals.md"


SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        sys.exit(f"error: slug '{slug}' is not kebab-case (expected pattern: {SLUG_RE.pattern})")


# ===== minimal schema-driven validation (see module docstring) =====

def validate_node(instance, schema: dict, path: str, errors: list[str]) -> None:
    t = schema.get("type")
    if t == "object":
        if not isinstance(instance, dict):
            errors.append(f"{path}: expected object, got {type(instance).__name__}")
            return
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(props))
            if extra:
                errors.append(f"{path}: unexpected properties: {extra}")
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property '{req}'")
        for key, subschema in props.items():
            if key in instance:
                validate_node(instance[key], subschema, f"{path}.{key}" if path else key, errors)
    elif t == "array":
        if not isinstance(instance, list):
            errors.append(f"{path}: expected array, got {type(instance).__name__}")
            return
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(instance)}")
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(instance):
                validate_node(item, items_schema, f"{path}[{i}]", errors)
    elif t == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}: expected string, got {type(instance).__name__}")
            return
        min_len = schema.get("minLength")
        if min_len is not None and len(instance) < min_len:
            errors.append(f"{path}: string shorter than minLength {min_len}")
    # other/unset types: not used by spec-template.json today, so left unchecked.


def validate_spec(root: Path, spec: dict) -> None:
    sp = schema_path(root)
    if not sp.exists():
        sys.exit(f"error: schema not found at {sp}")
    schema = json.loads(sp.read_text(encoding="utf-8"))
    errors: list[str] = []
    validate_node(spec, schema, "spec", errors)
    if errors:
        sys.exit("error: spec fails schema validation (" + str(sp) + "):\n  " + "\n  ".join(errors))


# ===== goals.md table I/O =====

def esc_cell(text: str) -> str:
    """Keep a value safe inside one markdown table cell (no literal newlines/pipes)."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def find_table_bounds(lines: list[str]) -> tuple[int, int]:
    """Return (start, end) half-open range of contiguous '|'-prefixed lines (header+sep+rows)."""
    start = None
    for i, line in enumerate(lines):
        if line.startswith("|"):
            start = i
            break
    if start is None:
        sys.exit("error: no markdown table found in goals.md")
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return start, end


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-+:?", c) for c in cells)


def build_row(cells: list[str]) -> str:
    return "| " + " | ".join(esc_cell(c) for c in cells) + " |"


def load_goals_rows(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Return [(line_index, cells)] for data rows (header + separator excluded)."""
    start, end = find_table_bounds(lines)
    rows = []
    for i in range(start, end):
        cells = split_row(lines[i])
        if cells == GOALS_HEADER_CELLS or is_sep_row(cells):
            continue
        rows.append((i, cells))
    return rows


def add_goals_row(root: Path, cells: list[str]) -> None:
    gp = goals_path(root)
    lines = gp.read_text(encoding="utf-8").splitlines()
    start, end = find_table_bounds(lines)
    lines.insert(end, build_row(cells))
    gp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_goals_rows_by_slug(root: Path, slug: str) -> list[tuple[int, list[str]]]:
    lines = goals_path(root).read_text(encoding="utf-8").splitlines()
    return [(i, cells) for i, cells in load_goals_rows(lines) if len(cells) > 2 and cells[2] == slug]


def remove_goals_row_by_slug(root: Path, slug: str) -> int:
    gp = goals_path(root)
    lines = gp.read_text(encoding="utf-8").splitlines()
    matches = [i for i, cells in load_goals_rows(lines) if len(cells) > 2 and cells[2] == slug]
    if not matches:
        return 0
    if len(matches) > 1:
        sys.exit(f"error: {len(matches)} goals.md rows match session '{slug}' (ambiguous); edit goals.md by hand")
    del lines[matches[0]]
    gp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1


def update_goals_row_by_slug(root: Path, slug: str, updates: dict[int, str]) -> None:
    """updates: {column_index (0-based into GOALS_HEADER_CELLS): new_value}."""
    gp = goals_path(root)
    lines = gp.read_text(encoding="utf-8").splitlines()
    matches = find_goals_rows_by_slug(root, slug)
    if not matches:
        print(f"warning: no goals.md row found for session '{slug}' (spec-only edit)", file=sys.stderr)
        return
    if len(matches) > 1:
        sys.exit(f"error: {len(matches)} goals.md rows match session '{slug}' (ambiguous); edit goals.md by hand")
    idx, cells = matches[0]
    for col, val in updates.items():
        cells[col] = val
    lines[idx] = build_row(cells)
    gp.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===== subcommands =====

def cmd_add(args: argparse.Namespace) -> None:
    root = resolve_root(args.repo_root)
    validate_slug(args.slug)
    sp = spec_path(root, args.slug)
    if sp.exists():
        sys.exit(f"error: spec already exists: {sp} (use `edit` instead)")
    if find_goals_rows_by_slug(root, args.slug):
        sys.exit(f"error: goals.md already has a row for session '{args.slug}'")

    spec: dict = {
        "goal": args.goal,
        "acceptance_criteria": args.criteria,
    }
    if args.kpi_gid or args.kpi_name:
        spec["kpi_sheet_tab"] = {"gid": args.kpi_gid or "", "name": args.kpi_name or ""}
    if args.epic_label:
        spec["epic_label"] = args.epic_label

    validate_spec(root, spec)  # kpi_sheet_tab required -> rejects here if omitted (issue #23 dependency)

    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    add_goals_row(root, [
        args.repo, args.source, args.slug, args.goal, UNSET_PRIORITY, date.today().isoformat(),
    ])
    print(f"added {sp}")
    print(f"added goals.md row for session '{args.slug}'")


def cmd_remove(args: argparse.Namespace) -> None:
    root = resolve_root(args.repo_root)
    sp = spec_path(root, args.slug)
    if not sp.exists():
        sys.exit(f"error: no such spec: {sp}")
    ap = archive_path(root, args.slug)
    ap.parent.mkdir(parents=True, exist_ok=True)
    sp.rename(ap)
    removed = remove_goals_row_by_slug(root, args.slug)
    print(f"archived {sp} -> {ap}")
    print(f"removed {removed} goals.md row(s) for session '{args.slug}'")


def cmd_edit(args: argparse.Namespace) -> None:
    root = resolve_root(args.repo_root)
    sp = spec_path(root, args.slug)
    if not sp.exists():
        sys.exit(f"error: no such spec: {sp} (use `add` instead)")
    spec = json.loads(sp.read_text(encoding="utf-8"))

    changed = False
    if args.goal is not None:
        spec["goal"] = args.goal
        changed = True
    if args.criteria:
        spec["acceptance_criteria"] = args.criteria
        changed = True
    if args.kpi_gid is not None or args.kpi_name is not None:
        tab = dict(spec.get("kpi_sheet_tab") or {})
        if args.kpi_gid is not None:
            tab["gid"] = args.kpi_gid
        if args.kpi_name is not None:
            tab["name"] = args.kpi_name
        spec["kpi_sheet_tab"] = tab
        changed = True
    if args.clear_epic_label:
        spec.pop("epic_label", None)
        changed = True
    elif args.epic_label is not None:
        spec["epic_label"] = args.epic_label
        changed = True

    goals_updates: dict[int, str] = {}
    if args.repo is not None:
        goals_updates[0] = args.repo
    if args.source is not None:
        goals_updates[1] = args.source
    if args.goal is not None:
        goals_updates[3] = args.goal  # keep goals.md 「ゴール 1 行」 in sync with the Spec (avoid drift)

    if not changed and not goals_updates:
        sys.exit("error: no fields to edit were given")

    if changed:
        validate_spec(root, spec)
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {sp}")
    if goals_updates:
        update_goals_row_by_slug(root, args.slug, goals_updates)
        print(f"updated goals.md row for session '{args.slug}'")


def cmd_list(args: argparse.Namespace) -> None:
    root = resolve_root(args.repo_root)
    specs_dir = root / "journal" / "specs"
    paths = sorted(p for p in specs_dir.glob("*.json"))
    if not paths:
        print("(no specs)")
        return
    goals_lines = goals_path(root).read_text(encoding="utf-8").splitlines()
    goals_rows = {cells[2]: cells for _, cells in load_goals_rows(goals_lines) if len(cells) > 2}
    for p in paths:
        slug = p.stem
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"{slug}: (invalid JSON: {e})")
            continue
        row = goals_rows.get(slug)
        repo = row[0] if row else "(no goals.md row)"
        kpi = spec.get("kpi_sheet_tab") or {}
        kpi_str = kpi.get("name", "?") if kpi else "未紐付け"
        n_criteria = len(spec.get("acceptance_criteria") or [])
        label = f" [{spec['epic_label']}]" if spec.get("epic_label") else ""
        print(f"{slug}{label}  repo={repo}  kpi={kpi_str}  criteria={n_criteria}")
        print(f"  goal: {spec.get('goal', '')}")


# ===== argparse wiring =====

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", type=Path, help="path to volante repo root (default: auto-detect from CWD)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="create a new Spec + goals.md row")
    p_add.add_argument("--slug", required=True, help="kebab-case identifier; also the goals.md session cell")
    p_add.add_argument("--repo", required=True, help="e.g. ma-navi/pitto, or a local path label like 'home'")
    p_add.add_argument("--goal", required=True)
    p_add.add_argument("--criteria", action="append", required=True, help="repeatable; at least one required")
    p_add.add_argument("--kpi-gid", help="PJCI sheet tab gid (required together with --kpi-name, issue #23)")
    p_add.add_argument("--kpi-name", help="PJCI sheet tab name")
    p_add.add_argument("--source", required=True, help="正本 URL/path (issue, PR, or goal file path)")
    p_add.add_argument("--epic-label", help="optional repo-side epic label (issue #22)")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove", help="archive a Spec + drop its goals.md row")
    p_rm.add_argument("slug")
    p_rm.set_defaults(func=cmd_remove)

    p_edit = sub.add_parser("edit", help="overwrite individual fields of an existing Spec/goals.md row")
    p_edit.add_argument("slug")
    p_edit.add_argument("--repo")
    p_edit.add_argument("--source")
    p_edit.add_argument("--goal")
    p_edit.add_argument("--criteria", action="append", help="repeatable; replaces the whole list if given")
    p_edit.add_argument("--kpi-gid")
    p_edit.add_argument("--kpi-name")
    p_edit.add_argument("--epic-label")
    p_edit.add_argument("--clear-epic-label", action="store_true")
    p_edit.set_defaults(func=cmd_edit)

    p_list = sub.add_parser("list", help="print current specs to stdout")
    p_list.set_defaults(func=cmd_list)

    return ap


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
