#!/usr/bin/env python3
"""Rebuild journal/attachments.json from `kitty @ ls` output + journal/specs/.

Usage:
    # live (invokes `kitty @ ls`)
    scripts/attachments-rebuild.py [--out journal/attachments.json]

    # from a file (offline testing, or when kitty is unreachable from this shell)
    scripts/attachments-rebuild.py --kitty-ls-json path/to/kitty-ls.json

Attach rule (`confidence` field):
  - **high**: cwd contains the spec's `owner/name` as consecutive path segments
    (unambiguous — only one repo maps to this cwd)
  - **medium**: cwd contains only the repo `name` segment (owner mismatch or unknown)
  - **low**: multiple specs match with equal top confidence — konuma disambiguation needed
    (attach to first alphabetically, `reason` lists candidates)

Windows with no matching spec go into `unattached_sessions` — these are the
"goal 設定要求" targets per SKILL.md 4. checklist.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / "journal").is_dir() and (p / ".claude-plugin").is_dir():
            return p
    return None


def load_kitty_ls(source: Path | None) -> list:
    if source is not None:
        return json.loads(source.read_text(encoding="utf-8"))
    try:
        out = subprocess.check_output(["kitty", "@", "ls"], stderr=subprocess.PIPE, timeout=10)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        sys.exit(f"error: could not run `kitty @ ls`: {e}. Pass --kitty-ls-json instead.")
    return json.loads(out)


def iter_windows(kitty_ls: list):
    for os_window in kitty_ls:
        for tab in os_window.get("tabs", []):
            for window in tab.get("windows", []):
                yield window


def is_claude_window(window: dict) -> bool:
    for proc in window.get("foreground_processes", []) or []:
        cmdline = " ".join(proc.get("cmdline", []) or [])
        if "claude" in cmdline.lower():
            return True
    return False


def foreground_cwd(window: dict) -> str:
    procs = window.get("foreground_processes", []) or []
    if not procs:
        return ""
    return procs[0].get("cwd", "") or ""


def git_branch(cwd: str) -> str:
    if not cwd or not Path(cwd).is_dir():
        return ""
    try:
        out = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def load_specs(specs_dir: Path) -> list[dict]:
    specs = []
    for path in sorted(specs_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: could not read {path}: {e}", file=sys.stderr)
            continue
        specs.append({"basename": path.stem, "repo": data.get("repo", ""), "epic": data.get("epic", {})})
    return specs


def score_spec_against_cwd(spec: dict, cwd: str) -> tuple[str, str]:
    """Return (confidence, reason) or ('', '') if no match."""
    repo = spec.get("repo", "")
    if not repo or "/" not in repo:
        return "", ""
    owner, name = repo.split("/", 1)
    cwd_norm = cwd.replace("\\", "/")
    if f"/{owner}/{name}" in cwd_norm or cwd_norm.endswith(f"/{owner}/{name}"):
        return "high", f"cwd contains owner/name: {owner}/{name}"
    if f"/{name}" in cwd_norm or cwd_norm.endswith(f"/{name}"):
        return "medium", f"cwd contains name only: {name}"
    return "", ""


def rebuild(kitty_ls: list, specs: list[dict]) -> dict:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    attachments = []
    unattached = []

    for window in iter_windows(kitty_ls):
        if not is_claude_window(window):
            continue
        window_id = f"w{window.get('id', '?')}"
        cwd = foreground_cwd(window)
        branch = git_branch(cwd)
        title = window.get("title", "") or ""

        candidates = []
        for spec in specs:
            conf, reason = score_spec_against_cwd(spec, cwd)
            if conf:
                candidates.append((conf, reason, spec))

        if not candidates:
            unattached.append({
                "window_id": window_id,
                "cwd": cwd,
                "reason": f"Spec 未登録 (cwd: {cwd or '(不明)'})",
            })
            continue

        rank = {"high": 3, "medium": 2, "low": 1}
        candidates.sort(key=lambda c: (-rank[c[0]], c[2]["basename"]))
        top_conf = candidates[0][0]
        top_matches = [c for c in candidates if c[0] == top_conf]

        chosen_conf, chosen_reason, chosen_spec = candidates[0]
        if len(top_matches) > 1:
            chosen_conf = "low"
            others = [c[2]["basename"] for c in top_matches]
            chosen_reason = f"multiple {top_conf} candidates: {', '.join(others)} — konuma disambiguation needed (defaulted to alpha-first)"

        entry = {
            "spec": chosen_spec["basename"],
            "window_id": window_id,
            "cwd": cwd,
            "confidence": chosen_conf,
            "reason": chosen_reason,
        }
        if title:
            entry["session_hint"] = title
        if branch:
            entry["branch"] = branch
        attachments.append(entry)

    return {
        "generated_at": generated_at,
        "attachments": attachments,
        "unattached_sessions": unattached,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path)
    ap.add_argument("--kitty-ls-json", type=Path, help="read kitty @ ls JSON from file (skip live)")
    ap.add_argument("--out", type=Path, help="output path (default: <repo_root>/journal/attachments.json)")
    ap.add_argument("--specs-dir", type=Path, help="specs directory (default: <repo_root>/journal/specs)")
    args = ap.parse_args()

    root = args.repo_root or find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not locate volante repo root")
    specs_dir = args.specs_dir or (root / "journal" / "specs")
    out_path = args.out or (root / "journal" / "attachments.json")

    kitty_ls = load_kitty_ls(args.kitty_ls_json)
    specs = load_specs(specs_dir)
    result = rebuild(kitty_ls, specs)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}: {len(result['attachments'])} attachments, {len(result['unattached_sessions'])} unattached")


if __name__ == "__main__":
    main()
