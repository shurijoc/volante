# goals index (v0.16.0+ 主キー = repo × epic)

差配は必ずここのゴールに紐付ける (SKILL.md 4. 差配とゴール紐付け)。**Spec 内容は Spec file が正**、
本ファイルは人間可読の index。`優先度` 列は **konuma 所有** (volante は変更しない、SKILL.md 芯 7)。
session ↔ Epic Spec の attach は `journal/attachments.json` (揮発、巡回で自動再構築、SKILL.md 7.1) 側で管理する。

| repo | epic | Spec | 正本 URL | 優先度 (konuma 所有) | 登録日 |
|---|---|---|---|---|---|
| ma-navi/pitto | issue-495 | [`specs/ma-navi--pitto__issue-495.json`](specs/ma-navi--pitto__issue-495.json) | https://github.com/ma-navi/pitto/issues/495 | 仮: 中 (達成済み) | 2026-07-08 |
| ma-navi/pitto | issue-365-payroll | [`specs/ma-navi--pitto__issue-365-payroll.json`](specs/ma-navi--pitto__issue-365-payroll.json) | https://github.com/ma-navi/pitto/issues/365 (+ `pitto/.claude/goals/payroll.md` tracer L2) | 仮: 中 | 2026-07-07 |
| ma-navi/navibot | epic-802 | [`specs/ma-navi--navibot__epic-802.json`](specs/ma-navi--navibot__epic-802.json) | https://github.com/ma-navi/navibot/issues/802 | 仮: 高 | 2026-07-07 |
| ma-navi/ma_navi_forge | epic-211 | [`specs/ma-navi--ma_navi_forge__epic-211.json`](specs/ma-navi--ma_navi_forge__epic-211.json) | https://github.com/ma-navi/ma_navi_forge/issues/211 | 仮: 高 | 2026-07-07 |
| home/memory-governance | audit-2026-07-14 | [`specs/home--memory-governance__audit-2026-07-14.json`](specs/home--memory-governance__audit-2026-07-14.json) | `~/.claude/projects/-Users-navi/memory-audit-log-2026-07-07.md` | 仮: 低 | 2026-07-07 |

- 優先度の初期値はすべて volante の仮置き。**konuma のレビュー・修正待ち**
- 1 repo に複数 epic が並走する場合は行を複数持つ (現状 ma-navi/pitto は 2 epic)
- tracer 管理 repo が現れた場合は正本 URL 列に goal file パス (`<repo>/.claude/goals/*.md`) を併記する
- 現在どの session (kitty window) がどの epic を担当しているかは `journal/attachments.json` を参照
