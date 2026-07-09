#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from volante journal state.

Reads:
  - journal/specs/*.json         (Session Spec v1)
  - journal/decisions-<YYYY-MM>.jsonl (latest month, last N events)
  - journal/patrols.md            (last few rows)
  - journal/retro-*.md           (index only)

Outputs:
  - journal/dashboard.html       (self-contained, JSON embedded via <script>)

Design principle (CLAUDE.md 設計原則, SKILL.md 芯 9):
  DB / サーバー不要、HTML + JSON でローカル完結。The output is a single .html
  file with embedded JSON. Open with `open journal/dashboard.html` — no server.

Status: v0.16.0-preview / MVP (issue #17 の第 1 段)。監督 AI 判定表示、
retro の内容展開、UI 洗練は継続イテレーションで対応する。
"""
import argparse
import json
import re
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


def load_recent_decisions(journal: Path, limit: int) -> list[dict]:
    now_month = datetime.now(timezone.utc).strftime("%Y-%m")
    path = journal / f"decisions-{now_month}.jsonl"
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
    return events[-limit:] if limit > 0 else events


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
        rows.append({"datetime": cells[0], "summary": " | ".join(cells[1:])})
    return rows[-limit:] if limit > 0 else rows


def load_retro_index(journal: Path) -> list[dict]:
    entries = []
    for path in sorted(journal.glob("retro-*.md"), reverse=True):
        m = re.search(r"retro-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$", path.name)
        entries.append({
            "file": path.name,
            "date": m.group(1) if m else "",
            "suffix": m.group(2) or "" if m else "",
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
  section { margin-bottom: 28px; background: var(--surface); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px 18px; }
  section > h2 { margin: 0 0 12px; font-size: 12px; letter-spacing: .08em;
                 text-transform: uppercase; color: var(--text-mute); font-weight: 700; }
  .spec-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
               gap: 12px; }
  .spec { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: var(--bg); }
  .spec .name { font-family: var(--mono); font-size: 13px; color: var(--accent); margin-bottom: 4px; }
  .spec .goal { margin-bottom: 8px; }
  .spec ul { margin: 0; padding-left: 18px; font-size: 13px; }
  .spec li { margin-bottom: 2px; }
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
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>volante dashboard</h1>
    <span class="meta">__REPO_PATH__ · generated __GENERATED_AT__ (issue #17 MVP)</span>
  </header>

  <section>
    <h2>Sessions (epic 主体、Spec v1)</h2>
    <div id="specs" class="spec-grid"></div>
  </section>

  <section>
    <h2>Recent decisions (JSONL、直近 __DECISIONS_LIMIT__ 件)</h2>
    <div id="decisions" class="timeline"></div>
  </section>

  <section>
    <h2>Recent patrols (直近 __PATROLS_LIMIT__ 行)</h2>
    <table id="patrols"><thead><tr><th>日時</th><th>サマリ</th></tr></thead><tbody></tbody></table>
  </section>

  <section>
    <h2>Retro index</h2>
    <table id="retros"><thead><tr><th>date</th><th>file</th></tr></thead><tbody></tbody></table>
  </section>
</div>

<script id="volante-data" type="application/json">__DATA_JSON__</script>
<script>
  const data = JSON.parse(document.getElementById('volante-data').textContent);

  const specsEl = document.getElementById('specs');
  if (data.specs.length === 0) {
    specsEl.innerHTML = '<div class="empty">Spec 未登録</div>';
  } else {
    for (const s of data.specs) {
      const el = document.createElement('div');
      el.className = 'spec';
      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = s.session;
      el.appendChild(name);
      const goal = document.createElement('div');
      goal.className = 'goal';
      goal.textContent = s.spec.goal || '';
      el.appendChild(goal);
      const ul = document.createElement('ul');
      for (const c of (s.spec.acceptance_criteria || [])) {
        const li = document.createElement('li');
        li.textContent = c;
        ul.appendChild(li);
      }
      el.appendChild(ul);
      specsEl.appendChild(el);
    }
  }

  const decEl = document.getElementById('decisions');
  if (data.decisions.length === 0) {
    decEl.innerHTML = '<div class="empty">decisions-YYYY-MM.jsonl 未生成 or 空 (v0.14.0 以降で新規エントリ併記化)</div>';
  } else {
    for (const ev of data.decisions.slice().reverse()) {
      const el = document.createElement('div');
      const branch = String(ev.branch || '');
      const branchClass = branch === '1' ? 'branch-1' : (branch.includes('監督 AI') ? 'branch-oversight' : '');
      el.className = 'event ' + branchClass;
      const head = document.createElement('div');
      head.className = 'head';
      const ts = document.createElement('span'); ts.className = 'ts'; ts.textContent = ev.timestamp || '';
      const br = document.createElement('span'); br.className = 'branch'; br.textContent = '枝 ' + branch;
      const tgt = document.createElement('span'); tgt.className = 'target'; tgt.textContent = ev.target_session || '';
      head.appendChild(ts); head.appendChild(br); head.appendChild(tgt);
      el.appendChild(head);
      const dec = document.createElement('div'); dec.className = 'decision'; dec.textContent = ev.decision || ''; el.appendChild(dec);
      if (ev.rationale) { const r = document.createElement('div'); r.className = 'rationale'; r.textContent = ev.rationale; el.appendChild(r); }
      if (ev.self_review) {
        const rv = document.createElement('div');
        const cls = /^OK/i.test(ev.self_review) ? 'ok' : (/^NG/i.test(ev.self_review) ? 'ng' : '');
        rv.className = 'review ' + cls;
        rv.textContent = ev.self_review;
        el.appendChild(rv);
      }
      decEl.appendChild(el);
    }
  }

  const patBody = document.querySelector('#patrols tbody');
  if (data.patrols.length === 0) {
    patBody.innerHTML = '<tr><td colspan="2" class="empty">patrols.md 空</td></tr>';
  } else {
    for (const row of data.patrols.slice().reverse()) {
      const tr = document.createElement('tr');
      const dt = document.createElement('td'); dt.className = 'dt'; dt.textContent = row.datetime || ''; tr.appendChild(dt);
      const sm = document.createElement('td'); sm.className = 'summary'; sm.textContent = row.summary || ''; tr.appendChild(sm);
      patBody.appendChild(tr);
    }
  }

  const retroBody = document.querySelector('#retros tbody');
  if (data.retros.length === 0) {
    retroBody.innerHTML = '<tr><td colspan="2" class="empty">retro なし</td></tr>';
  } else {
    for (const r of data.retros) {
      const tr = document.createElement('tr');
      const d = document.createElement('td'); d.textContent = r.date || '?'; tr.appendChild(d);
      const f = document.createElement('td');
      const code = document.createElement('code'); code.textContent = r.file; f.appendChild(code);
      tr.appendChild(f);
      retroBody.appendChild(tr);
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
    args = ap.parse_args()

    root = args.repo_root or find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not locate volante repo root (need journal/ + .claude-plugin/)")

    journal = root / "journal"
    specs = load_specs(journal / "specs")
    decisions = load_recent_decisions(journal, args.decisions_limit)
    patrols = load_recent_patrols(journal, args.patrols_limit)
    retros = load_retro_index(journal)

    payload = {"specs": specs, "decisions": decisions, "patrols": patrols, "retros": retros}
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
