# Changelog

## [0.16.2] - 2026-07-10

- **dashboard に対話的フィルタ + goal 履歴を追加** (issue #29, #30):
  - **対話的フィルタ** (#29): 全体タブの Recent decisions section 直上に `Decisions フィルタ`
    section を新設。枝別 (全 / 1〜5 / 監督 AI、chip multi-select) / session 別 (select、現存 spec
    のみ列挙) / 期間 (全期間 / 24h / 7d / 今月、radio、デフォルト今月) / 監督 AI のみ (checkbox、
    枝別と AND) の 4 軸で `data.decisions_all` を client-side in-memory filter する。フィルタ状態は
    `location.hash` (`#branch=1&session=...&period=...&osonly=1` の URLSearchParams 形式) に同期し、
    リロード・ブラウザ戻る/進むでも復元される。旧 #28 の「今月のみ/全期間」ボタン (`.scope-btn`) は
    新フィルタの期間 radio に統合・撤去 (機能的に上位互換、回帰なし)
  - **goal 更新履歴** (#30): `dashboard-generate.py` に `load_spec_history()` を追加。
    `git log --follow --name-status` で `journal/specs/<spec>.json` の全 revision (rename 追跡込み)
    を辿り、各 revision 時点の `goal` を `git show <hash>:<path>` で取得して
    `data.spec_history[spec_slug] = [{ts, goal, hash, hash_short}, ...]` (新しい順) を JSON に載せる。
    各 epic タブの Head 直下に「Goal 履歴 (N revisions)」の `<details>` を追加し、展開すると
    revision を新しい順に並べ、直前 revision との word 単位 diff (追加 = 緑 `.diff-add`、削除 = 赤
    `.diff-del` の取り消し線) を自前の LCS ベース diff で表示 (外部 chart/diff library 不使用、
    CLAUDE.md 設計原則どおり)。revision が 1 件 (新規 spec) または git 追跡外のファイルは
    section 自体を出さない
  - 検証: jsdom で合成データ (複数枝・複数 session・月またぎ event、3 revision の goal 変遷 spec、
    1 revision のみの spec) を描画し、chip/select/radio/checkbox 操作での絞り込み件数・URL hash
    書き込み/復元・reset・goal diff の追加/削除 span・1 revision spec でのセクション非表示を自動
    アサートで確認。実 repo データ (`journal/`) でも dashboard-generate.py 実行 + jsdom 描画で
    エラー無し、実際の goal 文言変遷 (rename に伴う微修正) の diff 表示も確認
- Spec schema・判断木・芯には変更なし。`journal/dashboard.html` を再生成しコミットに含める
- konuma 判断待ち: なし (UI 拡張のみ。2 issue とも acceptance criteria 通り実装)

## [0.16.1] - 2026-07-10

- **dashboard を 3 点強化** (issue #26, #27, #28):
  - **監督 AI 判定の詳細をインライン展開表示** (#26): `renderEvent()` を 監督 AI event (`branch` に
    "監督 AI" を含む) とそれ以外で分岐。監督 AI event はサマリ行 (時刻/枝/対象/判断) は従来どおり
    常時表示しつつ、`rationale` / `self_review` / `evidence` / `konuma_review` / (存在すれば)
    `oversight_verdict` / `oversight_evidence` を `<details>` 折りたたみ (`event-detail`) の中に monospace
    で表示するよう変更。非監督 event は従来の inline 表示のまま (回帰なし)
  - **retro 本文の折りたたみ表示** (#27): `dashboard-generate.py` の `load_retro_index()` が
    `journal/retro-*.md` の本文を先頭 2000 文字で truncate (超過時は `... [continued]` 付き `truncated: true`)
    して JSON に載せる。dashboard 側は Retro index を表形式から `<details><summary>date + file link</summary>
    <pre>本文</pre></details>` の折りたたみリスト (`.retro-list`) に変更。file リンクは summary 内に残るので
    従来どおりクリックで元 md に遷移できる
  - **前月以前の decisions ログを横断表示** (#28): `load_recent_decisions()` は current-month
    `decisions-YYYY-MM.jsonl` 専用のまま (PM table の指標計算はこれまでどおり今月のみ基準、回帰なし)。
    新設 `load_all_decisions()` が `decisions-*.jsonl` を glob して全月ぶんを時系列連結し、
    payload に `decisions_all` として追加。全体タブの Recent decisions timeline に
    「今月のみ / 全期間」切替ボタン (`.scope-btn`) を追加 (デフォルト: 今月のみ = 既存挙動維持)。
    epic タブ側の「直近 decisions」「監督 AI 判定履歴」フィルタは `decisions_all` を参照するよう変更し、
    月をまたいだ過去 event も対象セッションで絞り込めるようにした (表示件数上限は既存の
    `--decisions-limit` を両リストに同じく適用)
  - 実装中に判明した不具合を修正: `OVERSIGHT_DETAIL_FIELDS` の `const` 宣言をスクリプト先頭に移動。
    タブ構築ループが `renderEpicTab` → `renderEvent` を同期呼び出しする際、宣言前の temporal dead zone
    で `ReferenceError` が発生し dashboard 全体が描画不能になっていた (jsdom での DOM 実行テストで検出)
  - 検証: jsdom で decisions 複数月・監督 AI event・2000 文字超 retro を含む合成データを描画し、
    scope 切替・詳細展開・retro truncate・epic タブ全期間フィルタの期待動作を自動アサートで確認。
    実 repo データ (`journal/`) でも dashboard-generate.py 実行 + jsdom 描画でエラー無しを確認
- Spec schema・判断木・芯には変更なし。`journal/dashboard.html` を再生成しコミットに含める
- konuma 判断待ち: なし (UI 拡張のみ。3 issue とも acceptance criteria 通り実装)

## [0.16.0] - 2026-07-10

- **TUI adapter 層を導入し kitty 固定を解いた** (issue #25):
  - `skills/volante/adapters/interface.md` に 5 primitive (`list_sessions` / `read_screen` /
    `send_text` / `send_key` / `self_id`) の contract を明文化。各 adapter は
    `skills/volante/adapters/<adapter>.sh` という単一 CLI スクリプトとして実装する
  - `skills/volante/adapters/kitty.sh`: 既存の `kitty @ ls` / `get-text` / `send-text` 呼び出しをここに
    集約 (SKILL.md からの直書きを撤去)。konuma の M1 Mac 環境で `list_sessions` / `read_screen` /
    `self_id` の実機動作を確認し、既存挙動と一致することを検証済み (回帰なし)
  - `skills/volante/adapters/tmux.sh`: 最小実装を新規追加 (`list-panes` / `capture-pane` / `send-keys`
    ベース。send_key は esc/enter/ctrl-c/up/down)。kitty との機能パリティは要求せず、足りない部分は
    既存の「実測不可 → 人間確認」設計に委ねる
  - `~/.config/volante/config.json` (git 管理外、PC ごとの local config、schema:
    `skills/volante/templates/local-config.schema.json`) を新設。`/volante` 初回起動時に config が
    無ければ AskUserQuestion で adapter を選ばせ対話生成する (SKILL.md 7.1)。未実装 adapter
    (wezterm/manual) が選ばれた場合は選び直させる
  - SKILL.md 7.1〜7.4 (準備・観測・適用・検証) と `scripts/oversight-subagent.md`、
    `templates/decision-event.schema.json` / `decision-event.example.json` / `decision-entry.md` から
    kitty 固有コマンドの直書きを除去し、`$ADAPTER` 経由の primitive 呼び出しに置き換え
  - **判断木 (4. checklist) と芯 (1. role_and_goal の変更禁止の芯) はロジック不変** — adapter 層は
    「どう画面を読み・どう送るか」の実装詳細のみを差し替える (issue #25 の要求どおり)
  - `README.md` / `CLAUDE.md` / `.claude-plugin/plugin.json` の記述を adapter 層前提に更新。
    CLAUDE.md には 2026-07-07 の「kitty 専用 (YAGNI)」決定を覆した旨を追記

## [0.15.9] - 2026-07-10

- **新規 skill `/volante-epic`: epic (Spec) の追加・削除・編集を対話的に** (issue #24):
  `journal/specs/*.json` の手書き + `journal/goals.md` 行の手編集という 2 段階の運用を、
  1 回の対話で両方同時に更新するツールに置き換えた
  - `skills/volante-epic/SKILL.md` + `skills/volante-epic/scripts/epic_tool.py` (add/remove/edit/list の
    4 subcommand)。スクリプトはファイル書き込みのみ (`dashboard-generate.py` と同じ分離)、
    git add/commit/push は SKILL.md の手順側で行う
  - `add`: `kpi_sheet_tab` (`gid`+`name`) が未指定だと拒否される (issue #23 依存)。`優先度` 列は聞かず
    `未指定` を書く (konuma 専有、`skills/volante/SKILL.md` 芯 7 に従う)
  - `remove`: `journal/specs/<slug>.json` を `journal/specs/_archive/<slug>.json` へ移動 (削除ではなく
    アーカイブ) し、goals.md の該当行を削除する。SKILL.md 側で実行前に konuma へ 1 度確認する運用とした
  - `edit`: 指定したフィールドだけを個別上書き。`goal` を編集すると spec と goals.md の「ゴール 1 行」列を
    両方同期し乖離を防ぐ。`acceptance_criteria` はフルリスト置換 (差分マージなし)
  - **schema 検証は `jsonschema` パッケージを使わず自前の最小 validator** (type/required/
    additionalProperties/properties/minLength/minItems/items のみ対応) で `skills/volante/templates/
    spec-template.json` を都度読んで検証する。この環境に `jsonschema` が未インストールで、
    かつ現行 schema がこのサブセットしか使っていないため (依存追加なし、既存スクリプト群と同じ方針)
  - **このスキル発の goals.md 行に限り `session (役割名)` セルを slug そのものにする**ことで
    remove/edit がどの行かを一意に決める。既存の手書き行 (`ma_navi org kaizen loop 立ち上げ` 等) は
    slug 形式ではないため対象外のまま (触らない)
  - `.claude-plugin/plugin.json` の description に `/volante-epic` を追記、version を 0.15.9 に
- 判断木・芯・Spec schema 自体は不変 (このスキルは既存 schema を読むだけで拡張しない)

## [0.15.8] - 2026-07-10

- **dashboard.html を進捗表示・リンク・patrols/retro の 4 点で強化** (issue #22):
  - **進捗を `epic_label` ベースに切替可能化** (Spec schema v1.2):
    `templates/spec-template.json` に `epic_label` (任意 string) を追加。
    指定があれば `dashboard-generate.py` の `fetch_open_issue_count()` が
    `gh api search/issues?q=repo:<repo>+label:"<epic_label>"+is:issue+is:{open|closed}` で
    open/closed 両方を取り、dashboard は `X / (X+Y) closed` 形式で epic 単位の進捗を出す (100% で done 色)。
    未指定なら repo 全体の open 総数を fallback (後方互換)。
  - **epic 名を GitHub issues (label 絞り込み) リンクに** (PM table / Epics カード / epic タブ head の 3 箇所)。
    リンク先: `https://github.com/<repo>/issues?q=is:issue+label:<epic_label>`。
    `epic_label` 無しの spec はリンクにしない (text のまま)
  - **Recent patrols を 7 列表形式に**: `日時 / 観測 / IDLE / RUNNING / WAITING / 指示 / メモ`。
    `dashboard-generate.py` 側で patrols.md の summary を `/` split + 正規表現で分解 (`観測 N` 等)。
    どの pattern にも match しない token はメモ列に集約。全パターン unmatch なら全文をメモ列に (Fact 主義: 勝手に埋めない)
  - **Retro index の file 名を隣接 md への相対リンクに**: `<a href="./retro-YYYY-MM-DD.md">` で単純にブラウザで開ける
- Spec schema は v1.2 に (v1.1 `kpi_sheet_tab` は不変、`epic_label` を任意追加のみ)
- 判断木・芯には変更なし

## [0.15.7] - 2026-07-09

- **Spec schema v1.1: `kpi_sheet_tab` を必須追加** (issue #23):
  チーム共通の数値管理 (PJCI シート、`1WyEk-SLza9RjXfoYmoxn6zNwSKfeu4As7QIlUz0zj4U`) に epic (spec) を必ず
  紐付ける。volante 側は数値を持たず `{gid, name}` の参照のみ保持 (Fact 主義: 数値の正本は Sheet 側 1 箇所)
  - `templates/spec-template.json`: `required` に `kpi_sheet_tab` を追加 (`{gid, name}` 必須の nested object、
    `additionalProperties: false` 維持)。`goal` + `acceptance_criteria` の 2 要素は不変
  - `templates/spec-template.example.json` に例を追加
  - dashboard: PM table (KPI 列) / Epics 詳細カード / epic タブ head の 3 箇所に「KPI: <タブ名>」リンクを追加。
    `gid` から `https://docs.google.com/spreadsheets/d/<sheet-id>/edit?gid=<gid>#gid=<gid>` を生成。
    `kpi_sheet_tab` 未設定の Spec は「KPI: 未紐付け」とグレー表示 (dashboard generate 自体は落とさない)
  - **既存 Spec 2 件 (`pitto-kaizen.json` / `pitto-payroll.json`) は未移行、konuma 確認待ち**:
    PJCI シートのタブ一覧・各 epic との対応が volante 側から enumerate できないため (issue #23 Unknown)、
    勝手に gid を推測して埋めない。konuma からタブ一覧 (or 対応表) を貰い次第、後続 issue で移行する
  - v0.16.0 revert (0.15.3) の教訓どおり、primary key (session/repo 識別方式) には手を入れない最小差分
- 判断木・芯・Spec schema の `goal`/`acceptance_criteria` 部分は不変

## [0.15.6] - 2026-07-09

- **dashboard: epic 別タブに開発者ビューを実装** (issue #21、親 #17):
  各 epic タブ (Spec ごと 1 タブ) に以下を配置。全体タブ内のセクションは維持:
  1. **Head**: Spec name + repo link (GitHub 遷移) + 優先度 + status badge + Goal 全文
  2. **acceptance_criteria** (デフォルト展開、epic tab 内では折りたたみなし)
  3. **開いてる PR**: `gh pr list --json number,title,mergeStateStatus,statusCheckRollup,reviewDecision,url,isDraft`
     を generate 時に取得。CI 状態は `statusCheckRollup` から fail/pending/pass の集計に圧縮
  4. **開いてる issue**: `gh issue list --json number,title,url,labels,updatedAt`。label は chip 表示、
     updated timestamp 併記
  5. **直近 decisions (this epic)**: `data.decisions` を `target_session.includes(basename)` で filter
  6. **監督 AI 判定履歴**: 上記に `branch.includes("監督 AI")` を追加 filter
- **per-repo キャッシュ**: 同一 repo に複数 Spec (現状 pitto-kaizen / pitto-payroll) がある場合、
  gh query は repo 単位で 1 度のみ実行し結果を各 Spec に配布 (無駄クエリ削減)
- **`renderEvent()` 共通化**: 全体タブと epic タブの decisions timeline で同じ描画関数を使用 (DRY)
- **gh query 失敗時のフォールバック**: 各セクションで `data.error` を表示、generate 自体は成功する
  (SKILL.md 3. ground_truth の「実測不可」明記に準拠)
- **既知の制限** (issue #21 コメント記載予定):
  - 同一 repo 複数 Spec で PR / issue が同じリスト表示 (per-epic filter 未実装、Spec に epic id 拡張要)
  - kitty @ get-text の STATUS snapshot 未統合 (別 issue 想定)
  - CI 詳細 / branch 情報 / retro 抜粋 は未実装 (別 issue 想定)
- 判断木・芯・Spec schema すべて不変

## [0.15.5] - 2026-07-09

- **dashboard: tab 構造化 + 全体タブ (PM 視点 Epics テーブル)** (issue #20、親 #17):
  - 全体を tab に分割 (**全体** + **epic 別 × Spec 数**)。1 タブ目「全体」に既存 4 section (Epics 詳細カード /
    Recent decisions / Recent patrols / Retro index) を格納し、新規に **PM 視点 Epics テーブル**を先頭に配置
  - Epic 別タブは placeholder 表示 (「#21 で epic 別の開発者ビューを実装予定」)
  - tab 制御は vanilla JS (`document.querySelectorAll` + `classList.toggle`)、外部 library 依存なし
    (CLAUDE.md 設計原則遵守)
- **PM 視点テーブルの列** (8 列):
  1. Epic (Spec basename)
  2. repo (goals.md fuzzy resolve)
  3. 優先度 (goals.md `優先度` 列)
  4. status (色分け badge: `done` / `on-track` / `at-risk` / `stalled`)
  5. 進捗 (Issue #19 の open issue 数)
  6. 直近更新 (該当 Spec に紐づく decisions の最新 timestamp)
  7. ブロッカー数 (`konuma_review: 未` or NG の件数、警告色)
  8. 承認待ち数 (枝 1/3 かつ `konuma_review` が OK でない件数、警告色)
- **status 判定 rule** (初期案、konuma 実運用フィードバックで調整前提):
  - **done**: `spec.goal` に「達成」「完了」「done」いずれか含む
  - **stalled**: 該当 Spec に紐づく decisions が 0 件 or 直近更新から 24h 超経過
  - **at-risk**: 24h 以内の decisions あり かつ ブロッカー数 > 0 or 承認待ち数 > 0
  - **on-track**: 上記いずれでもない
- **decisions ↔ Spec の紐付け**: `decisions.jsonl` の `target_session` に Spec basename が含まれるか
  (`in` 判定)。v0.14.0 の JSONL が populate されるまではデータなしなので、多くの Spec は `stalled` に落ちる
  (仕様、実運用で JSONL 併記が回れば解消)
- **load_recent_decisions のリファクタ**: `limit=0` で全件返す挙動を活かし、`all_decisions` を 1 度 load して
  PM metrics 計算と表示用 (`--decisions-limit` 件) の両方に使い回す
- 判断木・芯・Spec schema すべて不変

## [0.15.4] - 2026-07-09

- **dashboard: Sessions grid を Epics カード化 + goal + 進捗明記** (issue #19、親 #17):
  - section 見出し `Sessions (epic 主体、Spec v1)` → **`Epics`**
  - 各カードに **repo ラベル** (goals.md からの fuzzy resolve) と **進捗** (open issue 数、gh api 経由) を追加
  - **acceptance_criteria を `<details>` で折りたたみ**、デフォルト閉じ、summary クリックで展開
- **goals.md 由来のデータ供給**:
  - `parse_goals_md()`: v0.15.3 の 6 列 (`repo | 正本 | session | ゴール | 優先度 | 登録日`) を dict list に
  - `resolve_repo_for_spec()`: Spec basename の prefix (最初の `-` まで) を goals.md の `owner/name` と
    fuzzy match。同一 repo 複数行は set で重複排除、単一 repo のときのみ返す (曖昧マッチは空返却)
  - `fetch_open_issue_count()`: `gh api search/issues?q=repo:owner/name+is:issue+is:open` の `total_count`。
    generate 時に 1 度だけ呼び HTML に埋め込み (CLAUDE.md 設計原則、runtime fetch なし)
  - `--no-gh` フラグでスキップ可能 (offline / rate limit 時)、エラー時は `(進捗未定義)` + tooltip でエラー表示
- **進捗表示のスタイル**:
  - 通常: mono の open 件数
  - 全 issue closed (0 open): 緑背景の `全 issue closed (0 open)`
  - 未定義: グレー `(進捗未定義)` + hover tooltip で原因 (no repo resolved / gh failed / gh skipped)
- **将来的な per-epic filter は別 issue** (#19 コメントで検討)。現状は repo 単位の open 件数のため、同一 repo の
  複数 Spec は同じ数字を表示する (例: pitto-kaizen / pitto-payroll は同じ open 件数)
- 判断木・芯・Spec schema すべて不変

## [0.15.3] - 2026-07-09

- **v0.16.0 の revert** (commit 111dc8e、konuma FB「過剰実装、意図と乖離」):
  Spec schema v2 化・attachments 揮発層・SKILL.md 大改修・dashboard 刷新の BREAKING を全 revert し、
  konuma の実意「w34 表記を epic 起点にしたい」の最小変更のみを再実装
- **`journal/goals.md` の列順入替** (repo × 正本 が主キー):
  - 現: `| session (直近 window) | repo | 正本 | ゴール 1 行 | 優先度 | 登録日 |`
  - 新: `| repo | 正本 | session (役割名) | ゴール 1 行 | 優先度 | 登録日 |`
  - session 列から `(w24)` `(w34)` 等 window id suffix を除去 (役割名だけ残す)
  - 冒頭説明を「repo × 正本 主キー、window id は goals.md に載せず決定/巡回ログのみで使う」に更新
- **Spec ファイル rename** (揮発 window id → 安定 role 名):
  - 具体 rename 2 件は journal/ (runtime state) 側で実施済み
  - Spec schema v1 (`goal` + `acceptance_criteria` の 2 要素) 自体は不変
- **skill 側 (`skills/volante/`) の完全 genericize** (konuma FB「pitto/payroll などこの skill が知る必要のないものが散見される」):
  - SKILL.md 4. 監督 AI subagent 節: 「試験運用は pitto 対象のみ (w24 / w59)」→
    「試験運用対象は konuma が別途指定する」
  - SKILL.md の起源注釈から具体 window id / project 名 (w24/w34/w59/pitto) を除去し
    日付 + 抽象説明に置換 (why は保持):
    - 枝 1 `--admin` 起源: 「2026-07-08 22:34 w59 PR #284 --admin merge」→
      「2026-07-08 の PR merge 時に branch protection bypass が発生した実事例」
    - 枝 4 次アクション代答起源: 「2026-07-08 21:04 w24 触らない判断... 22:14 w59 #137 代答」→
      「2026-07-08 の触らない判断で 30 分停滞した実事例の再発防止 / 同日、konuma 宛て質問への次アクション
      代答で 30 分以内に全完了した実運用実証」
    - 枝 1 2h 停滞起源: 「2026-07-08 w24 の 2h 停滞」→「2026-07-08 の 2h 停滞事例」
    - 7.2 回収漏れ起源: 「2026-07-07 w34 の回収漏れ未遂」→「2026-07-07 の回収漏れ未遂事例」
  - `scripts/oversight-subagent.md`: frontmatter description と本文の pitto 参照を除去
  - `templates/spec-template.example.json`: payroll 例 → generic placeholder
  - `templates/decision-event.example.json`: pitto/payroll/w59 → `<window-id>` `<owner/repo>` placeholder
  - `templates/decision-event.schema.json`: description 中の w59 例 → `<window-id>` placeholder
- **dashboard 見出しの最小調整**: `Sessions (Spec v1)` → `Sessions (epic 主体、Spec v1)`
  (renaming で自然に spec basename が role 名 = pitto-kaizen / pitto-payroll になり、window id が消える)
- **意図的にやっていないこと**:
  - Spec schema v2 化 (v1 = session-keyed のまま)
  - attachments-rebuild.py / attachments.json (revert 済み)
  - SKILL.md の芯・判断木・7.1 準備・監督 AI 入力 contract の大改修
  - 過去 decisions/patrols の w24/w34/w59/w61/w69 表記の遡及書換え
- 判断木の枝 1〜5 の意味・優先順位・番号は不変、芯 1〜9 も不変

## [0.15.2] - 2026-07-09

- **dashboard: Recent patrols を表形式に変更** (issue #17 継続、konuma FB「読みづらい」):
  - `load_recent_patrols` を dict list (`{"datetime", "summary"}`) 返却に変更、`|` 区切りを parse
  - 表示を `<table>` (日時 / サマリ 2 列) に切替。日時列は mono + `white-space: nowrap`、
    サマリ列は 12.5px / line-height 1.5 で長文でも読みやすく
  - 新しい行が上に来るよう `slice().reverse()` で最新順に描画

## [0.15.1] - 2026-07-09

- **HTML + JSON 型ローカル UI の MVP 第 1 段** (issue #17 v1.0 epic の「着手」段階、konuma /goal 承認済み)。
  epic は継続 open で、以下は v0 スタート:
  - `skills/volante/scripts/dashboard-generate.py`: journal/ を読み `journal/dashboard.html` を生成する
    Python スクリプト。読み込み対象は `journal/specs/*.json` (v0.13.0-b)、
    `journal/decisions-<current-month>.jsonl` (v0.14.0)、`journal/patrols.md`、`journal/retro-*.md`
  - **出力は完全自己完結**: 単一 HTML ファイル + `<script type="application/json">` 埋め込みデータ。
    サーバー不要、`open journal/dashboard.html` だけで動く (CLAUDE.md 設計原則 / SKILL.md 芯 9 遵守)
  - **表示**: Sessions grid (Spec の goal + acceptance_criteria)、Recent decisions timeline (直近 20 件、
    枝 1 と「監督 AI 判定」を色分け)、Recent patrols (直近 10 行)、Retro index
  - light / dark mode 対応 (`prefers-color-scheme`)。tracer の `dashboard-template.html` (14KB) を
    参考実装として意匠を圧縮 (`</` エスケープでスクリプト境界も安全)
  - **意図的に含めていない** (次イテレーション以降): 監督 AI 判定の詳細展開、retro 本文表示、対話的
    フィルタ、goal 更新履歴グラフ。dashboard.html は毎回 regenerate 前提で、差分管理はしない

## [0.15.0] - 2026-07-09

- **監督 AI subagent v1 (試験運用、pitto 対象のみ)** (issue #16、親 #10 の v0.15.0):
  - `scripts/oversight-subagent.md` を新設。frontmatter (`name: volante-oversight`, `model: opus`) +
    role / input contract / output contract / 禁止事項 / 判定手順。**opus + effort max、フレッシュ文脈**
    (global CLAUDE.md「effort max」節に準拠、親セッション側で `/effort max` に上げて起動する運用)
  - **判定範囲は 2 機能のみ** (質問応答代行は v0.16.0 以降):
    1. **Verifier**: STATUS ↔ Spec の `acceptance_criteria` 乖離チェック (乖離チェック 系統 2 の独立判定)
    2. **エスカレーション判定**: main の枝 2/4/5 自律判断が枝 1 相当でないかの二次チェック
  - **入力**: STATUS + Spec + decisions JSONL 直近 20 件 + tracer goal file (read-only、対象 repo 依存)
  - **出力**: JSON 1 件 (verifier / escalation / confidence / notes)。main が decisions JSONL に
    `branch: "監督 AI 判定"` として 1 event 追加
  - **禁止事項** (subagent 側で明示): kitty send-text、ファイル書き換え、Agent / WebSearch / WebFetch、
    機密の記載、Hypothesis の Fact 化。順守できないときは `unknown` / `unclear` で返す
  - **試験運用中は main が最終判断者**。食い違ったら decisions に記録し次サイクルの retro (7.6) で扱う
- SKILL.md 4. checklist の末尾に「監督 AI subagent」節を追加 (判断木 枝 1-5 の意味・優先順位・番号は不変)

## [0.14.0] - 2026-07-09

- **decisions ログ JSONL 併記化 + 抽出スクリプト** (issue #15、親 #10 の v0.14.0):
  - `templates/decision-event.schema.json` (v1、9 フィールド全 required、`additionalProperties: false`、
    JSON Schema draft 2020-12) と `templates/decision-event.example.json` を新設
  - `scripts/decisions-extract.py` (`--last N` で直近 N 件を JSON / JSONL 形式で標準出力へ、
    デフォルトは `journal/decisions-<current-month>.jsonl` の直近 20 件、malformed 行は warning で通過)
  - SKILL.md 7.5 に「併記: JSONL 追記」を追記。Markdown は human-readable、JSONL は
    subagent 入力用 (v0.15.0+)。既存の Markdown 過去分は遡及変換しない (新規エントリのみ併記)
- **背景 Fact** (issue #18 で計測、2026-07-09): decisions-2026-07.md は 154.2 KB / 1531 lines / 3 日で、
  平均 51 KB/日。月末見込み ~1.3 MB。opus context 上限内には収まるが grep / 目視レビューが重くなるため
  JSONL 併記化のタイミング妥当と判定

## [0.13.0] - 2026-07-09

- **HOTL Platform 昇華ロードマップの第 1 段** (issue #10、konuma 承認 2026-07-09 /goal「一通り完了するまで
  merge 含めて実装を進めて」)。差配の起点を goals.md から Session Spec (JSON) に段階移行する:
  1. **Spec schema v1 導入** (#12): `skills/volante/templates/spec-template.json` (JSON Schema draft
     2020-12、`additionalProperties: false`)。要素は `goal` (string) と `acceptance_criteria`
     (array of string、`minItems: 1`) のみ。制約 / 非目標 / 前提 / 依存 / エスカレーションは v0.14.0
     以降で段階拡張
  2. **pitto 先行移行** (#13): `journal/specs/pitto-w24.json` / `pitto-w59.json` を作成し schema
     v1 で validate 済み
  3. **SKILL.md 判断木更新** (#14):
     - **芯 9 追記** (設計原則): 「DB / サーバーを持たない。永続化は git 管理下ファイルで完結、UI は
       HTML + JSON 読み込み型のみ」を SaaS 化しない原則として明示。CLAUDE.md「設計原則」節と一致
     - **正本 3 層 → 4 層に拡張** (2. canonical_model): Session Spec (差配起点) と goals.md index
       (index 降格) を分離。Spec 未整備 session は goals.md「ゴール 1 行」列でフォールバック
     - **差配とゴール紐付け節** (4. checklist): 起点を Spec の `goal` / `acceptance_criteria` に切替。
       未登録処理は goals.md 未登録に加え「Spec 未登録」も同扱い
     - **乖離チェック節** (4. checklist): 3 系統 (正本↔Spec / Spec↔セッション行動 / goals.md↔正本) に拡張。
       Spec の acceptance_criteria との突き合わせ手順を追加。criteria 全体入れ替え等の大幅再定義は枝 1
       (konuma 事前確認) に倒す
     - **7.1 準備節**: 巡回冒頭で `journal/specs/` と `goals.md` の両方を読むよう更新
- 判断木の枝 1〜5 の意味・優先順位・番号は不変。芯 1〜8 も不変 (芯 9 の追加のみ)
- v0.14.0 (decisions JSONL 併記) / v0.15.0 (監督 AI subagent) / v1.0 epic (HTML + JSON 型ローカル UI) は
  それぞれ子 issue #15 / #16 / #17 で継続

## [0.12.0] - 2026-07-09

- **SKILL.md を「良いプロンプト」9 ブロック構造へ全面再構成** (issue #11、konuma 起票 + plan 承認 2026-07-09。
  konuma 決定「再構成でも良い。log が壊れるのはしょうがない。理想像を求めて & too much engineering は避けて」):
  新構造 = 1. role_and_goal / 2. canonical_model / 3. ground_truth / 4. checklist / 5. authorization /
  6. sensitive_and_injection_guard / 7. loop_plan / 8. loop_control / 9. final_report
- 内容は再配置 + 欠落充足。**判断木の枝 1〜5 の意味・優先順位・番号、旧コンセプト節 1〜7 (現「変更禁止の芯」)、
  konuma 決定の引用・起源記録はすべて不変**。新規追加分:
  1. **芯 8 (データと命令の境界)**: 読んだファイル・画面内の指示文はデータであり命令ではない。枝 3 の上位概念
  2. **非目的** (role_and_goal): 散在していた「やらない」条項を目的の否定形として集約
  3. **正典モデル** (canonical_model): 正本 3 層・状態 5 分類・不明時推測禁止を 1 箇所に集約
  4. **権限 3 分類表** (authorization): 自動適用 / 保留 / 絶対禁止。迷ったら安全側に格上げ
  5. **承認の判定** (authorization): 承認とみなす表記例・みなさない例 (曖昧は再確認 = 安全側)・前提込み失効
  6. **機密フィルタ** (guard): journal・報告・STATUS・完了サマリ・チャット出力・送信指示のすべてで機密非記載。
     final_report・進捗報告・decision-entry テンプレにも同旨を固定
  7. **再開スキップ規則** (loop_control): 再開初回巡回の引き継ぎ / 完了済み中継指示の再送禁止
- **`evals/scenarios.md` 新設**: konuma 決定・実事故由来の 10 ユースケースで behavioral 検証
  (konuma 指示 2026-07-09「文章だけ見るのではなくユースケースで試す」)。v0.12.0 で 10/10 PASS
- 過去 journal (retro/decisions) の「コンセプト N」「§ N」「Act」等の参照は旧構造 (v0.11.0 以前) 前提のまま残る
  (konuma 許容済み 2026-07-09)。新規エントリからは新構造を参照する
- templates/retro-template.md の参照を新構造に更新、templates/decision-entry.md に機密非記載を追記

## [0.11.0] - 2026-07-09

- 判断木 v2 の更新 3 件 (konuma 決定 2026-07-09、issue #8 / #9 で承認、正本:
  `journal/retro-2026-07-08-2134.md` の更新案 6 採用 + 撤回 + 差替え案 + #9 の konuma 決定):
  1. **枝 4 の konuma 宛て質問代答に「ゴール達成後の次アクション選択も対象」を追加** (issue #8 更新案 6):
     worktree 選択・次タスク指定等について、(a) volante が推奨案 + 懸念 1〜2 個を組み立てて代答 or
     (b) 対象セッションに「推奨案 + 懸念を送るので採否と根拠を返せ」形式で差配、のどちらかで進める。
     ただし `goals.md` 未登録なら代答せず goal 設定要求手順 (下記 3) に従う。
     起源: 2026-07-08 21:04 w24 触らない判断 (30 分停滞) の再発防止 / 22:14 w59 #137 代答 → 22:44 全完了で実証
  2. **枝 1 に `gh pr merge --admin` 判定基準を追記** (konuma 決定 2026-07-09「--admin は NG、
     既存 CI を通したい」、issue #9): branch protection bypass を要する状況は原則 NG。CI green を待たずに
     merge しない。人間レビュー要否は repo 依存 (`.github/CODEOWNERS` / `.github/branch-protection` /
     repo README 等)、volante は判定しない。起源: 2026-07-08 22:34 w59 PR #284 --admin merge
  3. **差配とゴール紐付け節の「goals.md 未登録」処理を強化** (konuma 決定 2026-07-09「そもそも goal 設定が
     ない状態がおかしい」、issue #8 更新案 7 撤回 + 差替え案): volante 側で仮置きしない。`ゴール未登録` +
     `確認待ち` 欄両方に「goal 設定要求」を明記し、konuma が goal 設定するまで枝 4 の推奨案代答・次アクション
     代答は行わない。緊急 hotfix 等の枝 1/2/3 は従来どおり働かせる
- 判断木の枝の意味・優先順位・コンセプト節は変更なし
- issue #8 / #9 に konuma 決定 2026-07-09 を反映済み。retro-2026-07-08-2134.md の承認状態を更新予定

## [0.10.0] - 2026-07-08

- 判断木 v2 のさらなる更新 (konuma 承認 2026-07-08「更新 ok」。retro 2 本を統合反映。
  正本: `journal/retro-2026-07-08-1824.md` + `journal/retro-2026-07-08-1954.md`):
  1. **枝 1 の基準に PR merge/approve 除外を明示** (konuma 決定 2026-07-08 18:14「merge/approve も
     あなたが判断して」): PR merge / PR approve は原則枝 4 側で、追加的なら自律実行・影響大 (URL 変更・
     destructive migration・force push 等) なら枝 1 で人間確認。実行前に CI 状態 / mergeStateStatus /
     reviewDecision を Fact 確認、判断根拠を毎回 decisions ログに明記。コンセプト節 3 と枝 1 本文の両方に反映
  2. **枝 5 に「送信直前 identifier 再確認」を追記** (retro-2026-07-08-1824 更新案 1 +
     retro-2026-07-08-1954 更新案 5): 中継指示の identifier (issue/PR 番号・label・state 等) は送信直前に
     gh 等で 1 段階再確認。並行進行中の状態急変を捕捉。検証できない場合は「中継元セッションの報告により
     (未検証)」と明示。起源: 2026-07-08 17:56 の PR #239 誤中継 / 19:04 の Forge #259 状態誤認
  3. **巡回義務の発火条件に副条件 (見送り基準) を追加** (retro-2026-07-08-1824 更新案 3): 発火条件を
     満たしても、konuma 判断保留 + context 依存の場合は保留処置まで見送る。ただし 2 巡回連続で発火条件維持
     なら副条件を無視 (無期限見送り回避のフェイルセーフ)。起源: 2026-07-08 17:56 の w61 見送り判断の揺れ
  4. **送信手順 (kitty) に対象状態別分岐を追加** (retro-2026-07-08-1954 更新案 4):
     WAITING (AskUserQuestion モード) では Esc が「User declined」扱いになる問題への対策。IDLE / WAITING /
     RUNNING / STUCK の 4 状態それぞれの送信手順を明記。起源: 2026-07-08 18:49 の User declined 失敗
  5. **Check セクションに `konuma レビュー` 欄の self-review 運用を明記** (konuma 決定 2026-07-08 18:44
     「decisions ログを自己レビュー, ただし外部への連絡類は一切 NG」): volante 自身が OK/NG + 根拠で
     埋める (社内・内部の判断のみ)。外部連絡類 (Slack/メール/社外向け PR・issue コメント、外部 API 呼び出し等)
     を含む判断は self-review 対象外で「未」で残す。NG/OK 基準と記入フォーマットも明記
  6. **Act の抽出対象を self-review 運用に合わせて更新**: 「self-review で NG が付いたエントリ」
     「konuma がチャットで NG 指摘した内容」を対象に含める。konuma チャット指摘は次回巡回時に該当エントリの
     `konuma レビュー` 欄に転記して self-review 結果を上書き
- 判断木の枝の意味・優先順位 (コンセプト節 1-2, 4-7) は変更なし。コンセプト節 3 は枝 1 の PR merge/approve
  除外に同期して 1 文追記
- retro 2 本の「konuma 承認」節を「承認 (2026-07-08)」に更新済み

## [0.9.0] - 2026-07-08

- 判断木 v2 (konuma 決定 2026-07-08 14:52、起点: konuma FB「なぜ俺の対応待ちとしたのか。改善したい」
  正本: `journal/retro-2026-07-08-1450.md`):
  1. 枝 1 の基準を「不可逆 or 外部可視」から「外部連絡 or 影響大の本番変更 (URL 変更・削除・既存設定の変更等)」に
     再定義。追加的で既存動作への影響が限定的な変更 (新規リソース・rule 追加、drift 解消方向の修正等) は
     本番反映でも自律で進めて事後レビュー。迷ったら人間確認に倒す
  2. 枝 4 に「konuma 宛て質問への代答」を追加 — 推奨案明示 + 内部・可逆なら推奨案で代答可 (報告に選択内容を明記)。
     外部連絡・影響大に触れる質問は枝 1 (w24 の 2h 停滞が起源)
  3. 枝 5 に「人間承認ゲート手前の準備作業 (plan 記述・PR 作成・diff 要約) はゲートを越えない境界付きで自律差配可」を明文化
- コンセプト節 3 を枝 1 の新基準に同期

## [0.8.0] - 2026-07-08

- 昨夜ループ (2026-07-07 21:41〜2026-07-08 01:17) の retro に基づく手順追記 3 件
  (正本: `journal/retro-2026-07-08.md`。判断木の枝 1〜5 の意味・優先順位は変更なし。
  v0.3.0 前例に従い判断木外の追記として反映、konuma 事後レビュー対象):
  1. 「3. Check」: journal に書く時刻 (patrols.md / decisions) は `date` コマンドの実測値を使う。
     経過からの推定で書かない (時刻 1〜2 時間誤記 → 完了サマリ集計誤りの再発防止)
  2. 「6. ループ自動停止 > 完了サマリ」: 成果集計のループ開始時刻は patrols.md 記載時刻と
     該当 commit timestamp を突合し、食い違う場合は commit timestamp を正とする
  3. 「1. Plan」: IDLE と分類したセッションは送信済み指示の完了条件が未報告のまま残っていないか
     decisions の直近エントリで確認する。未回収があれば「変化なし」(自動停止判定) とは数えず、
     判断木に入る前に確認・報告のみの指示で回収する
- retro 所見 (変更不要の確認): 枝 1 の承認失効→再承認型が 2 回機能 (RDS 縮小地雷を防止)、
  ループ自動停止 2 回正常発火、完了サマリ初適用が時刻誤記の検出に寄与

## [0.7.0] - 2026-07-08

- ループ停止時の完了サマリを必須化 (#7): 「6. ループ自動停止」の停止手順 5 (最終報告) を拡張し、
  新設「完了サマリ (停止時必須)」節を追加:
  1. 成果集計 (Fact、実測): ループ開始時刻以降の repo 別 issue close 数 / PR merge 数 /
     default branch commit 数を表で出す。対象は `journal/goals.md` 掲載の全 repo + volante 自身。
     ループ開始時刻は `journal/patrols.md` の直近の「ループ再開/開始」行から取る。実測は
     `gh api search/issues` (`is:issue`/`is:pr` + `closed:>=`/`merged:>=`) と
     `gh api repos/<repo>/commits --since` で行い、失敗時は 0 件と決め付けず「実測不可」と明記する
  2. repo 別サマリ: repo ごとに「今回やったこと (1〜3 行)」「次回以降やること (セッション作業 と
     konuma 作業を区別して列挙)」。素材は当該期間の patrols.md/decisions と各セッションの最新 STATUS
  3. 自動停止に限らず、konuma 指示による手動ループ停止でも同じ完了サマリを出す (自動停止専用にしない)
  - 完了サマリは 5. 報告 の既存フォーマットを置き換えず、その後ろに追加する
  - 判断木の枝・巡回義務 (1〜5) の判定基準・優先順位は変更なし
- konuma FB (2026-07-08, #7): 「この数 (issue close / commit / PR) を作業完了時に報告するようにして欲しい。
  あと repo の次回以降やることと今回やったことの要約があると良い」

## [0.6.0] - 2026-07-07

- retro 更新案 1〜4 の SKILL.md 反映 (#6, konuma 承認 2026-07-07「ok.」。正本: `journal/retro-2026-07-07.md` /
  `journal/retro-2026-07-07-2.md`):
  1. 枝共通セルフチェックに追記: 指示文中の前提は「画面で確認した事実」と「推定」を区別して書く。
     推定を前提にする場合は「違ったら報告して中断」を境界に含める
  2. 枝 1 に追記: konuma 承認は提示した前提 (diff 内容・影響範囲) 込み。実行過程で前提が変わったら
     承認は失効し、停止 → 再確認する
  3. 枝 2 を「既存 autonomy がある (tracer に限らない)」に拡張: tracer goal file に限らず、対象セッションが
     konuma から直接受けている権限委譲 (memory・issue 記載等) も尊重対象。volante はそれを狭めも広げもしない。
     委譲範囲内の行動は事後掲載、範囲が不明瞭なら枝 1 に倒す
  4. 送信手順に追記: 対象セッションに長時間コマンドを実行させる指示では background 化 + 進捗ログ出力を
     推奨する 1 文を含める (STUCK 誤判定の低減)
  - あわせて retro 2 ファイルの「konuma 承認」節を 承認 (2026-07-07) 済みに更新し、反映先を記録
  - 判断木の枝の優先順位・コンセプト項目 1〜7 の芯は変更なし

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
