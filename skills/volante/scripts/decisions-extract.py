#!/usr/bin/env python3
"""Extract the last N decision events from decisions-YYYY-MM.jsonl.

Usage:
    decisions-extract.py [--file PATH] [--last N] [--format json|jsonl]

Defaults: current-month jsonl under <repo_root>/journal/, last 20 events, format json.
Primary consumer: v0.15.0 監督 AI subagent (SKILL.md, issue #16).

Locates the repo root by walking up from CWD until a directory containing `journal/`
is found. Passes through malformed JSON lines with a warning instead of aborting.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / "journal").is_dir():
            return p
    return None


def default_path() -> Path:
    root = find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not find a journal/ directory from CWD upwards")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return root / "journal" / f"decisions-{month}.jsonl"


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"error: file not found: {path}")
    events: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"warning: parse error at line {i} of {path}: {e}", file=sys.stderr)
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, help="path to jsonl (default: journal/decisions-<current-month>.jsonl)")
    ap.add_argument("--last", type=int, default=20, help="number of most recent events (default: 20)")
    ap.add_argument("--format", choices=["json", "jsonl"], default="json", help="output format (default: json)")
    args = ap.parse_args()

    path = args.file if args.file else default_path()
    events = read_events(path)
    tail = events[-args.last:] if args.last > 0 else events

    if args.format == "json":
        json.dump(tail, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for ev in tail:
            sys.stdout.write(json.dumps(ev, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
