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


def fetch_open_issue_count(repo: str) -> dict:
    """Fetch open issue count via gh api search. Returns {"count", "source", "error"}."""
    if not repo or "/" not in repo:
        return {"count": None, "source": "", "error": "invalid repo"}
    try:
        out = subprocess.check_output(
            ["gh", "api", f"search/issues?q=repo:{repo}+is:issue+is:open", "--jq", ".total_count"],
            stderr=subprocess.PIPE, timeout=15,
        )
        return {"count": int(out.decode("utf-8").strip()), "source": f"gh api search/issues repo:{repo}", "error": ""}
    except FileNotFoundError:
        return {"count": None, "source": "", "error": "gh CLI not found"}
    except subprocess.CalledProcessError as e:
        return {"count": None, "source": "", "error": f"gh failed: {e.stderr.decode('utf-8', errors='ignore').strip()[:200]}"}
    except (subprocess.TimeoutExpired, ValueError) as e:
        return {"count": None, "source": "", "error": f"{type(e).__name__}"}


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
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>volante dashboard</h1>
    <span class="meta">__REPO_PATH__ · generated __GENERATED_AT__ (issue #17 MVP)</span>
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

    <div id="tab-epics-container"></div>
  </div>
</div>

<script id="volante-data" type="application/json">__DATA_JSON__</script>
<script>
  const data = JSON.parse(document.getElementById('volante-data').textContent);

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
      const ph = document.createElement('div');
      ph.className = 'placeholder';
      ph.textContent = '(#21 で epic 別の開発者ビューを実装予定 — Goal + acceptance_criteria check list / 開いてる PR + CI / 開いてる issue / 直近 decisions / 監督 AI 判定履歴 等)';
      pane.appendChild(ph);
      tabEpicsContainer.appendChild(pane);
    }
  }

  // ===== PM table =====
  const pmBody = document.querySelector('#pm-table tbody');
  if (data.specs.length === 0) {
    pmBody.innerHTML = '<tr><td colspan="8" class="empty">Spec 未登録</td></tr>';
  } else {
    for (const s of data.specs) {
      const m = s.metrics || {};
      const p = s.progress || {};
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td'); nameTd.className = 'epic-name'; nameTd.textContent = s.session; tr.appendChild(nameTd);
      const repoTd = document.createElement('td'); repoTd.className = 'repo'; repoTd.textContent = s.repo || '(未解決)'; tr.appendChild(repoTd);
      const prioTd = document.createElement('td'); prioTd.textContent = s.priority || '—'; tr.appendChild(prioTd);
      const statusTd = document.createElement('td');
      const badge = document.createElement('span'); badge.className = 'status-badge ' + (m.status || 'on-track');
      badge.textContent = m.status || 'on-track'; statusTd.appendChild(badge); tr.appendChild(statusTd);
      const progTd = document.createElement('td'); progTd.className = 'metric-num';
      if (p.count === 0) { progTd.classList.add('ok'); progTd.textContent = '0'; }
      else if (typeof p.count === 'number') { progTd.textContent = p.count; }
      else { progTd.textContent = '—'; progTd.title = p.error || ''; }
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
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = s.session;
      head.appendChild(name);
      if (s.repo) {
        const repoLabel = document.createElement('span');
        repoLabel.className = 'repo-label';
        repoLabel.textContent = s.repo;
        head.appendChild(repoLabel);
      }
      el.appendChild(head);

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
      const pd = s.progress || {};
      if (pd.count === 0) {
        progValue.textContent = '全 issue closed (0 open)';
        prog.classList.add('done');
      } else if (typeof pd.count === 'number') {
        progValue.textContent = pd.count + ' open issues';
      } else {
        prog.classList.add('unknown');
        progValue.textContent = '(進捗未定義)';
        if (pd.error) progValue.title = pd.error;
      }
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
    ap.add_argument("--no-gh", action="store_true", help="skip gh queries (progress will show '進捗未定義')")
    args = ap.parse_args()

    root = args.repo_root or find_repo_root(Path.cwd())
    if root is None:
        sys.exit("error: could not locate volante repo root (need journal/ + .claude-plugin/)")

    journal = root / "journal"
    specs = load_specs(journal / "specs")
    all_decisions = load_recent_decisions(journal, 0)
    decisions = all_decisions[-args.decisions_limit:] if args.decisions_limit > 0 else all_decisions
    patrols = load_recent_patrols(journal, args.patrols_limit)
    retros = load_retro_index(journal)
    goals_rows = parse_goals_md(journal)

    # Resolve repo + fetch progress per spec (v0.15.4+, cached at generate time per CLAUDE.md 設計原則)
    for spec in specs:
        basename = spec["session"]
        repo = resolve_repo_for_spec(basename, goals_rows)
        spec["repo"] = repo
        if repo and not args.no_gh:
            progress = fetch_open_issue_count(repo)
            spec["progress"] = progress
        else:
            spec["progress"] = {"count": None, "source": "", "error": "no repo resolved" if not repo else "gh skipped"}
        # Attach 優先度 from goals.md (first matching row by repo)
        priority = ""
        for row in goals_rows:
            if row.get("repo") == repo:
                priority = row.get("priority", "")
                break
        spec["priority"] = priority

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

    payload = {"specs": specs, "decisions": decisions, "patrols": patrols, "retros": retros, "goals": goals_rows}
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
