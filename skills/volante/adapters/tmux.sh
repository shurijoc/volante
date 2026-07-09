#!/usr/bin/env bash
# volante tmux adapter — implements adapters/interface.md's 5 primitives via tmux(1).
# Minimum implementation per issue #25 (kitty parity is not required — gaps fall back to
# "実測不可 → 人間確認" per SKILL.md's existing design, not to silent guessing).
#
# Known limitations:
# - list_sessions の Claude Code 判定は #{pane_current_command} (pane フォアグラウンドの
#   コマンド名) が "claude" を含むかどうかのベストエフォート。shell 経由の別名起動等は拾えない
# - send_key は esc/enter/ctrl-c/up/down のみ対応。AskUserQuestion モードでの複数行自由記述など
#   kitty 側で判明している未解決ケース (SKILL.md 7.3) は tmux でも未検証のまま持ち越す
set -euo pipefail

_usage() {
  echo "usage: $(basename "$0") {list_sessions|read_screen <id> [tail_lines]|send_text <id> <body>|send_key <id> <esc|enter|ctrl-c|up|down>|self_id}" >&2
  exit 1
}

self_id() {
  echo "${TMUX_PANE:-}"
}

list_sessions() {
  local self
  self="$(self_id)"
  if ! tmux list-panes -a -F '#{pane_id}|#{pane_title}|#{pane_current_path}|#{pane_pid}|#{pane_current_command}' 2>/dev/null | \
    SELF_ID="$self" python3 -c '
import os, sys, json
self_id = os.environ.get("SELF_ID", "")
out = []
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    parts = line.split("|", 4)
    if len(parts) < 5:
        continue
    pane_id, title, cwd, pid, cmd = parts
    if "claude" not in cmd:
        continue
    out.append({
        "id": pane_id,
        "title": title,
        "cwd": cwd,
        "pid": int(pid) if pid.isdigit() else None,
        "is_self": bool(self_id) and pane_id == self_id,
    })
print(json.dumps(out))
'
  then
    echo "[]"
    return 1
  fi
}

read_screen() {
  local id="$1"
  local tail_lines="${2:-60}"
  tmux capture-pane -p -t "$id" -S "-${tail_lines}"
}

send_text() {
  local id="$1"
  local body="$2"
  tmux send-keys -t "$id" -l -- "$body"
}

send_key() {
  local id="$1"
  local key="$2"
  case "$key" in
    esc) tmux send-keys -t "$id" Escape ;;
    enter) tmux send-keys -t "$id" Enter ;;
    ctrl-c) tmux send-keys -t "$id" C-c ;;
    up) tmux send-keys -t "$id" Up ;;
    down) tmux send-keys -t "$id" Down ;;
    *)
      echo "tmux adapter: unsupported key '$key' (supported: esc/enter/ctrl-c/up/down)" >&2
      return 1
      ;;
  esac
}

case "${1:-}" in
  list_sessions) list_sessions ;;
  read_screen) [ $# -ge 2 ] || _usage; read_screen "$2" "${3:-60}" ;;
  send_text) [ $# -ge 3 ] || _usage; send_text "$2" "$3" ;;
  send_key) [ $# -ge 3 ] || _usage; send_key "$2" "$3" ;;
  self_id) self_id ;;
  *) _usage ;;
esac
