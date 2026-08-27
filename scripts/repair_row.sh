#!/usr/bin/env bash
# Close the loop on cases a row lost to transient gateway failures.
#
# A row can finish "successfully" while missing cases: a truncated
# transcript (backbone crashed mid-conversation, no metrics entry) or a
# case the judge dropped. Neither shows in the aggregates, and the loss is
# not outcome-neutral — the first main-table row lost two terminal_resolved
# cases to one 502, so it reported a grade below what the model earned.
#
# This waits for each row to be judged, then repairs it: clear truncated
# transcripts, re-run the row (the backbone skips cases it already has),
# recompute metrics, re-judge (the judge skips cases already judged). Runs
# at low concurrency so it never starves the row still in flight.
set -u
mkdir -p "${GB_OPS_DIR:-$HOME/graph_bench_runs/ops}"
LOG="${GB_OPS_DIR:-$HOME/graph_bench_runs/ops}"/repair.log
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
cd /tmp/gb-v6 || exit 1
set -a; . ./.env 2>/dev/null || true; set +a

for pass in $(seq 1 400); do
  for row in m-gpt56 m-kimi25 m-glm51 m-gpt55; do
    rd="runs/matrix/$row/$row"
    [ -f "$rd/judgments.json" ] || continue
    # Never touch the row the queue is currently running.
    pgrep -f "run-id $row" > /dev/null && continue
    missing=$(./.venv/bin/python - "$rd" <<'PY'
import glob, json, os, sys
d = sys.argv[1]
t = {os.path.basename(p)[:-6] for p in glob.glob(d + '/*.jsonl')}
m = set(json.load(open(d + '/metrics.json'))['testcases'])
print(len(t - m))
PY
)
    [ "$missing" = "0" ] && continue
    say "$row: $missing truncated — repairing"
    ./.venv/bin/python - "$rd" <<'PY'
import glob, json, os, sys
d = sys.argv[1]
m = set(json.load(open(d + '/metrics.json'))['testcases'])
for p in glob.glob(d + '/*.jsonl'):
    if os.path.basename(p)[:-6] not in m:
        os.remove(p)
PY
    cfg='{"max_tokens": 8000}'
    case "$row" in
      m-kimi25) cfg='{"model": "lynx_ai_kimi_2.5", "api": "chat", "max_tokens": 8000}' ;;
      m-glm51)  cfg='{"model": "lynx_ai_glm_5.1", "api": "chat", "max_tokens": 8000}' ;;
      m-gpt55)  cfg='{"model": "lynx_bench_gpt_5.5", "effort": "high", "max_tokens": 8000}' ;;
    esac
    uv run --native-tls python -m graph_bench backbone run --agent api \
      --agent-config "$cfg" --sim-config '{}' \
      --tasks 'data/released/graphs/*.json' --run-id "$row" \
      --out "runs/matrix/$row" --online --max-turns 30 --concurrency 3 \
      >> "runs/matrix/${row}.log" 2>&1
    uv run --native-tls python -m graph_bench recorder metrics "$rd" \
      >> "runs/matrix/${row}.log" 2>&1
    uv run --native-tls python -m graph_bench judge run "$rd" \
      --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 3 \
      >> "runs/matrix/${row}.log" 2>&1
    say "$row repaired: $(ls $rd/*.jsonl | wc -l | tr -d ' ') transcripts"
  done
  sleep 600
done
