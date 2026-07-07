# Changelog

## [0.5.0] - 2026-07-07

- 「5. 報告」の後に「6. ループ自動停止」節を追加 (#5): `/loop`・cron でループ運用中、
  **2 巡回連続で「送った指示 0 かつ 対象セッションの状態変化なし」** となったら
  `CronList` → `CronDelete` でループの cron job を止め、最終報告に
  「ループ自動停止 (2 巡回無変化)。再開は `/loop 5m /volante`」と明記する
  - 「状態変化なし」の定義: 全セッションの分類 (RUNNING/WAITING/IDLE/STUCK)・進行フェーズが前巡回と
    同一で、差配・確認事項の変化もないこと。RUNNING 継続は「変化なし」に含む
    (worker が黙々と動いている間の空巡回が対象)
  - 判定は `journal/patrols.md` の直近行との比較で行う。指示を送った・状態が変化した時点で連続カウントはリセット
  - 停止時も `patrols.md` に停止行を記録して commit/push する (通常の Check 手順に従う)
  - 注意書き: cron job はループを起動したセッションが所有するため、停止操作 (`CronDelete`) は
    同一セッション内でのみ可能。対象ジョブが見当たらない場合は自動停止をスキップし konuma に手動停止を依頼する
  - 判断木・巡回義務 (1〜5) 自体の判定基準・優先順位は変更なし
- konuma 決定 (2026-07-07, #5): 「2回やって変更無ければloop止めるようにして」

## [0.4.0] - 2026-07-07

- goals index — 差配を「都度の発明」から「ゴールとの差分導出」に変更 (#4):
  - 正本の 3 層構成を明記: 各 repo の epic issue / tracer 管理 repo は goal file / volante は
    `journal/goals.md` という薄い index (参照 + ゴール 1 行のみ) を持つだけ
  - 「0. 準備」: 巡回冒頭で `$VOLANTE_REPO/journal/goals.md` を読む手順を追加。
    未登録セッションは「ゴール未登録」扱い
  - 「2. Do」に枝共通ルールとして「差配とゴール紐付け」を追加: 指示文の「目的」はゴールから導出する。
    ゴール未登録セッションへの差配は報告に明記し、konuma にエントリ追加を促す
  - 「2. Do」に「乖離チェック」を追加: 正本 (epic issue / goal file) と goals.md の 1 行サマリが
    食い違っていたら goals.md 側を正本に合わせて更新する (参照 + 1 行のみの更新で低リスクなため
    事前確認不要)。更新した旨は報告に載せる
  - コンセプト節に項目 7 を追加: `goals.md` の `優先度` 列は konuma 専有。volante はプロジェクト間の
    優先順位を変えず、ゴール内の次アクション導出のみ自律判断する
  - `templates/goals-template.md` を新設 (表形式: window/session | repo | 正本 | ゴール 1 行 |
    優先度 (konuma 所有) | 登録日。内容を書かず参照 + 1 行だけに限定する制約を注記)
  - `journal/README.md` に `goals.md` の行を追加
  - goals.md の初期データ投入は本リリースの範囲外 (main session 側で実施)
- konuma 決定 (2026-07-07, #4)。判断木の枝 1-5 自体の意味・優先順位は変更なし

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
