# goals index

差配は必ずここのゴールに紐付ける。**内容は書かない — 正本への参照 + 1 行だけ** (詳細は正本を読む)。
`優先度` 列は **konuma 所有** (volante は変更しない。プロジェクト間の優先順位づけは konuma 専権)。
window id は揮発的 (セッション再起動で変わる) なので session 名 + repo をキーにする。

| session (直近 window) | repo | 正本 | ゴール 1 行 | 優先度 (konuma 所有) | 登録日 |
|---|---|---|---|---|---|
| Cosmos/jingu 経理 kaizen (w24) | ma-navi/pitto | [#427](https://github.com/ma-navi/pitto/issues/427) | jingu effective 0.85+ へ (現状 0.82、証憑受領がトリガー。自力弾は枯渇済み) | 仮: 中 (外部待ち) | 2026-07-07 |
| navibot×Forge 統合 (w34) | ma-navi/navibot | [epic #802](https://github.com/ma-navi/navibot/issues/802) | ADR-0011 a〜f の統合層完成 + cross-user leakage ゲート検証 (#220) 通過 | 仮: 高 | 2026-07-07 |
| payroll kaizen (w59) | ma-navi/pitto | [#365](https://github.com/ma-navi/pitto/issues/365) | payroll 照合 kaizen の再開 (明日=07-08 打ち合わせ後)。待機中はインフラ弾 #488/#464 消化 | 仮: 中 | 2026-07-07 |
| AI agent v1 (w61) | ma-navi/ma_navi_forge | [epic #211](https://github.com/ma-navi/ma_navi_forge/issues/211) | v1 結合完了 — Forge 側完了済み。残: navibot 側 (公開鍵/SSE 送出/by_client 消費) + konuma GCP/実機確認 + #220 | 仮: 高 | 2026-07-07 |
| memory 統治ループ (w69) | /Users/navi (home) | ~/.claude/projects/-Users-navi/memory-audit-log-2026-07-07.md | 定期 memory 監査 (次回 2026-07-14〜21 or 大規模リファクタ直後)。現サイクルは done | 仮: 低 | 2026-07-07 |

- 優先度の初期値はすべて volante の仮置き。**konuma のレビュー・修正待ち**
- tracer 管理 repo が現れた場合は正本列に goal file パスを書く (`.claude/goals/*.md`)
