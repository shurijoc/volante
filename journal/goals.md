# goals index

差配は必ずここのゴールに紐付ける。**内容は書かない — 正本への参照 + 1 行だけ** (詳細は正本を読む)。
`優先度` 列は **konuma 所有** (volante は変更しない。プロジェクト間の優先順位づけは konuma 専権)。
**repo × 正本 を主キー**とし、session 役割名を人間可読ラベルとして併記する
(session id は揮発的なため goals.md には載せない。決定ログ・巡回ログ側で実務的に使う)。

## 進行中

| repo | 正本 | session (役割名) | ゴール 1 行 | 優先度 (konuma 所有) | 登録日 |
|---|---|---|---|---|---|
| ma-navi/pitto | [#365](https://github.com/ma-navi/pitto/issues/365) + `pitto/.claude/goals/payroll.md` (tracer, autonomy L2) | payroll kaizen | payroll 方向転換 (konuma 決定 07-14): payroll-import の kaizen-loop 統合 #534 (PR #539 進行中)。旧照合 target (#365) と tracer goal file の扱いは要整理。インフラ弾 #488 残 | 高 (konuma 2026-07-14) | 2026-07-07 |
| ma-navi/navibot | [epic #802](https://github.com/ma-navi/navibot/issues/802) | navibot×Forge 統合 | ADR-0011 a〜f の統合層完成 + cross-user leakage ゲート検証 (#220) 通過 | 高 (konuma 2026-07-14) | 2026-07-07 |
| /Users/navi (home) | ~/.claude/projects/-Users-navi/memory-audit-log-2026-07-07.md | memory 統治ループ | 定期 memory 監査 round 2。**konuma 決定 07-14「すぐ実施」** — volante が read-only 監査 subagent を起動済み、適用は konuma 承認ゲート維持 | 仮: 低 (実施中) | 2026-07-07 |
| ma-navi/navibot | https://github.com/ma-navi/navibot/issues/802 | navibot-ai-chat-db-update | navibot #802 を本文で言及する open issue を 0 にする (2026-07-14 実測 2 件: #900/#836。#804 は PR #872 merge で close) | 高 (konuma 2026-07-14、navibot×Forge 統合系として) | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/500 | pitto-cosmos-book-keeping | kaizen loop で cosmos の記帳仕訳精度を 90% にする。※07-13: 自力弾枯渇 Fact 確定 — 達成宣言 or 別ゴール移行は konuma 判断待ち | 並列 | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/501 | pitto-jingu-book-keeping | kaizen loop で jingu の記帳仕訳精度を 90% にする | 並列 | 2026-07-10 |
| ma-navi/ma_navi_forge | https://github.com/ma-navi/ma_navi_forge/issues/314 | forge-mock-parity | mock 差分対象の open issue (scope:forge + plan-ready) を 0 にする (2026-07-14 実測 5 件: #264/#265/#266/#268/#304) | 並列 | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/502 | pitto-ma-navi-book-keeping | ma-navi 全体の book keeping (cosmos / jingu 等) の記帳仕訳精度を 90% にする (cosmos/jingu の個別 epic を統べる umbrella) | 高 (konuma 2026-07-14、navi org 分を優先) | 2026-07-10 |

## 達成済み (2026-07-14 整理)

| repo | 正本 | session (役割名) | 達成内容 (gh 実測) | 登録日 → 達成 |
|---|---|---|---|---|
| ma-navi/pitto | issue-495 + PR #496 | ma_navi org kaizen loop 立ち上げ | PR #496 merged (2026-07-08、fe1405c)。follow-up 3 件 (drift 3 件・schema-only PR verify 問題) は konuma 判断待ちのまま | 2026-07-08 → 07-08 |
| ma-navi/ma_navi_forge | [epic #211](https://github.com/ma-navi/ma_navi_forge/issues/211) | AI agent v1 | #211 CLOSED (gh 実測 2026-07-14)。v1 結合完了 | 2026-07-07 → 07-14 確認 |
| ma-navi/ma_navi_forge | https://github.com/ma-navi/ma_navi_forge/issues/313 | forge-ai-chat-db-update | #313 CLOSED + scope:ai-agent open issue 0 件 (gh 実測 2026-07-14)。spec は `specs/_archive/` へ移動 | 2026-07-10 → 07-14 確認 |

- 優先度の初期値はすべて volante の仮置き。**konuma のレビュー・修正待ち**
- 1 repo に複数 epic が並走する場合は行を複数持つ
- tracer 管理 repo が現れた場合は正本列に goal file パスを書く (`.claude/goals/*.md`)
- session id (w24 等) は adapter/セッション再起動で変わる揮発値。実務で使う際は決定ログ・巡回ログ側にのみ残す
- 達成済み epic の spec は `journal/specs/_archive/` に移動する (2026-07-14 運用開始)
