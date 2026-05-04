#!/usr/bin/env bash
# Nova Observatory — tmux dashboard for live dream loop monitoring
#
# Layout:
#   ┌─────────────────────────────┬─────────────────────────────┐
#   │ Pane 0: Execution           │ Pane 2: JQ Validator        │
#   │ (run loops, replay scripts) │ (watch latest record.json)  │
#   ├─────────────────────────────┤                             │
#   │ Pane 1: Heartbeat (logs)    │                             │
#   └─────────────────────────────┴─────────────────────────────┘
#
# Requirements: tmux >= 3.0, jq, watch (brew install watch)

set -euo pipefail

SESSION="nova"
NOVA_ROOT="${NOVA_ROOT:-$HOME/nova}"
EXPERIMENTS_ROOT="${EXPERIMENTS_ROOT:-$NOVA_ROOT/experiments}"

# --- Preflight ---
command -v tmux  >/dev/null || { echo "tmux not found";  exit 1; }
command -v jq    >/dev/null || { echo "jq not found";    exit 1; }
command -v watch >/dev/null || { echo "watch not found (brew install watch)"; exit 1; }

# --- Session setup ---
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -c "$NOVA_ROOT"

# Global QoL
tmux set  -g mouse on
tmux set  -g status-position top
tmux set  -g status-bg black
tmux set  -g status-fg cyan
tmux set  -g status-left  "[NOVA OBSERVATORY] "
tmux set  -g status-right "%H:%M:%S "

# --- Pane 0 (top-left): Execution shell ---
tmux send-keys -t "$SESSION":0.0 \
  "source .venv/bin/activate && clear && echo '[NOVA] ENGINE READY'" C-m

# --- Pane 1 (bottom-left): Heartbeat / logs ---
tmux split-window -v -l 40% -t "$SESSION":0.0 -c "$NOVA_ROOT"
tmux send-keys -t "$SESSION":0.1 \
  "while :; do exp=\$(ls -1dt $EXPERIMENTS_ROOT/*/ 2>/dev/null | head -1); \
   if [[ -n \"\$exp\" ]]; then \
     logs=\$(ls -1t \"\$exp\"*.log 2>/dev/null | head -1); \
     if [[ -n \"\$logs\" ]]; then tail -F \"\$logs\"; \
     else echo \"[heartbeat] \$exp — no logs yet\"; fi; \
   else echo \"[heartbeat] waiting for first experiment...\"; fi; \
   sleep 2; done" C-m

# --- Pane 2 (right): JQ Validator ---
tmux split-window -h -l 50% -t "$SESSION":0.0 -c "$NOVA_ROOT"
tmux send-keys -t "$SESSION":0.2 \
  "watch -n 1 -t -c 'f=\$(ls -1t $EXPERIMENTS_ROOT/*/iter*_record.json 2>/dev/null | head -1); \
   if [[ -n \"\$f\" ]]; then \
     echo \"LATEST RECORD: \$f\"; echo; \
     jq -C \"{iteration, status, score: .score.overall, reasoning: (.score.reasoning // \\\"\\\")[:100]}\" \"\$f\"; \
   else \
     echo \"Waiting for first iteration record...\"; \
   fi'" C-m

# --- Focus & attach ---
tmux select-pane -t "$SESSION":0.0
tmux attach -t "$SESSION"
