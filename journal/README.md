# journal — volante の判断ログ置き場

volante skill が巡回時に書き込む。すべてここ (volante repo 側) に集約し、対象 repo 側には何も書かない
(設計判断 2026-07-07、`../CLAUDE.md` 参照)。

| ファイル | 内容 |
|---|---|
| `decisions-YYYY-MM.md` | 判断ログ本体。1 判断 1 エントリ (雛形: `../skills/volante/templates/decision-entry.md`) |
| `patrols.md` | 巡回 1 回 = 1 行のサマリ |
| `retro-YYYY-MM-DD.md` | Act フェーズの振り返り (雛形: `../skills/volante/templates/retro-template.md`)。判断木更新案はここに書き konuma 承認後に SKILL.md へ反映 |
| `goals.md` | セッション横断の薄い index。正本 (epic issue / tracer goal file) への参照 + ゴール 1 行のみ (雛形: `../skills/volante/templates/goals-template.md`)。内容は書かず、乖離時は正本に合わせて更新する。`優先度` 列は konuma 専有 |
