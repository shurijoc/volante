# Changelog

## [0.3.0] - 2026-07-07

- 巡回義務として context 管理を追加 (判断木の枝 1-5 の意味・優先順位は変更なし):
  - Plan (観測): status bar の `🧠xx%` (context 使用率) と `/clear` ヒント表示の有無を、
    RUNNING/WAITING/IDLE/STUCK の分類と併せて記録する
  - Do: IDLE セッションが `🧠 50% 以上` または `/clear` ヒント表示のとき、
    `/context-reset` → (退避完了確認) → `/clear` → 再開プロンプト送信の 3 ステップを実行する。
    RUNNING/WAITING/STUCK には実行しない。1 巡回で reset するのは最大 1 セッション、
    reset 直後のセッションへの同一巡回内の追加指示も禁止 (全滅・作業破壊リスク回避)
  - volante 自身は context 非依存設計 (毎巡回 state をファイルから読む) なので konuma 判断で `/clear` 可。
    ただし session-only の cron ループの `/clear` 後の生存は未確認 (Unknown) なため巡回時に確認・再設定する
  - 記録は既存の `decisions-YYYY-MM.md` / `templates/decision-entry.md` をそのまま使う (枝 5 内部定型作業として)
- konuma FB (2026-07-07, #3): 「context は定期的にリセットさせることできる？各セッションは低く保ちたい」
  に基づく巡回義務の追加 (判断木自体の枝は変更していないため範囲外の konuma 承認は不要、追加分は
  Act フェーズの通常レビュー対象)

## [0.2.0] - 2026-07-07

- 判断木 v1.1 — 枝 4 (技術的トレードオフ) の低リスク側 (内部かつ可逆) は konuma への事前確認なしに
  volante が判断・実行するよう明記。事前確認が必須なのは枝 1 (不可逆・外部可視・ADR 等ガバナンス) と
  枝 3 (送信元不明) のみ
- 報告フォーマット (5. 報告): 「確認項目」を「確認待ち (枝 1/3)」と「自律判断 (konuma レビュー対象、
  枝 2/4 低リスク/5)」に分離
- `templates/decision-entry.md` に `konuma レビュー` 欄を追加 (既定値: 未 / 未・OK・NG+理由 で更新)
- Act (振り返り) の抽出対象に「konuma レビューで NG が付いたエントリ」を追加し、レビュー欄の反映方法
  (konuma が直接埋める / チャット指摘を次回巡回で転記) を明記
- konuma FB (2026-07-07, #2): 「判断精度をレビューで上げたい」に基づく判断木自体の変更として konuma 承認済み

## [0.1.0] - 2026-07-07

- 初版 scaffold: plugin manifest + `skills/volante/SKILL.md` (PDCA 1 巡回 = 1 起動)
- 判断木 v1 (不可逆・外部可視 / tracer autonomy / 送信元不明 / トレードオフ / 内部定型 の 5 枝)
- 判断ログ (`journal/`) と decision-entry テンプレート
- Act (振り返り): decisions 10 件ごと、判断木変更は konuma 承認必須
