#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from volante journal state.

Reads:
  - journal/specs/*.json         (Epic Spec v2, keyed by repo × epic)
  - journal/attachments.json     (session ↔ Epic Spec, volatile, v0.16.0+)
  - journal/decisions-<YYYY-MM>.jsonl (latest month, last N events)
  - journal/patrols.md            (last few rows)
  - journal/retro-*.md           (index only)

Outputs:
  - journal/dashboard.html       (self-contained, JSON embedded via <script>)

Design principle (CLAUDE.md 設計原則, SKILL.md 芯 9):
  DB / サーバー不要、HTML + JSON でローカル完結。The output is a single .html
  file with embedded JSON. Open with `open journal/dashboard.html` — no server.

Status: v0.16.0 (issue #17 継続、Spec 主キーを repo × epic に移行)。
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
    """Load Epic Spec v2 files. Sort by (repo, epic.id) for stable grouping."""
    specs = []
    if not specs_dir.is_dir():
        return specs
    for path in sorted(specs_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: could not read {path}: {e}", file=sys.stderr)
            continue
        epic = data.get("epic") or {}
        specs.append({
            "basename": path.stem,
            "repo": data.get("repo", ""),
            "epic_id": epic.get("id", ""),
            "epic_url": epic.get("url", ""),
            "goal": data.get("goal", ""),
            "acceptance_criteria": data.get("acceptance_criteria", []),
        })
    specs.sort(key=lambda s: (s["repo"], s["epic_id"]))
    return specs


def load_attachments(journal: Path) -> dict:
    path = journal / "attachments.json"
    if not path.exists():
        return {"generated_at": "", "attachments": [], "unattached_sessions": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: could not read {path}: {e}", file=sys.stderr)
        return {"generated_at": "", "attachments": [], "unattached_sessions": []}


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
  .repo-group { margin-bottom: 20px; }
  .repo-group:last-child { margin-bottom: 0; }
  .repo-group h3 { margin: 0 0 8px; font-family: var(--mono); font-size: 13px;
                   color: var(--text); font-weight: 700; }
  .epic-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
               gap: 12px; }
  .epic { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: var(--bg); }
  .epic .epic-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
  .epic .epic-id { font-family: var(--mono); font-size: 13px; color: var(--accent); font-weight: 600; }
  .epic .epic-id a { color: inherit; text-decoration: none; }
  .epic .epic-id a:hover { text-decoration: underline; }
  .epic .basename { font-family: var(--mono); font-size: 10px; color: var(--text-mute); }
  .epic .goal { margin-bottom: 8px; font-size: 13px; }
  .epic ul { margin: 0 0 8px; padding-left: 18px; font-size: 12.5px; }
  .epic li { margin-bottom: 2px; }
  .attach-list { display: flex; gap: 6px; flex-wrap: wrap; padding-top: 8px;
                 border-top: 1px dashed var(--border); }
  .attach-chip { display: inline-flex; gap: 4px; align-items: baseline;
                 font-family: var(--mono); font-size: 11px; padding: 2px 8px;
                 border-radius: 12px; border: 1px solid var(--border);
                 background: var(--surface); }
  .attach-chip.high { border-color: var(--ok); background: var(--ok-bg); color: var(--ok); }
  .attach-chip.medium { border-color: var(--warn); background: var(--warn-bg); color: var(--warn); }
  .attach-chip.low { border-color: var(--warn); background: var(--warn-bg); color: var(--warn);
                     text-decoration: underline dotted; }
  .attach-chip .wid { font-weight: 700; }
  .attach-chip .hint { color: var(--text-mute); font-weight: 400; }
  .attach-empty { font-size: 11px; color: var(--text-mute); padding-top: 8px;
                  border-top: 1px dashed var(--border); font-style: italic; }
  .unattached { border-left: 3px solid var(--warn); background: var(--warn-bg);
                padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; }
  .unattached .u-head { font-family: var(--mono); font-size: 12px; font-weight: 700;
                        color: var(--warn); margin-bottom: 4px; }
  .unattached .u-body { font-size: 12.5px; }
  .attach-meta { font-family: var(--mono); font-size: 11px; color: var(--text-mute); }
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
    <span class="meta">__REPO_PATH__ · generated __GENERATED_AT__ · attachments __ATTACH_AT__ (issue #17、v0.16.0 = repo × epic 主キー)</span>
  </header>

  <section id="unattached-section" style="display:none">
    <h2>Attention: Spec 未登録の稼働セッション</h2>
    <div id="unattached"></div>
  </section>

  <section>
    <h2>Epics (Spec v2、repo × epic) — 各 epic の attached sessions つき</h2>
    <div id="epics"></div>
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

  // Build spec -> [attachments] index
  const attachIdx = {};
  for (const a of (data.attachments && data.attachments.attachments) || []) {
    if (!attachIdx[a.spec]) attachIdx[a.spec] = [];
    attachIdx[a.spec].push(a);
  }

  // Group specs by repo
  const byRepo = {};
  for (const s of data.specs) {
    if (!byRepo[s.repo]) byRepo[s.repo] = [];
    byRepo[s.repo].push(s);
  }

  const epicsEl = document.getElementById('epics');
  const repos = Object.keys(byRepo).sort();
  if (repos.length === 0) {
    epicsEl.innerHTML = '<div class="empty">Spec 未登録</div>';
  } else {
    for (const repo of repos) {
      const group = document.createElement('div');
      group.className = 'repo-group';
      const h3 = document.createElement('h3');
      h3.textContent = repo;
      group.appendChild(h3);
      const grid = document.createElement('div');
      grid.className = 'epic-grid';
      for (const s of byRepo[repo]) {
        const card = document.createElement('div');
        card.className = 'epic';
        const head = document.createElement('div');
        head.className = 'epic-head';
        const eid = document.createElement('span');
        eid.className = 'epic-id';
        if (s.epic_url) {
          const a = document.createElement('a');
          a.href = s.epic_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = s.epic_id;
          eid.appendChild(a);
        } else {
          eid.textContent = s.epic_id;
        }
        head.appendChild(eid);
        const bn = document.createElement('span');
        bn.className = 'basename'; bn.textContent = s.basename;
        head.appendChild(bn);
        card.appendChild(head);
        const goal = document.createElement('div');
        goal.className = 'goal'; goal.textContent = s.goal || '';
        card.appendChild(goal);
        const ul = document.createElement('ul');
        for (const c of s.acceptance_criteria || []) {
          const li = document.createElement('li'); li.textContent = c; ul.appendChild(li);
        }
        card.appendChild(ul);
        // Attached sessions
        const atts = attachIdx[s.basename] || [];
        if (atts.length === 0) {
          const em = document.createElement('div');
          em.className = 'attach-empty';
          em.textContent = 'attached sessions なし (attachments.json 未再構築 or 未 attach)';
          card.appendChild(em);
        } else {
          const list = document.createElement('div');
          list.className = 'attach-list';
          for (const a of atts) {
            const chip = document.createElement('span');
            chip.className = 'attach-chip ' + (a.confidence || 'low');
            const wid = document.createElement('span'); wid.className = 'wid'; wid.textContent = a.window_id;
            chip.appendChild(wid);
            if (a.session_hint) {
              const hint = document.createElement('span'); hint.className = 'hint'; hint.textContent = a.session_hint;
              chip.appendChild(hint);
            }
            if (a.confidence && a.confidence !== 'high') {
              const c = document.createElement('span'); c.className = 'hint'; c.textContent = '(' + a.confidence + ')';
              chip.appendChild(c);
            }
            chip.title = (a.reason || '') + (a.branch ? ' · branch: ' + a.branch : '') + (a.cwd ? ' · cwd: ' + a.cwd : '');
            list.appendChild(chip);
          }
          card.appendChild(list);
        }
        grid.appendChild(card);
      }
      group.appendChild(grid);
      epicsEl.appendChild(group);
    }
  }

  // Unattached sessions
  const unattached = (data.attachments && data.attachments.unattached_sessions) || [];
  if (unattached.length > 0) {
    document.getElementById('unattached-section').style.display = '';
    const uEl = document.getElementById('unattached');
    for (const u of unattached) {
      const div = document.createElement('div');
      div.className = 'unattached';
      const h = document.createElement('div');
      h.className = 'u-head'; h.textContent = 'Spec 設定要求: ' + (u.window_id || '?');
      div.appendChild(h);
      const b = document.createElement('div');
      b.className = 'u-body';
      const reason = document.createElement('div'); reason.textContent = u.reason || ''; b.appendChild(reason);
      if (u.cwd) {
        const meta = document.createElement('div'); meta.className = 'attach-meta'; meta.textContent = 'cwd: ' + u.cwd; b.appendChild(meta);
      }
      div.appendChild(b);
      uEl.appendChild(div);
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
    attachments = load_attachments(journal)
    decisions = load_recent_decisions(journal, args.decisions_limit)
    patrols = load_recent_patrols(journal, args.patrols_limit)
    retros = load_retro_index(journal)

    payload = {
        "specs": specs,
        "attachments": attachments,
        "decisions": decisions,
        "patrols": patrols,
        "retros": retros,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    now_str = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    attach_at = attachments.get("generated_at", "(未生成)")

    html = (TEMPLATE
            .replace("__REPO_PATH__", escape(str(root)))
            .replace("__GENERATED_AT__", escape(now_str))
            .replace("__ATTACH_AT__", escape(attach_at))
            .replace("__DECISIONS_LIMIT__", str(args.decisions_limit))
            .replace("__PATROLS_LIMIT__", str(args.patrols_limit))
            .replace("__DATA_JSON__", payload_json.replace("</", "<\\/")))

    out = args.out or (journal / "dashboard.html")
    out.write_text(html, encoding="utf-8")
    n_att = len(attachments.get("attachments") or [])
    n_un = len(attachments.get("unattached_sessions") or [])
    print(f"wrote {out} ({len(html)} bytes, {len(specs)} specs, {n_att} attachments, {n_un} unattached, {len(decisions)} decisions)")


if __name__ == "__main__":
    main()
