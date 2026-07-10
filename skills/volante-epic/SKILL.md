---
name: volante-epic
description: >
  Add, remove, and edit volante epic Specs (journal/specs/<slug>.json + the matching
  journal/goals.md row) through one conversational turn instead of hand-editing two files.

  volante の epic (Spec) を対話 1 回で追加・削除・編集する skill。`journal/specs/<slug>.json` と
  `journal/goals.md` の 1 行を同時に作成・更新・削除する。「epic 追加して」「epic 消して」
  「spec 編集して」「/volante-epic」などと言われたら使う。
---

# volante-epic — epic (Spec) の対話的 CRUD

打ち方は **`/volante-epic add|remove|edit|list`**。`journal/specs/*.json` と `journal/goals.md` の
手編集 2 段階を対話 1 回にまとめる (issue #24)。実体は `skills/volante-epic/scripts/epic_tool.py`
(このスキルの `--repo-root` は `$VOLANTE_REPO` に固定する。`skills/volante/SKILL.md` 7.1 と同じ find 手順:
`find ~/git -maxdepth 3 -type d -name volante -not -path '*/.*' 2>/dev/null | head -1`)。

スクリプトはファイル書き込みのみ行う。**git add/commit/push は毎回このスキル側の手順で行う**
(`skills/volante/scripts/dashboard-generate.py` と同じ分離)。

## 前提知識 (このスキルが触る 2 ファイルの関係)

- `journal/specs/<slug>.json`: Spec 本体。schema は `skills/volante/templates/spec-template.json`
  (現行 v1.2: `goal` / `acceptance_criteria` / `kpi_sheet_tab` が必須、`epic_label` が任意)
- `journal/goals.md`: session ↔ repo ↔ 正本 URL の index。**`session (役割名)` セルにはこのスキルが
  常に slug をそのまま書く** — これにより remove/edit がどの行を触ればよいか一意に決まる
  (goals.md 本文コメントにある「repo × 正本 が主キー」という原則とは別に、このスキル発の行に限り
  session セルを機械可読キーとして使う)。既存の手書き行 (`ma_navi org kaizen loop 立ち上げ` 等) は
  slug 形式ではないため、このスキルの remove/edit では**触れない** (対象外。手動編集のまま)
- `優先度` 列は konuma 専有 (`CLAUDE.md`・`skills/volante/SKILL.md` 芯 7)。add は `未指定` を入れ、
  edit/remove はこの列を変更しない

## add

1. 対話で以下を聞く (未回答があれば聞き返す。仮置きしない):
   - `slug`: kebab-case (例: `ma-navi-repo-kaizen`)。`^[a-z0-9]+(-[a-z0-9]+)*$` を満たすこと
   - `repo`: 対象 repo (`owner/name`) か `home` 等のローカルラベル
   - `goal`: 1 文
   - `acceptance_criteria`: 1 件以上、複数可
   - `kpi_sheet_tab`: PJCI シート (`1WyEk-SLza9RjXfoYmoxn6zNwSKfeu4As7QIlUz0zj4U`) の `gid` と `name`。
     **未回答なら add を拒否する** (issue #23 依存。konuma がタブを未作成ならまずそちらを確認してもらう)
   - `正本` の扱い: 次のいずれか (v0.17.0 で追加、issue TBD):
     - **既存の issue/PR/goal file がある** → `--source <URL/path>` を渡す。GitHub URL の場合は
       スクリプトが対象 issue に `epic` label を自動付与する (label が repo に無ければ作成)。
       非 GitHub の path (`<repo>/.claude/goals/*.md` 等) の場合は label 付与はスキップ
     - **無い / 新規に立てたい** → `--create-issue` を渡す。スクリプトが `gh issue create` で
       `title=[epic] <goal>` / `body=Goal + Acceptance Criteria` / `label=epic` の epic issue を対象
       repo に起票し、その URL を正本として goals.md に書く。**先に必ず `--dry-run` で title/body を
       konuma に見せて OK を取ってから本実行**する (下記 2 の手順参照)
   - `epic_label` (任意): 対象 repo 側の epic label (issue #22 の label 進捗集計用。上述の自動付与
     とは別軸の任意フィールド)
   - `優先度` は聞かない (konuma 専有。goals.md には常に `未指定` を書く)
2. 実行 (source 分岐):
   - **既存 URL がある場合**:
     ```bash
     python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" add \
       --slug <slug> --repo <repo> --goal "<goal>" \
       --criteria "<criteria 1>" --criteria "<criteria 2>" \
       --kpi-gid <gid> --kpi-name "<name>" --source "<正本 URL>" \
       [--epic-label "<epic_label>"]
     ```
   - **新規 epic issue を起票する場合** (2 段階: dry-run → 本実行):
     ```bash
     # 1. dry-run で title/body を konuma に提示
     python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" add \
       --slug <slug> --repo <repo> --goal "<goal>" \
       --criteria "<criteria 1>" --criteria "<criteria 2>" \
       --kpi-gid <gid> --kpi-name "<name>" --create-issue --dry-run

     # 2. konuma の OK を得たら --dry-run を外して本実行
     python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" add \
       --slug <slug> --repo <repo> --goal "<goal>" \
       --criteria "<criteria 1>" --criteria "<criteria 2>" \
       --kpi-gid <gid> --kpi-name "<name>" --create-issue \
       [--epic-label "<epic_label>"]
     ```
   - `--source` と `--create-issue` は排他 (両方指定 or 両方省略はエラー)
   - schema 違反 (kpi_sheet_tab 欠落等) やスラグ重複はスクリプトが exit 1 + エラー文で返す。エラーが出たら
     対話に戻して該当項目を聞き直す (推測で埋めない)
   - `gh` の失敗 (権限・network 等) はスクリプトが exit 1 + gh の stderr をそのまま返す。konuma に
     報告して手動対応 (=gh の設定確認 or 手動起票 → `--source` 経路に切り替え) してもらう
3. 成功したら commit + push:
   ```bash
   git -C "$VOLANTE_REPO" add journal/specs/<slug>.json journal/goals.md
   git -C "$VOLANTE_REPO" commit -m "epic: add <slug>"
   git -C "$VOLANTE_REPO" push
   ```
4. 報告: 作成した spec の内容 + goals.md 行 + commit sha。`--create-issue` を使った場合は起票された
   issue URL も明記する。`--source` 経路で label 付与が発生した場合はその結果 (`added`/`already`)
   も添える

## remove

1. `<slug>` を指定させる。`epic_tool.py list` で現存する slug を確認してよい
2. **実行前に 1 度 konuma に確認する** (issue #24 実装方針: remove は破壊的操作扱い)。
   確認内容: 対象 spec の goal + `_archive/` への移動である旨 (削除ではなく git 管理下に残ることを明記)
3. 承認後に実行:
   ```bash
   python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" remove <slug>
   ```
   `journal/specs/<slug>.json` → `journal/specs/_archive/<slug>.json` に移動し、goals.md の該当行
   (session セル == slug) を削除する。**goals.md 側に手書きの旧形式行しかない場合は削除されず warning
   が出る** — その場合は konuma に手動編集を依頼する (推測で別行を消さない)
4. commit + push (3-way: 元 spec 削除 + archive 追加 + goals.md 更新):
   ```bash
   git -C "$VOLANTE_REPO" add journal/specs/<slug>.json journal/specs/_archive/<slug>.json journal/goals.md
   git -C "$VOLANTE_REPO" commit -m "epic: remove <slug> (archived)"
   git -C "$VOLANTE_REPO" push
   ```

## edit

1. `<slug>` + 変更したいフィールドを聞く (goal / acceptance_criteria 全置換 / kpi_sheet_tab の gid・name /
   epic_label 追加・削除 / repo / 正本 URL)。**変更しないフィールドは指定しない** (スクリプトは指定された
   フィールドだけ上書きし、他は保持する)
2. 実行 (指定されたフラグだけ渡す):
   ```bash
   python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" edit <slug> \
     [--goal "<new goal>"] [--criteria "<c1>" --criteria "<c2>" ...] \
     [--kpi-gid <gid>] [--kpi-name "<name>"] \
     [--epic-label "<label>" | --clear-epic-label] \
     [--repo <repo>] [--source "<url>"]
   ```
   - `--goal` を指定すると spec の `goal` と goals.md の「ゴール 1 行」列の両方が更新される (乖離防止)
   - `--criteria` は指定した分だけの配列で丸ごと置換 (差分マージはしない)。既存を残したい項目も含めて
     フルリストを聞き直す
   - `kpi_sheet_tab` は `gid`/`name` を個別上書き可 (片方のみ指定でも既存値とマージされる)
   - 編集後も schema validate を通らなければスクリプトが exit 1 で拒否する (壊れた spec を書かない)
3. commit + push:
   ```bash
   git -C "$VOLANTE_REPO" add journal/specs/<slug>.json journal/goals.md
   git -C "$VOLANTE_REPO" commit -m "epic: edit <slug>"
   git -C "$VOLANTE_REPO" push
   ```

## list

dashboard を開かず現状を stdout で見るだけ。commit なし:

```bash
python3 "$VOLANTE_REPO/skills/volante-epic/scripts/epic_tool.py" --repo-root "$VOLANTE_REPO" list
```

## 非スコープ (触らない)

- `優先度` 列の変更 (konuma 専有、`skills/volante/SKILL.md` 芯 7)
- 対象 repo 側 (`.claude/goals/*.md` 等 tracer 資産) への同時反映
- slug のリネーム (実質 remove + add。必要なら個別に相談)
- goals.md の手書き旧形式行 (session セルが slug 形式でない行) の編集・削除
- `--create-issue` で作成する epic issue の body は最低限 (Goal + Acceptance Criteria) のみ。
  詳細な設計・タスク分解は `/issue` skill が担う (責務分離)。epic issue に後から追記する分には
  volante-epic 側は関知しない
