# volante

複数の並走 Claude Code セッション (別リポジトリ・別 kitty ウィンドウで自律実行中) を、
開発リーダーとして巡回・差配する Claude Code skill。名前はサッカーのボランチ (試合全体を読んで采配する司令塔) から。

「好きにやって OK」の白紙委任はしない。送る指示は必ず「何を」「どこまで」を明示し、
すべての判断をログに残して定期的に判断基準を更新する (PDCA)。背景と設計判断は [CLAUDE.md](CLAUDE.md)。

## 使い方

```
/volante        # 1 回起動 = 1 巡回 (Plan → Do → Check → Act → 報告)
/loop 10m /volante   # 定期巡回したい場合 (daemon は持たない)

/volante-epic add|remove|edit|list   # epic (Spec) の追加・削除・編集・一覧を対話 1 回で
```

## インストール (ローカル)

```bash
claude --plugin-dir /path/to/volante
# または skill として symlink
ln -s /path/to/volante/skills/volante ~/.claude/skills/volante
```

## 前提

- kitty + `allow_remote_control yes` (`kitty @ ls` / `send-text` / `get-text` を使う)
- 判断ログはこのリポジトリの `journal/` に集約される
