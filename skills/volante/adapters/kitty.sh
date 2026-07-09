#!/usr/bin/env bash
# volante kitty adapter — implements adapters/interface.md's 5 primitives via `kitty @ ...`
# remote control. Existing kitty-specific volante behavior (SKILL.md pre-#25) is preserved here
# 1:1, only relocated out of SKILL.md so the skill body can stay adapter-agnostic (issue #25).
#
# Known limitations (kept here per interface.md "絞り込みの精度は adapter ごとの既知の限界"):
# - list_sessions の Claude Code 判定は foreground_processes の cmdline に "claude" を含むかどうかの
#   ベストエフォート。別プロセス名で起動された claude は拾えない
# - multi-line send_text の submit には、本文を送った後 esc → enter を「間に sleep を挟んで」別々に
#   送る必要がある (1 回にまとめると submit が落ちる、kitty 固有の既知挙動)。この sleep はこのスクリプトの
#   責務ではなく呼び出し側 (SKILL.md 7.3) が primitive 呼び出しの間に入れる
set -euo pipefail

_usage() {
  echo "usage: $(basename "$0") {list_sessions|read_screen <id> [tail_lines]|send_text <id> <body>|send_key <id> <esc|enter|ctrl-c|up|down>|self_id}" >&2
  exit 1
}

_ls_json() {
  kitty @ ls
}

self_id() {
  if [ -n "${KITTY_WINDOW_ID:-}" ]; then
    echo "$KITTY_WINDOW_ID"
    return 0
  fi
  # フォールバック: $KITTY_WINDOW_ID が空/未 export のときは is_focused な window を自己候補にする
  # (SKILL.md 7.1 の既存フォールバック仕様を移設)
  _ls_json | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for osw in data:
    for tab in osw.get("tabs", []):
        for w in tab.get("windows", []):
            if w.get("is_focused"):
                print(w["id"])
                sys.exit(0)
'
}

list_sessions() {
  local self
  self="$(self_id 2>/dev/null || true)"
  _ls_json | SELF_ID="$self" python3 -c '
import json, os, sys
self_id = os.environ.get("SELF_ID", "")
try:
    data = json.load(sys.stdin)
except Exception:
    print("[]")
    sys.exit(1)
out = []
for osw in data:
    for tab in osw.get("tabs", []):
        for w in tab.get("windows", []):
            procs = w.get("foreground_processes", []) or []
            cmdlines = [" ".join(p.get("cmdline", []) or []) for p in procs]
            if not any("claude" in c for c in cmdlines):
                continue
            wid = str(w.get("id"))
            out.append({
                "id": wid,
                "title": w.get("title", "") or "",
                "cwd": w.get("cwd", "") or "",
                "pid": (procs[0].get("pid") if procs else None),
                "is_self": bool(self_id) and wid == str(self_id),
            })
print(json.dumps(out))
'
}

read_screen() {
  local id="$1"
  local tail_lines="${2:-60}"
  kitty @ get-text --match "id:$id" --extent screen | tail -n "$tail_lines"
}

send_text() {
  local id="$1"
  local body="$2"
  kitty @ send-text --match "id:$id" "$body"
}

send_key() {
  local id="$1"
  local key="$2"
  case "$key" in
    esc) kitty @ send-text --match "id:$id" $'\x1b' ;;
    enter) kitty @ send-text --match "id:$id" $'\r' ;;
    ctrl-c) kitty @ send-text --match "id:$id" $'\x03' ;;
    up) kitty @ send-text --match "id:$id" $'\x1b[A' ;;
    down) kitty @ send-text --match "id:$id" $'\x1b[B' ;;
    *)
      echo "kitty adapter: unsupported key '$key' (supported: esc/enter/ctrl-c/up/down)" >&2
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
