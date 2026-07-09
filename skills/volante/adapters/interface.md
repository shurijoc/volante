# volante adapter interface v1

volante は「どの TUI/multiplexer で並走セッションを動かしているか」に依存しない。
差は各 adapter 実装 (このディレクトリの `<adapter>.sh`) に閉じ込め、SKILL.md 本体は
以下 5 primitive の呼び出しだけで書く (issue #25)。

## 呼び出し規約

各 adapter は `skills/volante/adapters/<adapter名>.sh` という単一の実行可能スクリプトで、
第一引数に primitive 名、以降は引数を渡す CLI として呼ぶ:

```bash
ADAPTER="$VOLANTE_REPO/skills/volante/adapters/<adapter>.sh"
"$ADAPTER" list_sessions
"$ADAPTER" read_screen <id> [tail_lines]
"$ADAPTER" send_text <id> <body>
"$ADAPTER" send_key <id> <key>
"$ADAPTER" self_id
```

`<adapter>` は `~/.config/volante/config.json` (git 管理外、PC ごとの local config。
schema: `../templates/local-config.schema.json`) の `adapter` フィールドで決まる。
SKILL.md 側は config を読んで adapter スクリプトのパスを決めるだけで、primitive 呼び出し以降は
adapter 非依存のロジックだけを書く。

対応する adapter スクリプトが存在しない (未実装) 場合、呼び出し側は推測で代替せず
「adapter '<name>' 未実装。config を修正するか konuma に確認」で止まる (SKILL.md 2. 推測禁止の適用)。

## 5 primitive の contract

### `list_sessions() -> JSON array`

対象になりうる全セッション (Claude Code が動いていそうな pane/window) を JSON 配列で標準出力に返す。
1 要素のスキーマ:

```json
{
  "id": "string (adapter 内で一意。kitty なら window id、tmux なら pane id)",
  "title": "string (取得できなければ空文字列)",
  "cwd": "string (取得できなければ空文字列)",
  "pid": "number | null",
  "is_self": "boolean (self_id() と一致するか。判定不能なら false)"
}
```

- Claude Code らしきセッションだけに絞り込む判定方法は adapter ごとに異なってよい (foreground process の
  cmdline に `claude` を含む、等)。**絞り込みの精度は adapter ごとの既知の限界として adapter ファイル冒頭に
  コメントで明記する** (issue #25 の Unknown: 「Claude Code のセッション自動発見手段」は adapter 単位で
  ベストエフォート)
- 0 件・取得失敗時も空配列 `[]` を返し、呼び出し側 (SKILL.md 7.2) が「実測不可」と区別できるよう
  終了コード非 0 で異常を返す (正常時は 0 件でも exit 0)

### `read_screen(id, tail_lines=60) -> string`

指定セッションの画面出力 (直近 `tail_lines` 行) をプレーンテキストで標準出力に返す。
巡回の状態分類 (2. canonical_model の 5 分類) と送信結果検証 (7.4) の両方で使う。

### `send_text(id, body) -> なし`

指定セッションに文字列 `body` をそのまま入力として送る (改行を含んでよい)。**Enter や Esc の送出はしない**
— それは `send_key` の責務。SKILL.md 7.3 の複数行送信手順は `send_text` → sleep → `send_key esc` → sleep →
`send_key enter` のように primitive を明示的に組み合わせて書く。

### `send_key(id, key) -> なし`

抽象キー名 1 つを送る。**必須サポート**: `esc` / `enter` / `ctrl-c`。**推奨サポート** (WAITING の
AskUserQuestion モードでの選択肢移動に使う): `up` / `down`。未対応キーは exit 非 0 + stderr にメッセージ。

### `self_id() -> string | none`

巡回シェル自身が動いているセッションの id を返す (自ウィンドウ除外用)。判定不能なら空文字列を返し、
呼び出し側 (SKILL.md 7.1) が「自ウィンドウ判別不能」に倒せるようにする (2. 推測禁止)。

## 実装済み adapter

| adapter | ファイル | 状態 |
|---|---|---|
| kitty | `kitty.sh` | 実装済み (既存 `kitty @ ...` 呼び出しの集約、konuma の M1 Mac 環境で回帰なし確認) |
| tmux | `tmux.sh` | 最小実装 (list_sessions / read_screen / send_text / send_key(enter/esc/ctrl-c/up/down) / self_id) |
| wezterm | (未実装) | config の enum には存在するが adapter ファイルなし。選択されたら SKILL.md 側で「未実装」と案内し選び直させる |
| manual | (未実装) | 同上。最終手段 (人間コピペ) 用に enum だけ確保。需要が出たら追加 |

## adapter を追加するとき

1. `skills/volante/adapters/<name>.sh` を作り、上記 5 primitive を CLI dispatch で実装する
2. 未対応の primitive があれば省略せず、exit 非 0 + stderr 説明で明示する (silent no-op 禁止)
3. `templates/local-config.schema.json` の `adapter` enum に追加する
4. この表に行を追加する
