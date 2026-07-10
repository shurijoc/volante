#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from volante journal state.

Reads:
  - journal/specs/*.json         (Session Spec v1)
  - journal/decisions-<YYYY-MM>.jsonl (current month, last N events; issue #26/#27/#28)
  - journal/decisions-*.jsonl     (all months, globbed, for the "全期間" toggle + epic-tab filter)
  - journal/patrols.md            (last few rows)
  - journal/retro-*.md           (index + truncated body, issue #27)

Outputs:
  - journal/dashboard.html       (self-contained, JSON embedded via <script>)

Design principle (CLAUDE.md 設計原則, SKILL.md 芯 9):
  DB / サーバー不要、HTML + JSON でローカル完結。The output is a single .html
  file with embedded JSON. Open with `open journal/dashboard.html` — no server.

Status: v0.16.1 — 監督 AI 判定の詳細展開 (#26)、retro 本文の折りたたみ表示 (#27)、
前月以前の decisions ログの横断表示 (#28) を実装。
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / "journal").is_dir() and (p / ".claude-plugin").is_dir():
            return p
    return None


def load_specs(specs_dir: Path) -> list[dict]:
    specs = []
    if not specs_dir.is_dir():
        return specs
    for path in sorted(specs_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            specs.append({"session": path.stem, "spec": data})
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: could not read {path}: {e}", file=sys.stderr)
    return specs


def _parse_decisions_file(path: Path) -> list[dict]:
    """Parse one decisions-YYYY-MM.jsonl file into a list of event dicts (chronological)."""
    if not path.exists():
        return []
    events = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"warning: parse error at {path}:{i}: {e}", file=sys.stderr)
    return events


def load_recent_decisions(journal: Path, limit: int) -> list[dict]:
    """Load the current month's decisions-YYYY-MM.jsonl (unlimited if limit<=0)."""
    now_month = datetime.now(timezone.utc).strftime("%Y-%m")
    events = _parse_decisions_file(journal / f"decisions-{now_month}.jsonl")
    return events[-limit:] if limit > 0 else events


def load_all_decisions(journal: Path) -> list[dict]:
    """issue #28: glob every decisions-YYYY-MM.jsonl and concatenate in chronological
    (filename-sorted) order, so past months don't disappear once the calendar rolls over.
    Returns [] when no jsonl has ever been written (Fact 主義: 現状のまま、何も無ければ空)."""
    events = []
    for path in sorted(journal.glob("decisions-*.jsonl")):
        events.extend(_parse_decisions_file(path))
    return events


def parse_goals_md(journal: Path) -> list[dict]:
    """Parse journal/goals.md table rows into structured data.

    v0.15.3 columns: | repo | 正本 | session (役割名) | ゴール | 優先度 | 登録日 |
    """
    path = journal / "goals.md"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0] in ("repo",):
            continue
        rows.append({
            "repo": cells[0],
            "source": cells[1],
            "session_role": cells[2],
            "goal": cells[3],
            "priority": cells[4],
            "registered": cells[5],
        })
    return rows


def resolve_repo_for_spec(spec_basename: str, goals_rows: list[dict]) -> str:
    """Fuzzy match a Spec basename to a repo via goals.md.

    Convention: Spec basename starts with a short repo hint (e.g., 'pitto-kaizen'
    → hint 'pitto' matches repo 'ma-navi/pitto'). If ambiguous or unmatched,
    return empty string.
    """
    if "-" not in spec_basename:
        hint = spec_basename
    else:
        hint = spec_basename.split("-", 1)[0]
    if not hint:
        return ""
    matches = set()
    for row in goals_rows:
        repo = row.get("repo", "")
        if "/" not in repo:
            if hint in repo:
                matches.add(repo)
            continue
        owner, name = repo.split("/", 1)
        if hint == owner or hint == name or name.startswith(hint + "-") or name.startswith(hint + "_"):
            matches.add(repo)
    if len(matches) == 1:
        return next(iter(matches))
    return ""


def _gh_search_count(query: str) -> dict:
    """Run `gh api search/issues?q=<query>` and return {"count", "error"}."""
    try:
        out = subprocess.check_output(
            ["gh", "api", f"search/issues?q={query}", "--jq", ".total_count"],
            stderr=subprocess.PIPE, timeout=15,
        )
        return {"count": int(out.decode("utf-8").strip()), "error": ""}
    except FileNotFoundError:
        return {"count": None, "error": "gh CLI not found"}
    except subprocess.CalledProcessError as e:
        return {"count": None, "error": f"gh failed: {e.stderr.decode('utf-8', errors='ignore').strip()[:200]}"}
    except (subprocess.TimeoutExpired, ValueError) as e:
        return {"count": None, "error": f"{type(e).__name__}"}


def fetch_open_issue_count(repo: str, epic_label: str = "") -> dict:
    """Fetch issue progress via gh api search.

    issue #22: if `epic_label` is given, scope the count to that label and
    return open + closed counts (epic-level progress: X / (X+Y) closed).
    If `epic_label` is absent, fall back to the pre-#22 behavior (repo-wide
    open issue count) for backward compatibility with Specs that don't set
    `epic_label` yet.
    """
    if not repo or "/" not in repo:
        return {"count": None, "source": "", "error": "invalid repo"}
    if epic_label:
        open_r = _gh_search_count(f'repo:{repo}+label:"{epic_label}"+is:issue+is:open')
        closed_r = _gh_search_count(f'repo:{repo}+label:"{epic_label}"+is:issue+is:closed')
        err = open_r["error"] or closed_r["error"]
        if err or open_r["count"] is None or closed_r["count"] is None:
            return {"count": None, "open": None, "closed": None, "total": None,
                     "label": epic_label, "source": "", "error": err or "unknown error"}
        o, c = open_r["count"], closed_r["count"]
        return {
            "count": o, "open": o, "closed": c, "total": o + c, "label": epic_label,
            "source": f'gh api search/issues repo:{repo}+label:"{epic_label}"', "error": "",
        }
    r = _gh_search_count(f"repo:{repo}+is:issue+is:open")
    if r["count"] is None:
        return {"count": None, "source": "", "error": r["error"]}
    return {"count": r["count"], "source": f"gh api search/issues repo:{repo}", "error": ""}


def fetch_open_prs(repo: str, limit: int = 20) -> dict:
    """Fetch open PRs (list) via gh pr list. Returns {"prs": [...], "error": str}."""
    if not repo or "/" not in repo:
        return {"prs": [], "error": "invalid repo"}
    try:
        out = subprocess.check_output(
            ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
             "--json", "number,title,mergeStateStatus,statusCheckRollup,reviewDecision,url,isDraft,headRefName"],
            stderr=subprocess.PIPE, timeout=20,
        )
        prs = json.loads(out.decode("utf-8"))
        # Simplify statusCheckRollup to a single status
        for pr in prs:
            checks = pr.get("statusCheckRollup") or []
            if not checks:
                pr["ciSummary"] = ""
                continue
            fail = sum(1 for c in checks if (c.get("conclusion") == "FAILURE" or c.get("status") == "FAILURE"))
            pending = sum(1 for c in checks if c.get("status") in ("IN_PROGRESS", "QUEUED", "PENDING"))
            success = sum(1 for c in checks if c.get("conclusion") in ("SUCCESS", "NEUTRAL", "SKIPPED"))
            total = len(checks)
            if fail:
                pr["ciSummary"] = f"❌ {fail}/{total} fail"
            elif pending:
                pr["ciSummary"] = f"⏳ {pending}/{total} pending"
            elif success == total:
                pr["ciSummary"] = f"✓ {total} pass"
            else:
                pr["ciSummary"] = f"{success}/{total} ok"
            del pr["statusCheckRollup"]
        return {"prs": prs, "error": ""}
    except FileNotFoundError:
        return {"prs": [], "error": "gh CLI not found"}
    except subprocess.CalledProcessError as e:
        return {"prs": [], "error": f"gh failed: {e.stderr.decode('utf-8', errors='ignore').strip()[:200]}"}
    except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as e:
        return {"prs": [], "error": f"{type(e).__name__}"}


def fetch_open_issues_list(repo: str, limit: int = 30) -> dict:
    """Fetch open issue list via gh issue list."""
    if not repo or "/" not in repo:
        return {"issues": [], "error": "invalid repo"}
    try:
        out = subprocess.check_output(
            ["gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
             "--json", "number,title,url,labels,updatedAt"],
            stderr=subprocess.PIPE, timeout=20,
        )
        return {"issues": json.loads(out.decode("utf-8")), "error": ""}
    except FileNotFoundError:
        return {"issues": [], "error": "gh CLI not found"}
    except subprocess.CalledProcessError as e:
        return {"issues": [], "error": f"gh failed: {e.stderr.decode('utf-8', errors='ignore').strip()[:200]}"}
    except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as e:
        return {"issues": [], "error": f"{type(e).__name__}"}


PATROL_METRIC_PATTERNS = {
    "observed": re.compile(r"観測\s*(\d+)"),
    "idle": re.compile(r"IDLE\s*(\d+)"),
    "running": re.compile(r"RUNNING\s*(\d+)"),
    "waiting": re.compile(r"WAITING\s*(\d+)"),
    "instructed": re.compile(r"指示\s*(\d+)"),
}


def parse_patrol_summary(summary: str) -> dict:
    """Parse a patrols.md summary cell into 観測/IDLE/RUNNING/WAITING/指示 counts + memo.

    issue #22: summary is a `観測 N / IDLE N / RUNNING N / ... / <free text>` line.
    Split on "/", classify each token against the known metric patterns, and put
    any unmatched token into memo. Fact 主義: if nothing matches (format changed
    or one-off note), leave all counts blank and dump the whole line into memo
    rather than guessing.
    """
    fields = {k: "" for k in PATROL_METRIC_PATTERNS}
    memo_parts = []
    matched_any = False
    for token in (t.strip() for t in summary.split("/")):
        if not token:
            continue
        matched = False
        for key, pat in PATROL_METRIC_PATTERNS.items():
            m = pat.match(token)
            if m:
                fields[key] = m.group(1)
                matched = True
                matched_any = True
                break
        if not matched:
            memo_parts.append(token)
    if not matched_any:
        return {**fields, "memo": summary}
    return {**fields, "memo": " / ".join(memo_parts)}


def load_recent_patrols(journal: Path, limit: int) -> list[dict]:
    path = journal / "patrols.md"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("日時",):
            continue
        summary = " | ".join(cells[1:])
        rows.append({"datetime": cells[0], "summary": summary, **parse_patrol_summary(summary)})
    return rows[-limit:] if limit > 0 else rows


def load_spec_history(root: Path, spec_slug: str) -> list[dict]:
    """issue #30: walk the git history of journal/specs/<spec_slug>.json (following
    renames, since specs get renamed e.g. w24 → kaizen) and return each revision's
    `goal` text, newest first.

    Returns [] when the file isn't tracked by git at all (`git ls-files` empty) or
    when git itself isn't available/fails — dashboard then omits the "Goal 履歴"
    section entirely per acceptance criteria (git 履歴が取れない環境は section を出さない).
    """
    rel_path = f"journal/specs/{spec_slug}.json"
    try:
        ls = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", rel_path],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if ls.returncode != 0 or not ls.stdout.strip():
        return []

    try:
        log = subprocess.run(
            ["git", "-C", str(root), "log", "--follow", "--name-status",
             "--format=%x00%H%x01%aI", "--", rel_path],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if log.returncode != 0:
        return []

    history = []
    for block in log.stdout.split("\x00"):
        if not block.strip():
            continue
        lines = block.splitlines()
        header = lines[0] if lines else ""
        if "\x01" not in header:
            continue
        commit_hash, ts = header.split("\x01", 1)
        # The file's path in this commit's tree is the last column of the last
        # name-status line (handles A/M plain paths and R### rename "old\tnew" pairs).
        path_at_commit = rel_path
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            fields = line.split("\t")
            path_at_commit = fields[-1]
        try:
            show = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit_hash}:{path_at_commit}"],
                capture_output=True, text=True, timeout=15,
            )
        except subprocess.TimeoutExpired:
            continue
        if show.returncode != 0:
            continue
        try:
            spec_data = json.loads(show.stdout)
        except json.JSONDecodeError:
            continue
        history.append({
            "hash": commit_hash,
            "hash_short": commit_hash[:7],
            "ts": ts,
            "goal": spec_data.get("goal", ""),
        })
    return history  # `git log` default order is already newest-first


RETRO_BODY_TRUNCATE_CHARS = 2000


def load_retro_index(journal: Path) -> list[dict]:
    """issue #27: load the retro-*.md body (truncated) alongside the index so the
    dashboard can render an inline <details> preview, not just a link."""
    entries = []
    for path in sorted(journal.glob("retro-*.md"), reverse=True):
        m = re.search(r"retro-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$", path.name)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"warning: could not read {path}: {e}", file=sys.stderr)
            text = ""
        truncated = len(text) > RETRO_BODY_TRUNCATE_CHARS
        body = text[:RETRO_BODY_TRUNCATE_CHARS]
        if truncated:
            body += "\n... [continued]"
        entries.append({
            "file": path.name,
            "date": m.group(1) if m else "",
            "suffix": m.group(2) or "" if m else "",
            "body": body,
            "truncated": truncated,
        })
    return entries


TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>volante dashboard</title>
<style>
  :root {
    --bg: #fbfbfa; --surface: #ffffff; --border: #e4e4e0; --text: #1f2328;
    --text-mute: #636c76; --accent: #2f6fed; --accent-bg: #eaf1fe;
    --ok: #1f883d; --ok-bg: #eaf6ec; --warn: #9a6700; --warn-bg: #fdf3e0;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    --sans: system-ui, -apple-system, "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #15171a; --surface: #1c1f23; --border: #30363d; --text: #e6edf3;
      --text-mute: #99a2ab; --accent: #4f8bff; --accent-bg: #16243f;
      --ok: #4ac26b; --ok-bg: #122017; --warn: #e3b341; --warn-bg: #241c0c;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px 16px; color: var(--text); background: var(--bg);
         font-family: var(--sans); line-height: 1.55; font-size: 14px;
         -webkit-font-smoothing: antialiased; }
  .wrap { max-width: 1200px; margin: 0 auto; }
  header { padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
  header h1 { margin: 0 0 4px; font-size: 20px; }
  header .meta { color: var(--text-mute); font-family: var(--mono); font-size: 12px; }
  header .about-link { margin-top: 6px; font-size: 12.5px; }
  header .about-link a { color: var(--accent); text-decoration: none; }
  header .about-link a:hover { text-decoration: underline; }
  section { margin-bottom: 28px; background: var(--surface); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px 18px; }
  section > h2 { margin: 0 0 12px; font-size: 12px; letter-spacing: .08em;
                 text-transform: uppercase; color: var(--text-mute); font-weight: 700; }
  .epic-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
               gap: 12px; }
  .epic-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; background: var(--bg);
               display: flex; flex-direction: column; gap: 8px; }
  .epic-card .name { font-family: var(--mono); font-size: 13px; color: var(--accent); font-weight: 700; }
  .epic-card .repo-label { font-family: var(--mono); font-size: 11px; color: var(--text-mute); }
  .epic-card .goal { font-size: 13.5px; line-height: 1.5; }
  .epic-card .progress { display: flex; align-items: baseline; gap: 8px; font-size: 12.5px;
                         padding: 6px 10px; border-radius: 6px; background: var(--surface);
                         border: 1px solid var(--border); }
  .epic-card .progress .label { color: var(--text-mute); text-transform: uppercase;
                                letter-spacing: .05em; font-size: 10.5px; font-weight: 700; }
  .epic-card .progress .value { font-family: var(--mono); font-weight: 600; }
  .epic-card .progress.done { background: var(--ok-bg); border-color: var(--ok); }
  .epic-card .progress.done .value { color: var(--ok); }
  .epic-card .progress.unknown { color: var(--text-mute); }
  .epic-card details { margin-top: 4px; font-size: 13px; }
  .epic-card details > summary { cursor: pointer; color: var(--text-mute); font-size: 12px;
                                 list-style: none; padding: 4px 0; }
  .epic-card details > summary::marker, .epic-card details > summary::-webkit-details-marker { display: none; }
  .epic-card details > summary::before { content: "▸ "; display: inline-block; transition: transform .1s; }
  .epic-card details[open] > summary::before { content: "▾ "; }
  .epic-card details ul { margin: 4px 0 0; padding-left: 18px; font-size: 13px; }
  .epic-card details li { margin-bottom: 2px; }
  .timeline { display: flex; flex-direction: column; gap: 8px; }
  .event { border-left: 3px solid var(--border); padding: 4px 12px; font-size: 13px; }
  .event.branch-1 { border-color: var(--warn); background: var(--warn-bg); }
  .event.branch-oversight { border-color: var(--accent); background: var(--accent-bg); }
  .event .head { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
  .event .ts { font-family: var(--mono); color: var(--text-mute); font-size: 12px; }
  .event .branch { font-family: var(--mono); font-size: 11px; padding: 1px 6px;
                   border-radius: 4px; background: var(--surface); border: 1px solid var(--border); }
  .event .target { font-family: var(--mono); font-size: 12px; color: var(--text-mute); }
  .event .decision { margin: 4px 0; }
  .event .rationale { color: var(--text-mute); font-size: 12px; }
  .event .review { font-family: var(--mono); font-size: 11px; color: var(--text-mute); margin-top: 4px; }
  .event .review.ok::before { content: "✓ "; color: var(--ok); }
  .event .review.ng::before { content: "✗ "; color: var(--warn); }
  .event details.event-detail { margin-top: 6px; font-size: 12px; }
  .event details.event-detail > summary { cursor: pointer; color: var(--text-mute); font-size: 12px;
                                          list-style: none; padding: 3px 0; }
  .event details.event-detail > summary::marker, .event details.event-detail > summary::-webkit-details-marker { display: none; }
  .event details.event-detail > summary::before { content: "▸ 詳細"; display: inline-block; }
  .event details.event-detail[open] > summary::before { content: "▾ 詳細"; }
  .event-detail-row { margin: 6px 0 0; }
  .event-detail-row .label { display: block; color: var(--text-mute); font-size: 10.5px;
                             text-transform: uppercase; letter-spacing: .05em; margin-bottom: 2px; }
  .event-detail-row pre { font-family: var(--mono); font-size: 12px; white-space: pre-wrap;
                          word-break: break-word; margin: 0; background: var(--surface);
                          border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  table th, table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--border);
                       vertical-align: top; }
  table th { font-weight: 600; color: var(--text-mute); font-size: 11px;
             text-transform: uppercase; letter-spacing: .05em; }
  #patrols td.dt { font-family: var(--mono); font-size: 12px; color: var(--text-mute);
                   white-space: nowrap; width: 1%; }
  #patrols td.summary { font-size: 12.5px; line-height: 1.5; }
  .empty { color: var(--text-mute); font-style: italic; }
  code { font-family: var(--mono); font-size: 12px; }
  .tabs { margin-top: 8px; }
  .tab-buttons { display: flex; gap: 2px; border-bottom: 1px solid var(--border);
                 margin-bottom: 20px; overflow-x: auto; }
  .tab-btn { padding: 8px 14px; background: none; border: none; cursor: pointer;
             color: var(--text-mute); font-size: 13px; font-family: var(--sans);
             border-bottom: 2px solid transparent; white-space: nowrap; transition: color .1s; }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .tab-pane { display: none; }
  .tab-pane.active { display: block; }
  #pm-table { font-size: 13px; }
  #pm-table td, #pm-table th { padding: 8px 10px; }
  #pm-table td.epic-name { font-family: var(--mono); font-weight: 700; color: var(--accent); }
  #pm-table td.repo { font-family: var(--mono); font-size: 11.5px; color: var(--text-mute); }
  .status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
                  font-family: var(--mono); font-size: 11px; font-weight: 700;
                  text-transform: uppercase; letter-spacing: .05em; }
  .status-badge.done { background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok); }
  .status-badge.on-track { background: var(--accent-bg); color: var(--accent); border: 1px solid var(--accent); }
  .status-badge.at-risk { background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn); }
  .status-badge.stalled { background: var(--surface-2, var(--surface)); color: var(--text-mute); border: 1px solid var(--border); }
  #pm-table td.metric-num { font-family: var(--mono); text-align: right; }
  #pm-table td.metric-num.warn { color: var(--warn); font-weight: 700; }
  #pm-table td.metric-num.ok { color: var(--ok); }
  #pm-table td.metric-ts { font-family: var(--mono); font-size: 11.5px; color: var(--text-mute);
                           white-space: nowrap; }
  .placeholder { padding: 32px; text-align: center; color: var(--text-mute); font-style: italic; }
  .epic-tab-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
                   padding-bottom: 8px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
  .epic-tab-head .name { font-family: var(--mono); font-size: 18px; font-weight: 700; color: var(--accent); }
  .epic-tab-head .repo-link { font-family: var(--mono); font-size: 13px; color: var(--text-mute); }
  .epic-tab-head .repo-link a { color: inherit; text-decoration: none; }
  .epic-tab-head .repo-link a:hover { text-decoration: underline; }
  .epic-tab-head .goal-txt { flex-basis: 100%; font-size: 14px; margin-top: 4px; }
  .criteria-list { padding-left: 22px; margin: 6px 0 0; font-size: 13px; }
  .criteria-list li { margin-bottom: 4px; }
  .criteria-list li::marker { color: var(--text-mute); }
  .pr-row a, .issue-row a { color: var(--accent); text-decoration: none; font-family: var(--mono); }
  .pr-row a:hover, .issue-row a:hover { text-decoration: underline; }
  .pr-row .title, .issue-row .title { font-size: 13px; }
  .pr-row .ci { font-family: var(--mono); font-size: 11.5px; white-space: nowrap; }
  .pr-row .num, .issue-row .num { font-family: var(--mono); font-size: 12px; color: var(--text-mute);
                                  white-space: nowrap; width: 1%; }
  .pr-row .draft-tag { display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px;
                       background: var(--surface); border: 1px solid var(--border); color: var(--text-mute);
                       margin-right: 4px; }
  .label-chip { display: inline-block; font-size: 10.5px; padding: 1px 6px; border-radius: 8px;
                background: var(--surface); border: 1px solid var(--border); margin-right: 3px;
                color: var(--text-mute); }
  .kpi-link { font-family: var(--mono); font-size: 12px; }
  .kpi-link a { color: var(--accent); text-decoration: none; }
  .kpi-link a:hover { text-decoration: underline; }
  .kpi-link.unset { color: var(--text-mute); font-style: italic; }
  #pm-table td.kpi { font-family: var(--mono); font-size: 11.5px; }
  a.epic-name-link { color: inherit; text-decoration: none; border-bottom: 1px dotted var(--accent); }
  a.epic-name-link:hover { text-decoration: none; border-bottom-style: solid; }
  .retro-link { color: inherit; text-decoration: none; }
  .retro-link:hover { text-decoration: underline; }
  #patrols td.memo { font-size: 12.5px; line-height: 1.5; }
  .retro-list { display: flex; flex-direction: column; gap: 6px; }
  .retro-entry { border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; background: var(--bg); }
  .retro-entry > summary { cursor: pointer; font-size: 13px; display: flex; gap: 10px; align-items: baseline;
                           list-style: none; }
  .retro-entry > summary::-webkit-details-marker { display: none; }
  .retro-entry > summary::before { content: "▸ "; color: var(--text-mute); }
  .retro-entry[open] > summary::before { content: "▾ "; }
  .retro-entry .date { font-family: var(--mono); color: var(--text-mute); font-size: 12px; white-space: nowrap; }
  .retro-body { margin: 10px 0 0; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border);
               border-radius: 6px; font-family: var(--mono); font-size: 12px; white-space: pre-wrap;
               word-break: break-word; max-height: 480px; overflow-y: auto; }
  .decisions-filter { display: flex; flex-direction: column; gap: 10px; }
  .filter-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .filter-label { font-size: 11px; color: var(--text-mute); text-transform: uppercase;
                  letter-spacing: .05em; font-weight: 700; min-width: 44px; }
  .chip-group, .radio-group { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { padding: 3px 12px; font-size: 12px; font-family: var(--sans); border: 1px solid var(--border);
         border-radius: 12px; background: var(--surface); color: var(--text-mute); cursor: pointer; }
  .chip:hover { color: var(--text); }
  .chip.active { background: var(--accent-bg); color: var(--accent); border-color: var(--accent); font-weight: 600; }
  .radio-chip { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-mute);
               cursor: pointer; }
  .radio-chip input { cursor: pointer; }
  #filter-session { font-size: 12px; font-family: var(--sans); padding: 3px 8px; border-radius: 6px;
                    border: 1px solid var(--border); background: var(--surface); color: var(--text); }
  .filter-checkbox { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; cursor: pointer; }
  .filter-checkbox input { cursor: pointer; }
  .filter-reset-btn { padding: 3px 12px; font-size: 12px; font-family: var(--sans); border: 1px solid var(--border);
                      border-radius: 6px; background: var(--surface); color: var(--text-mute); cursor: pointer; }
  .filter-reset-btn:hover { color: var(--text); }
  #decisions-count { font-family: var(--mono); color: var(--text); }
  .goal-history { margin-top: 10px; font-size: 13px; }
  .goal-history > summary { cursor: pointer; color: var(--text-mute); font-size: 12.5px;
                            list-style: none; padding: 4px 0; }
  .goal-history > summary::-webkit-details-marker { display: none; }
  .goal-history > summary::before { content: "▸ "; }
  .goal-history[open] > summary::before { content: "▾ "; }
  .goal-history-list { display: flex; flex-direction: column; gap: 10px; margin-top: 6px; }
  .goal-history-row { border-left: 2px solid var(--border); padding: 4px 10px; }
  .goal-history-meta { font-family: var(--mono); font-size: 11px; color: var(--text-mute); margin-bottom: 2px; }
  .goal-history-diff { font-size: 13px; line-height: 1.6; }
  .diff-add { background: var(--ok-bg); color: var(--ok); border-radius: 2px; padding: 0 1px; }
  .diff-del { background: var(--warn-bg); color: var(--warn); text-decoration: line-through;
             border-radius: 2px; padding: 0 1px; }
  .diff-unchanged { color: var(--text-mute); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>volante dashboard</h1>
    <span class="meta">__REPO_PATH__ · generated __GENERATED_AT__ (issue #17 MVP)</span>
    <div class="about-link"><a href="./about.html">仕組みの説明 (about) →</a></div>
  </header>

  <div class="tabs">
    <div id="tab-buttons" class="tab-buttons"></div>

    <div id="tab-all" class="tab-pane active">
      <section>
        <h2>Epics overview (PM view)</h2>
        <table id="pm-table">
          <thead>
            <tr>
              <th>Epic</th>
              <th>repo</th>
              <th>KPI</th>
              <th>優先度</th>
              <th>status</th>
              <th>進捗</th>
              <th>直近更新</th>
              <th>ブロッカー</th>
              <th>承認待ち</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </section>

      <section>
        <h2>Epics (詳細カード)</h2>
        <div id="specs" class="epic-grid"></div>
      </section>

      <section>
        <h2>Decisions フィルタ (issue #29)</h2>
        <div id="decisions-filter" class="decisions-filter">
          <div class="filter-row">
            <span class="filter-label">枝</span>
            <div id="filter-branch-chips" class="chip-group"></div>
          </div>
          <div class="filter-row">
            <span class="filter-label">session</span>
            <select id="filter-session"></select>
          </div>
          <div class="filter-row">
            <span class="filter-label">期間</span>
            <div id="filter-period-radios" class="radio-group"></div>
          </div>
          <div class="filter-row">
            <label class="filter-checkbox"><input type="checkbox" id="filter-oversight-only"> 監督 AI のみ</label>
            <button type="button" id="filter-reset" class="filter-reset-btn">リセット</button>
          </div>
        </div>
      </section>

      <section>
        <h2>Recent decisions (直近 __DECISIONS_LIMIT__ 件中 <span id="decisions-count">0</span> 件表示)</h2>
        <div id="decisions" class="timeline"></div>
      </section>

      <section>
        <h2>Recent patrols (直近 __PATROLS_LIMIT__ 行)</h2>
        <table id="patrols"><thead><tr><th>日時</th><th>観測</th><th>IDLE</th><th>RUNNING</th><th>WAITING</th><th>指示</th><th>メモ</th></tr></thead><tbody></tbody></table>
      </section>

      <section>
        <h2>Retro index</h2>
        <div id="retros" class="retro-list"></div>
      </section>
    </div>

    <div id="tab-epics-container"></div>
  </div>
</div>

<script id="volante-data" type="application/json">__DATA_JSON__</script>
<script>
  const data = JSON.parse(document.getElementById('volante-data').textContent);

  // issue #26: fields shown inside the collapsible "詳細" panel for 監督 AI judgement events.
  // Declared early (before the tab-construction loop below, which calls renderEvent via
  // renderEpicTab synchronously) to avoid a temporal-dead-zone ReferenceError.
  const OVERSIGHT_DETAIL_FIELDS = [
    ['rationale', '根拠 (rationale)'],
    ['self_review', 'self_review'],
    ['evidence', 'evidence'],
    ['konuma_review', 'konuma レビュー'],
    ['oversight_verdict', 'oversight_verdict'],
    ['oversight_evidence', 'oversight_evidence'],
  ];

  // ===== KPI sheet link (issue #23: epic は必ず PJCI シートのタブに紐付ける) =====
  const KPI_SHEET_ID = '1WyEk-SLza9RjXfoYmoxn6zNwSKfeu4As7QIlUz0zj4U';
  function kpiSheetUrl(gid) {
    const g = encodeURIComponent(gid);
    return 'https://docs.google.com/spreadsheets/d/' + KPI_SHEET_ID + '/edit?gid=' + g + '#gid=' + g;
  }
  function renderKpiLink(kpiTab) {
    const el = document.createElement('span'); el.className = 'kpi-link';
    if (!kpiTab || !kpiTab.gid || !kpiTab.name) {
      el.classList.add('unset');
      el.textContent = 'KPI: 未紐付け';
      return el;
    }
    const a = document.createElement('a');
    a.href = kpiSheetUrl(kpiTab.gid); a.target = '_blank'; a.rel = 'noopener';
    a.textContent = 'KPI: ' + kpiTab.name;
    el.appendChild(a);
    return el;
  }

  // ===== Epic name → GitHub issues (label 絞り込み) link (issue #22) =====
  function epicIssuesUrl(repo, epicLabel) {
    return 'https://github.com/' + repo + '/issues?q=' + encodeURIComponent('is:issue label:' + epicLabel);
  }
  function renderEpicName(s, className) {
    const epicLabel = (s.spec || {}).epic_label;
    if (epicLabel && s.repo) {
      const a = document.createElement('a');
      a.className = (className + ' epic-name-link').trim();
      a.href = epicIssuesUrl(s.repo, epicLabel);
      a.target = '_blank'; a.rel = 'noopener';
      a.textContent = s.session;
      return a;
    }
    const span = document.createElement('span');
    span.className = className;
    span.textContent = s.session;
    return span;
  }

  // ===== Progress display: epic_label 付きなら "X / (X+Y) closed", 無ければ repo 全体 open 数 (fallback) =====
  function progressInfo(p) {
    p = p || {};
    if (p.label && typeof p.closed === 'number' && typeof p.total === 'number') {
      return {
        text: p.closed + ' / ' + p.total + ' closed',
        done: p.total > 0 && p.closed === p.total,
        unknown: false,
        title: 'label:' + p.label,
      };
    }
    if (p.count === 0) {
      return { text: '全 issue closed (0 open)', done: true, unknown: false, title: '' };
    }
    if (typeof p.count === 'number') {
      return { text: p.count + ' open issues', done: false, unknown: false, title: '' };
    }
    return { text: '(進捗未定義)', done: false, unknown: true, title: p.error || '' };
  }

  // ===== issue #30: Goal 履歴の簡易 word-diff (外部 chart/diff library 禁止 → 自前実装) =====
  function tokenizeForDiff(s) { return s.match(/\\s+|[^\\s]+/g) || []; }

  function diffTokens(a, b) {
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const ops = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push(['eq', a[i]]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push(['del', a[i]]); i++; }
      else { ops.push(['add', b[j]]); j++; }
    }
    while (i < n) { ops.push(['del', a[i]]); i++; }
    while (j < m) { ops.push(['add', b[j]]); j++; }
    return ops;
  }

  function renderGoalDiff(oldStr, newStr) {
    const frag = document.createDocumentFragment();
    if (oldStr === newStr) {
      const span = document.createElement('span'); span.className = 'diff-unchanged';
      span.textContent = newStr || '(変更なし)';
      frag.appendChild(span);
      return frag;
    }
    const ops = diffTokens(tokenizeForDiff(oldStr || ''), tokenizeForDiff(newStr || ''));
    for (const [type, text] of ops) {
      if (type === 'eq') { frag.appendChild(document.createTextNode(text)); continue; }
      const span = document.createElement('span');
      span.className = type === 'add' ? 'diff-add' : 'diff-del';
      span.textContent = text;
      frag.appendChild(span);
    }
    return frag;
  }

  // Renders the collapsible "Goal 履歴 (N revisions)" block for one epic tab.
  // history is newest-first ({ts, goal, hash, hash_short}[]); each revision is diffed
  // against the next (older) entry. Suppressed entirely when <=1 revision (new spec)
  // or when git history wasn't available (dashboard-generate.py returns [] in that case).
  function renderGoalHistory(history) {
    if (!history || history.length <= 1) return null;
    const det = document.createElement('details'); det.className = 'goal-history';
    const sum = document.createElement('summary'); sum.textContent = 'Goal 履歴 (' + history.length + ' revisions)';
    det.appendChild(sum);
    const list = document.createElement('div'); list.className = 'goal-history-list';
    for (let i = 0; i < history.length; i++) {
      const rev = history[i];
      const older = history[i + 1];
      const row = document.createElement('div'); row.className = 'goal-history-row';
      const meta = document.createElement('div'); meta.className = 'goal-history-meta';
      meta.textContent = (rev.ts || '').replace('T', ' ').slice(0, 16) + '  ' + (rev.hash_short || '')
        + (older ? '' : '  (初版)');
      row.appendChild(meta);
      const diffEl = document.createElement('div'); diffEl.className = 'goal-history-diff';
      diffEl.appendChild(older ? renderGoalDiff(older.goal || '', rev.goal || '')
                                : document.createTextNode(rev.goal || ''));
      row.appendChild(diffEl);
      list.appendChild(row);
    }
    det.appendChild(list);
    return det;
  }

  // ===== Tab framework =====
  const tabBtns = document.getElementById('tab-buttons');
  const tabEpicsContainer = document.getElementById('tab-epics-container');
  const allTabs = [{id: 'tab-all', label: '全体'}];
  for (const s of data.specs) allTabs.push({id: 'tab-' + s.session, label: s.session, spec: s});
  function activateTab(id) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === id));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === id));
  }
  for (const t of allTabs) {
    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (t.id === 'tab-all' ? ' active' : '');
    btn.dataset.tab = t.id;
    btn.textContent = t.label;
    btn.addEventListener('click', () => activateTab(t.id));
    tabBtns.appendChild(btn);
    if (t.id !== 'tab-all') {
      const pane = document.createElement('div');
      pane.id = t.id;
      pane.className = 'tab-pane';
      renderEpicTab(pane, t.spec, data);
      tabEpicsContainer.appendChild(pane);
    }
  }

  // ===== Per-epic tab renderer (#21) =====
  function renderEpicTab(pane, s, data) {
    const spec = s.spec || {};
    const m = s.metrics || {};

    // Head: name + repo link + status badge + goal
    const head = document.createElement('div');
    head.className = 'epic-tab-head';
    head.appendChild(renderEpicName(s, 'name'));
    if (s.repo) {
      const repoWrap = document.createElement('span'); repoWrap.className = 'repo-link';
      const repoA = document.createElement('a');
      repoA.href = 'https://github.com/' + s.repo; repoA.target = '_blank'; repoA.rel = 'noopener';
      repoA.textContent = s.repo;
      repoWrap.appendChild(repoA);
      head.appendChild(repoWrap);
    }
    head.appendChild(renderKpiLink(spec.kpi_sheet_tab));
    if (s.priority) {
      const pri = document.createElement('span'); pri.className = 'repo-link';
      pri.textContent = '優先度: ' + s.priority; head.appendChild(pri);
    }
    const badge = document.createElement('span');
    badge.className = 'status-badge ' + (m.status || 'on-track');
    badge.textContent = m.status || 'on-track';
    head.appendChild(badge);
    if (spec.goal) {
      const g = document.createElement('div'); g.className = 'goal-txt'; g.textContent = spec.goal;
      head.appendChild(g);
    }
    pane.appendChild(head);

    // issue #30: Goal 履歴 (git log --follow 由来の revision diff)
    const goalHistoryEl = renderGoalHistory((data.spec_history || {})[s.session]);
    if (goalHistoryEl) pane.appendChild(goalHistoryEl);

    // acceptance_criteria (open by default in epic tab)
    if (spec.acceptance_criteria && spec.acceptance_criteria.length > 0) {
      const sec = document.createElement('section');
      const h = document.createElement('h2'); h.textContent = 'acceptance_criteria (' + spec.acceptance_criteria.length + ')'; sec.appendChild(h);
      const ul = document.createElement('ul'); ul.className = 'criteria-list';
      for (const c of spec.acceptance_criteria) {
        const li = document.createElement('li'); li.textContent = c; ul.appendChild(li);
      }
      sec.appendChild(ul);
      pane.appendChild(sec);
    }

    // Open PRs
    const prSec = document.createElement('section');
    const prH = document.createElement('h2'); prH.textContent = '開いてる PR' + (s.repo ? ' (' + s.repo + ')' : ''); prSec.appendChild(prH);
    const prd = s.prs || {};
    if (prd.error) {
      const em = document.createElement('div'); em.className = 'empty'; em.textContent = prd.error; prSec.appendChild(em);
    } else if (!prd.prs || prd.prs.length === 0) {
      const em = document.createElement('div'); em.className = 'empty'; em.textContent = '(open PR なし)'; prSec.appendChild(em);
    } else {
      const tbl = document.createElement('table');
      const thead = document.createElement('thead');
      thead.innerHTML = '<tr><th>#</th><th>title</th><th>CI</th><th>review</th><th>merge</th></tr>';
      tbl.appendChild(thead);
      const tb = document.createElement('tbody');
      for (const pr of prd.prs) {
        const tr = document.createElement('tr'); tr.className = 'pr-row';
        const num = document.createElement('td'); num.className = 'num';
        const a = document.createElement('a'); a.href = pr.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '#' + pr.number;
        num.appendChild(a);
        tr.appendChild(num);
        const title = document.createElement('td'); title.className = 'title';
        if (pr.isDraft) {
          const dt = document.createElement('span'); dt.className = 'draft-tag'; dt.textContent = 'draft';
          title.appendChild(dt);
        }
        title.appendChild(document.createTextNode(pr.title || ''));
        tr.appendChild(title);
        const ci = document.createElement('td'); ci.className = 'ci'; ci.textContent = pr.ciSummary || ''; tr.appendChild(ci);
        const rev = document.createElement('td'); rev.className = 'ci'; rev.textContent = pr.reviewDecision || ''; tr.appendChild(rev);
        const mrg = document.createElement('td'); mrg.className = 'ci'; mrg.textContent = pr.mergeStateStatus || ''; tr.appendChild(mrg);
        tb.appendChild(tr);
      }
      tbl.appendChild(tb);
      prSec.appendChild(tbl);
    }
    pane.appendChild(prSec);

    // Open Issues
    const isSec = document.createElement('section');
    const isH = document.createElement('h2'); isH.textContent = '開いてる issue' + (s.repo ? ' (' + s.repo + ')' : ''); isSec.appendChild(isH);
    const isd = s.issues || {};
    if (isd.error) {
      const em = document.createElement('div'); em.className = 'empty'; em.textContent = isd.error; isSec.appendChild(em);
    } else if (!isd.issues || isd.issues.length === 0) {
      const em = document.createElement('div'); em.className = 'empty'; em.textContent = '(open issue なし)'; isSec.appendChild(em);
    } else {
      const tbl = document.createElement('table');
      const thead = document.createElement('thead');
      thead.innerHTML = '<tr><th>#</th><th>title</th><th>labels</th><th>updated</th></tr>';
      tbl.appendChild(thead);
      const tb = document.createElement('tbody');
      for (const iss of isd.issues) {
        const tr = document.createElement('tr'); tr.className = 'issue-row';
        const num = document.createElement('td'); num.className = 'num';
        const a = document.createElement('a'); a.href = iss.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '#' + iss.number;
        num.appendChild(a); tr.appendChild(num);
        const title = document.createElement('td'); title.className = 'title'; title.textContent = iss.title || ''; tr.appendChild(title);
        const lbl = document.createElement('td');
        for (const l of iss.labels || []) {
          const chip = document.createElement('span'); chip.className = 'label-chip'; chip.textContent = l.name || l; lbl.appendChild(chip);
        }
        tr.appendChild(lbl);
        const upd = document.createElement('td'); upd.className = 'metric-ts';
        upd.textContent = (iss.updatedAt || '').replace('T', ' ').slice(0, 16); tr.appendChild(upd);
        tb.appendChild(tr);
      }
      tbl.appendChild(tb);
      isSec.appendChild(tbl);
    }
    pane.appendChild(isSec);

    // Filtered decisions (this epic only). issue #28: filter from the full-period set
    // (decisions_all), not just the current-month-limited main timeline list.
    const decSec = document.createElement('section');
    const decH = document.createElement('h2'); decH.textContent = '直近 decisions (' + s.session + ' 関連・全期間)'; decSec.appendChild(decH);
    const relevant = (data.decisions_all || data.decisions || []).filter(ev => (ev.target_session || '').includes(s.session));
    if (relevant.length === 0) {
      const em = document.createElement('div'); em.className = 'empty'; em.textContent = '(該当なし)'; decSec.appendChild(em);
    } else {
      const tl = document.createElement('div'); tl.className = 'timeline';
      for (const ev of relevant.slice().reverse()) {
        tl.appendChild(renderEvent(ev));
      }
      decSec.appendChild(tl);
    }
    pane.appendChild(decSec);

    // Oversight (v0.15.0) history for this epic
    const ovSec = document.createElement('section');
    const ovH = document.createElement('h2'); ovH.textContent = '監督 AI 判定履歴 (' + s.session + ' 関連)'; ovSec.appendChild(ovH);
    const ovs = (data.decisions_all || data.decisions || []).filter(ev => (ev.target_session || '').includes(s.session)
                                                    && String(ev.branch || '').includes('監督 AI'));
    if (ovs.length === 0) {
      const em = document.createElement('div'); em.className = 'empty';
      em.textContent = '(監督 AI 判定なし。試験運用対象未指定 or 未起動)'; ovSec.appendChild(em);
    } else {
      const tl = document.createElement('div'); tl.className = 'timeline';
      for (const ev of ovs.slice().reverse()) tl.appendChild(renderEvent(ev));
      ovSec.appendChild(tl);
    }
    pane.appendChild(ovSec);
  }

  // Shared event renderer (used by main timeline and per-epic timeline)
  function renderEvent(ev) {
    const el = document.createElement('div');
    const branch = String(ev.branch || '');
    const isOversight = branch.includes('監督 AI');
    const branchClass = branch === '1' ? 'branch-1' : (isOversight ? 'branch-oversight' : '');
    el.className = 'event ' + branchClass;
    const head = document.createElement('div'); head.className = 'head';
    const ts = document.createElement('span'); ts.className = 'ts'; ts.textContent = ev.timestamp || ''; head.appendChild(ts);
    const br = document.createElement('span'); br.className = 'branch'; br.textContent = '枝 ' + branch; head.appendChild(br);
    const tgt = document.createElement('span'); tgt.className = 'target'; tgt.textContent = ev.target_session || ''; head.appendChild(tgt);
    el.appendChild(head);
    const dec = document.createElement('div'); dec.className = 'decision'; dec.textContent = ev.decision || ''; el.appendChild(dec);

    if (isOversight) {
      // issue #26: 監督 AI event だけ、詳細フィールドを <details> に折りたたむ (非監督 event は下の else 節のまま = 回帰なし)
      const present = OVERSIGHT_DETAIL_FIELDS.filter(([key]) => ev[key]);
      if (present.length > 0) {
        const det = document.createElement('details'); det.className = 'event-detail';
        const sum = document.createElement('summary'); det.appendChild(sum);
        for (const [key, label] of present) {
          const row = document.createElement('div'); row.className = 'event-detail-row';
          const lab = document.createElement('span'); lab.className = 'label'; lab.textContent = label;
          row.appendChild(lab);
          const pre = document.createElement('pre'); pre.textContent = String(ev[key]);
          row.appendChild(pre);
          det.appendChild(row);
        }
        el.appendChild(det);
      }
    } else {
      if (ev.rationale) { const r = document.createElement('div'); r.className = 'rationale'; r.textContent = ev.rationale; el.appendChild(r); }
      if (ev.self_review) {
        const rv = document.createElement('div');
        const cls = /^OK/i.test(ev.self_review) ? 'ok' : (/^NG/i.test(ev.self_review) ? 'ng' : '');
        rv.className = 'review ' + cls; rv.textContent = ev.self_review; el.appendChild(rv);
      }
    }
    return el;
  }

  // ===== PM table =====
  const pmBody = document.querySelector('#pm-table tbody');
  if (data.specs.length === 0) {
    pmBody.innerHTML = '<tr><td colspan="9" class="empty">Spec 未登録</td></tr>';
  } else {
    for (const s of data.specs) {
      const m = s.metrics || {};
      const p = s.progress || {};
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td'); nameTd.className = 'epic-name'; nameTd.appendChild(renderEpicName(s, '')); tr.appendChild(nameTd);
      const repoTd = document.createElement('td'); repoTd.className = 'repo'; repoTd.textContent = s.repo || '(未解決)'; tr.appendChild(repoTd);
      const kpiTd = document.createElement('td'); kpiTd.className = 'kpi'; kpiTd.appendChild(renderKpiLink(s.spec.kpi_sheet_tab)); tr.appendChild(kpiTd);
      const prioTd = document.createElement('td'); prioTd.textContent = s.priority || '—'; tr.appendChild(prioTd);
      const statusTd = document.createElement('td');
      const badge = document.createElement('span'); badge.className = 'status-badge ' + (m.status || 'on-track');
      badge.textContent = m.status || 'on-track'; statusTd.appendChild(badge); tr.appendChild(statusTd);
      const progTd = document.createElement('td'); progTd.className = 'metric-num';
      const pinfo = progressInfo(p);
      progTd.textContent = pinfo.text;
      if (pinfo.done) progTd.classList.add('ok');
      if (pinfo.title) progTd.title = pinfo.title;
      tr.appendChild(progTd);
      const tsTd = document.createElement('td'); tsTd.className = 'metric-ts';
      tsTd.textContent = m.latest_ts ? m.latest_ts.replace('T', ' ').slice(0, 16) : '—';
      tr.appendChild(tsTd);
      const blkTd = document.createElement('td'); blkTd.className = 'metric-num';
      if (m.blockers > 0) blkTd.classList.add('warn');
      blkTd.textContent = m.blockers || 0;
      tr.appendChild(blkTd);
      const aprTd = document.createElement('td'); aprTd.className = 'metric-num';
      if (m.approval_pending > 0) aprTd.classList.add('warn');
      aprTd.textContent = m.approval_pending || 0;
      tr.appendChild(aprTd);
      pmBody.appendChild(tr);
    }
  }

  const specsEl = document.getElementById('specs');
  if (data.specs.length === 0) {
    specsEl.innerHTML = '<div class="empty">Spec 未登録</div>';
  } else {
    for (const s of data.specs) {
      const el = document.createElement('div');
      el.className = 'epic-card';

      // Header row: name + repo label
      const head = document.createElement('div');
      head.style.display = 'flex';
      head.style.alignItems = 'baseline';
      head.style.gap = '8px';
      head.style.flexWrap = 'wrap';
      head.appendChild(renderEpicName(s, 'name'));
      if (s.repo) {
        const repoLabel = document.createElement('span');
        repoLabel.className = 'repo-label';
        repoLabel.textContent = s.repo;
        head.appendChild(repoLabel);
      }
      el.appendChild(head);

      // KPI (issue #23)
      el.appendChild(renderKpiLink(s.spec.kpi_sheet_tab));

      // Goal
      const goal = document.createElement('div');
      goal.className = 'goal';
      goal.textContent = s.spec.goal || '';
      el.appendChild(goal);

      // Progress
      const prog = document.createElement('div');
      prog.className = 'progress';
      const progLabel = document.createElement('span');
      progLabel.className = 'label';
      progLabel.textContent = '進捗';
      prog.appendChild(progLabel);
      const progValue = document.createElement('span');
      progValue.className = 'value';
      const pinfoCard = progressInfo(s.progress);
      progValue.textContent = pinfoCard.text;
      if (pinfoCard.done) prog.classList.add('done');
      if (pinfoCard.unknown) prog.classList.add('unknown');
      if (pinfoCard.title) progValue.title = pinfoCard.title;
      prog.appendChild(progValue);
      el.appendChild(prog);

      // acceptance_criteria (collapsible)
      const criteria = s.spec.acceptance_criteria || [];
      if (criteria.length > 0) {
        const det = document.createElement('details');
        const sum = document.createElement('summary');
        sum.textContent = 'acceptance_criteria (' + criteria.length + ')';
        det.appendChild(sum);
        const ul = document.createElement('ul');
        for (const c of criteria) {
          const li = document.createElement('li');
          li.textContent = c;
          ul.appendChild(li);
        }
        det.appendChild(ul);
        el.appendChild(det);
      }

      specsEl.appendChild(el);
    }
  }

  // ===== issue #29: 対話的フィルタ (枝別・session 別・期間・監督 AI のみ) =====
  // Supersedes the old #28 "今月のみ/全期間" scope toggle: 期間 radio's "全期間" option
  // covers that case, and the filter now always reads from decisions_all (full multi-month
  // set, capped by --decisions-limit as before) so 24h/7d/月内 can filter across months too.
  const decEl = document.getElementById('decisions');
  const decCountEl = document.getElementById('decisions-count');
  const BRANCH_CHIP_DEFS = [['1', '1'], ['2', '2'], ['3', '3'], ['4', '4'], ['5', '5'], ['oversight', '監督 AI']];
  const PERIOD_DEFS = [['all', '全期間'], ['24h', '24h'], ['7d', '7d'], ['month', '今月']];
  const DEFAULT_FILTER_STATE = { branches: new Set(), session: '', period: 'month', oversightOnly: false };

  function parseFilterHash() {
    const raw = location.hash.startsWith('#') ? location.hash.slice(1) : location.hash;
    const params = new URLSearchParams(raw);
    const branchParam = params.get('branch');
    return {
      branches: branchParam ? new Set(branchParam.split(',').filter(Boolean)) : new Set(),
      session: params.get('session') || '',
      period: params.get('period') || 'month',
      oversightOnly: params.get('osonly') === '1',
    };
  }

  function writeFilterHash() {
    const params = new URLSearchParams();
    if (filterState.branches.size > 0) params.set('branch', Array.from(filterState.branches).join(','));
    if (filterState.session) params.set('session', filterState.session);
    if (filterState.period !== 'month') params.set('period', filterState.period);
    if (filterState.oversightOnly) params.set('osonly', '1');
    const qs = params.toString();
    history.replaceState(null, '', qs ? ('#' + qs) : (location.pathname + location.search));
  }

  let filterState = parseFilterHash();

  function renderBranchChips() {
    const container = document.getElementById('filter-branch-chips');
    container.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.type = 'button';
    allBtn.className = 'chip' + (filterState.branches.size === 0 ? ' active' : '');
    allBtn.textContent = '全';
    allBtn.addEventListener('click', () => { filterState.branches = new Set(); onFilterChange(); });
    container.appendChild(allBtn);
    for (const [val, label] of BRANCH_CHIP_DEFS) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip' + (filterState.branches.has(val) ? ' active' : '');
      btn.textContent = label;
      btn.addEventListener('click', () => {
        if (filterState.branches.has(val)) filterState.branches.delete(val); else filterState.branches.add(val);
        onFilterChange();
      });
      container.appendChild(btn);
    }
  }

  function renderSessionSelect() {
    const sel = document.getElementById('filter-session');
    sel.innerHTML = '';
    const optAll = document.createElement('option'); optAll.value = ''; optAll.textContent = '全';
    sel.appendChild(optAll);
    for (const s of data.specs) {
      const opt = document.createElement('option'); opt.value = s.session; opt.textContent = s.session;
      sel.appendChild(opt);
    }
    sel.value = filterState.session;
    sel.addEventListener('change', () => { filterState.session = sel.value; onFilterChange(); });
  }

  function renderPeriodRadios() {
    const container = document.getElementById('filter-period-radios');
    container.innerHTML = '';
    for (const [val, label] of PERIOD_DEFS) {
      const wrap = document.createElement('label'); wrap.className = 'radio-chip';
      const input = document.createElement('input');
      input.type = 'radio'; input.name = 'filter-period'; input.value = val;
      input.checked = filterState.period === val;
      input.addEventListener('change', () => { filterState.period = val; onFilterChange(); });
      wrap.appendChild(input);
      wrap.appendChild(document.createTextNode(label));
      container.appendChild(wrap);
    }
  }

  function refreshFilterUI() {
    renderBranchChips();
    renderSessionSelect();
    renderPeriodRadios();
    document.getElementById('filter-oversight-only').checked = filterState.oversightOnly;
  }

  function onFilterChange() {
    writeFilterHash();
    refreshFilterUI();
    renderDecisionsTimeline();
  }

  document.getElementById('filter-oversight-only').addEventListener('change', (e) => {
    filterState.oversightOnly = e.target.checked;
    onFilterChange();
  });
  document.getElementById('filter-reset').addEventListener('click', () => {
    filterState = { branches: new Set(), session: '', period: 'month', oversightOnly: false };
    onFilterChange();
  });
  window.addEventListener('hashchange', () => {
    filterState = parseFilterHash();
    refreshFilterUI();
    renderDecisionsTimeline();
  });

  function passesDecisionFilter(ev) {
    const branch = String(ev.branch || '');
    const isOv = branch.includes('監督 AI');
    if (filterState.branches.size > 0) {
      let ok = false;
      for (const b of filterState.branches) {
        if (b === 'oversight') { if (isOv) { ok = true; break; } }
        else if (branch === b) { ok = true; break; }
      }
      if (!ok) return false;
    }
    if (filterState.oversightOnly && !isOv) return false;
    if (filterState.session && !String(ev.target_session || '').includes(filterState.session)) return false;
    if (filterState.period !== 'all') {
      const ts = ev.timestamp || '';
      const evDate = new Date(ts);
      if (!ts || isNaN(evDate.getTime())) return false;
      const now = new Date();
      if (filterState.period === '24h' && (now - evDate) > 24 * 3600 * 1000) return false;
      if (filterState.period === '7d' && (now - evDate) > 7 * 24 * 3600 * 1000) return false;
      if (filterState.period === 'month' && ts.slice(0, 7) !== now.toISOString().slice(0, 7)) return false;
    }
    return true;
  }

  function renderDecisionsTimeline() {
    const source = (data.decisions_all && data.decisions_all.length) ? data.decisions_all : (data.decisions || []);
    decEl.innerHTML = '';
    if (source.length === 0) {
      decCountEl.textContent = '0';
      decEl.innerHTML = '<div class="empty">decisions-YYYY-MM.jsonl 未生成 or 空</div>';
      return;
    }
    const filtered = source.filter(passesDecisionFilter);
    decCountEl.textContent = String(filtered.length);
    if (filtered.length === 0) {
      decEl.innerHTML = '<div class="empty">条件に一致する decision がありません</div>';
      return;
    }
    for (const ev of filtered.slice().reverse()) decEl.appendChild(renderEvent(ev));
  }

  refreshFilterUI();
  renderDecisionsTimeline();

  const patBody = document.querySelector('#patrols tbody');
  const PATROL_METRIC_COLS = ['observed', 'idle', 'running', 'waiting', 'instructed'];
  if (data.patrols.length === 0) {
    patBody.innerHTML = '<tr><td colspan="7" class="empty">patrols.md 空</td></tr>';
  } else {
    for (const row of data.patrols.slice().reverse()) {
      const tr = document.createElement('tr');
      const dt = document.createElement('td'); dt.className = 'dt'; dt.textContent = row.datetime || ''; tr.appendChild(dt);
      for (const key of PATROL_METRIC_COLS) {
        const td = document.createElement('td'); td.className = 'metric-num'; td.textContent = row[key] || ''; tr.appendChild(td);
      }
      const memo = document.createElement('td'); memo.className = 'memo'; memo.textContent = row.memo || ''; tr.appendChild(memo);
      patBody.appendChild(tr);
    }
  }

  // issue #27: retro index を <details> の折りたたみリストに (link はそのまま summary 内に残す)
  const retroBody = document.getElementById('retros');
  if (data.retros.length === 0) {
    retroBody.innerHTML = '<div class="empty">retro なし</div>';
  } else {
    for (const r of data.retros) {
      const det = document.createElement('details'); det.className = 'retro-entry';
      const sum = document.createElement('summary');
      const d = document.createElement('span'); d.className = 'date'; d.textContent = r.date || '?'; sum.appendChild(d);
      const code = document.createElement('code');
      const a = document.createElement('a'); a.className = 'retro-link'; a.href = './' + r.file; a.textContent = r.file;
      code.appendChild(a);
      sum.appendChild(code);
      det.appendChild(sum);
      const pre = document.createElement('pre'); pre.className = 'retro-body';
      pre.textContent = r.body || '(本文取得不可)';
      det.appendChild(pre);
      retroBody.appendChild(det);
    }
  }
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, help="path to volante repo root")
    ap.add_argument("--out", type=Path, help="output HTML path (default: <repo_root>/journal/dashboard.html)")
    ap.add_argument("--decisions-limit", type=int, default=20)
    ap.add_argument("--patrols-limit", type=int, default=10)
    ap.add_argument("--now", type=str, help="fixed ISO-8601 timestamp for reproducible output (default: now)")
    ap.add_argument("--no-gh", action="store_true", help="skip gh queries (progress will show '進捗未定義')")
    args = ap.parse_args()

    root = args.repo_root or find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not locate volante repo root (need journal/ + .claude-plugin/)")

    journal = root / "journal"
    specs = load_specs(journal / "specs")
    all_decisions = load_recent_decisions(journal, 0)
    decisions = all_decisions[-args.decisions_limit:] if args.decisions_limit > 0 else all_decisions
    # issue #28: full multi-month set, capped by the same --decisions-limit, for the
    # "全期間" toggle + epic-tab filter. all_decisions (current-month-only, unlimited)
    # keeps feeding the PM-table metrics below unchanged (regression-free).
    all_decisions_multi = load_all_decisions(journal)
    decisions_all = (all_decisions_multi[-args.decisions_limit:]
                      if args.decisions_limit > 0 else all_decisions_multi)
    patrols = load_recent_patrols(journal, args.patrols_limit)
    retros = load_retro_index(journal)
    goals_rows = parse_goals_md(journal)

    # Resolve repo + fetch progress per spec (v0.15.4+, cached at generate time per CLAUDE.md 設計原則)
    # per-repo cache to avoid re-querying same repo (multi-Spec-per-repo case).
    # progress is cached per (repo, epic_label) since #22: two Specs on the same
    # repo can carry different epic_label scoping, but PRs/issues stay repo-wide.
    repo_cache: dict[str, dict] = {}
    progress_cache: dict[tuple[str, str], dict] = {}
    for spec in specs:
        basename = spec["session"]
        repo = resolve_repo_for_spec(basename, goals_rows)
        spec["repo"] = repo
        epic_label = (spec.get("spec") or {}).get("epic_label", "") or ""
        if repo and not args.no_gh:
            if repo not in repo_cache:
                repo_cache[repo] = {
                    "prs": fetch_open_prs(repo),
                    "issues": fetch_open_issues_list(repo),
                }
            spec["prs"] = repo_cache[repo]["prs"]
            spec["issues"] = repo_cache[repo]["issues"]
            cache_key = (repo, epic_label)
            if cache_key not in progress_cache:
                progress_cache[cache_key] = fetch_open_issue_count(repo, epic_label)
            spec["progress"] = progress_cache[cache_key]
        else:
            reason = "no repo resolved" if not repo else "gh skipped"
            spec["progress"] = {"count": None, "source": "", "error": reason}
            spec["prs"] = {"prs": [], "error": reason}
            spec["issues"] = {"issues": [], "error": reason}
        # Attach 優先度 from goals.md (first matching row by repo)
        priority = ""
        for row in goals_rows:
            if row.get("repo") == repo:
                priority = row.get("priority", "")
                break
        spec["priority"] = priority

    # issue #30: goal revision history per spec, keyed by basename (spec_slug)
    spec_history = {spec["session"]: load_spec_history(root, spec["session"]) for spec in specs}

    # Compute PM-view metrics per spec (v0.15.5+, issue #20)
    now_dt = datetime.now(timezone.utc)
    for spec in specs:
        basename = spec["session"]
        goal_text = (spec.get("spec") or {}).get("goal", "")
        matches = [ev for ev in all_decisions if basename and basename in (ev.get("target_session") or "")]
        latest_ts = ""
        for ev in matches:
            ts = ev.get("timestamp") or ""
            if ts > latest_ts:
                latest_ts = ts
        blockers = sum(1 for ev in matches if (ev.get("konuma_review") or "").startswith(("未", "NG")))
        approval_pending = sum(1 for ev in matches
                                if str(ev.get("branch") or "") in ("1", "3")
                                and not (ev.get("konuma_review") or "").startswith("OK"))
        # status rule
        status = "on-track"
        if any(kw in goal_text for kw in ("達成", "完了", "done")):
            status = "done"
        elif not latest_ts:
            status = "stalled"
        else:
            try:
                latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                delta_hours = (now_dt - latest_dt).total_seconds() / 3600
                if delta_hours > 24:
                    status = "stalled"
                elif blockers > 0 or approval_pending > 0:
                    status = "at-risk"
            except ValueError:
                pass
        spec["metrics"] = {
            "status": status,
            "latest_ts": latest_ts,
            "blockers": blockers,
            "approval_pending": approval_pending,
            "decisions_count": len(matches),
        }

    payload = {"specs": specs, "decisions": decisions, "decisions_all": decisions_all,
               "patrols": patrols, "retros": retros, "goals": goals_rows,
               "spec_history": spec_history}
    payload_json = json.dumps(payload, ensure_ascii=False)
    now_str = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = (TEMPLATE
            .replace("__REPO_PATH__", escape(str(root)))
            .replace("__GENERATED_AT__", escape(now_str))
            .replace("__DECISIONS_LIMIT__", str(args.decisions_limit))
            .replace("__PATROLS_LIMIT__", str(args.patrols_limit))
            .replace("__DATA_JSON__", payload_json.replace("</", "<\\/")))

    out = args.out or (journal / "dashboard.html")
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html)} bytes, {len(specs)} specs, {len(decisions)} decisions)")


if __name__ == "__main__":
    main()
