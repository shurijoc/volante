# goals index

差配は必ずここのゴールに紐付ける。**内容は書かない — 正本への参照 + 1 行だけ** (詳細は正本を読む)。
`優先度` 列は **konuma 所有** (volante は変更しない。プロジェクト間の優先順位づけは konuma 専権)。
**repo × 正本 を主キー**とし、session 役割名を人間可読ラベルとして併記する
(session id は揮発的なため goals.md には載せない。決定ログ・巡回ログ側で実務的に使う)。

| repo | 正本 | session (役割名) | ゴール 1 行 | 優先度 (konuma 所有) | 登録日 |
|---|---|---|---|---|---|
| ma-navi/pitto | issue-495 (M&A ナビ org 追加) + PR #496 (self-check) | ma_navi org kaizen loop 立ち上げ | 新規 ma_navi org の scaffold + kaizen-loop verify を通し PR #496 を merge まで **達成 (2026-07-08 18:18 UTC merged、fe1405c で main 反映済み、後片付け完了)**。follow-up 3 件は konuma 判断待ち (drift 3 件・schema-only PR verify 問題) | 仮: 中 (達成済み) | 2026-07-08 |
| ma-navi/pitto | [#365](https://github.com/ma-navi/pitto/issues/365) + `pitto/.claude/goals/payroll.md` (tracer, autonomy L2) | payroll kaizen | payroll 照合 kaizen の再開 (明日=07-08 打ち合わせ後)。待機中はインフラ弾 #488/#464 消化 | 仮: 中 | 2026-07-07 |
| ma-navi/navibot | [epic #802](https://github.com/ma-navi/navibot/issues/802) | navibot×Forge 統合 | ADR-0011 a〜f の統合層完成 + cross-user leakage ゲート検証 (#220) 通過 | 仮: 高 | 2026-07-07 |
| ma-navi/ma_navi_forge | [epic #211](https://github.com/ma-navi/ma_navi_forge/issues/211) | AI agent v1 | v1 結合完了 — Forge/navibot 両側完了・結合テスト green (07-08)。残: konuma 実機確認 + WAF #6058 判断 + #220。再発防止は起票済み (#257/#258、PR #6057 merge 待ち) | 仮: 高 | 2026-07-07 |
| /Users/navi (home) | ~/.claude/projects/-Users-navi/memory-audit-log-2026-07-07.md | memory 統治ループ | 定期 memory 監査 (次回 2026-07-14〜21 or 大規模リファクタ直後)。現サイクルは done | 仮: 低 | 2026-07-07 |
| ma-navi/navibot | https://github.com/ma-navi/navibot/issues/802 | navibot-ai-chat-db-update | navibot #802 (ADR-0011 個人スコープ操作) を本文で言及する navibot open issue を 0 にする (現在 5 件: #804/#835/#836/#838/#839) | 並列 | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/500 | pitto-cosmos-book-keeping | kaizen loop で cosmos の記帳仕訳精度を 90% にする | 並列 | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/501 | pitto-jingu-book-keeping | kaizen loop で jingu の記帳仕訳精度を 90% にする | 並列 | 2026-07-10 |
| ma-navi/ma_navi_forge | https://github.com/ma-navi/ma_navi_forge/issues/313 | forge-ai-chat-db-update | AI チャットからの DB 更新関連の open issue (ma_navi_forge の scope:ai-agent) を 0 にする (現在 3 件: #140/#238/#260) | 並列 | 2026-07-10 |
| ma-navi/ma_navi_forge | https://github.com/ma-navi/ma_navi_forge/issues/314 | forge-mock-parity | mock 差分対象の open issue (ma_navi_forge の scope:forge + plan-ready) を 0 にする (現在 12 件) | 並列 | 2026-07-10 |
| ma-navi/pitto | https://github.com/ma-navi/pitto/issues/502 | pitto-ma-navi-book-keeping | ma-navi 全体の book keeping (cosmos / jingu 等) の記帳仕訳精度を 90% にする (cosmos/jingu の個別 epic を統べる umbrella) | 並列 | 2026-07-10 |

- 優先度の初期値はすべて volante の仮置き。**konuma のレビュー・修正待ち**
- 1 repo に複数 epic が並走する場合は行を複数持つ (現状 ma-navi/pitto は 2 行)
- tracer 管理 repo が現れた場合は正本列に goal file パスを書く (`.claude/goals/*.md`)
- session id (w24 等) は adapter/セッション再起動で変わる揮発値。実務で使う際は決定ログ・巡回ログ側にのみ残す
