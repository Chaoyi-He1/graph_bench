#!/usr/bin/env bash
# One row, with the simulator model pinnable per run.
#   usage: run_row3.sh <run_id> <agent_cfg> <sim_cfg> <max_turns> <tasks> [sim_model]
#
# The simulator drives both the simulated user and the turn->edge judge,
# so swapping it is the E8 stability check: a result that only holds
# under one simulator is a property of that model, not of the benchmark.
# A new file rather than an edit of run_row2.sh — a running wrapper reads
# its script incrementally and would resume at a stale byte offset.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
run_id=$1; cfg=${2:-'{"max_tokens": 8000}'}; sim=${3:-'{}'}; turns=${4:-30}
tasks=${5:-'data/released/graphs/*.json'}
[ $# -ge 6 ] && [ -n "$6" ] && export SIM_MODEL="$6"
out="runs/matrix/${run_id}"; rd="${out}/${run_id}"; log="runs/matrix/${run_id}.log"
expected=$(ls $tasks | wc -l | tr -d ' ')

uv run --native-tls python -m graph_bench backbone run \
  --agent api --agent-config "$cfg" --sim-config "$sim" --tasks "$tasks" \
  --run-id "$run_id" --out "$out" --online --max-turns "$turns" \
  --concurrency 6 >> "$log" 2>&1
rc=$?
got=$(ls "$rd"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
floor=$(( expected * 95 / 100 ))
if [ "$got" -lt "$floor" ]; then
  echo "== $run_id: backbone rc=$rc, ${got}/${expected} transcripts — NOT judging"
  exit 1
fi
uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 6 >> "$log" 2>&1
echo "== $run_id done (${got}/${expected}, SIM_MODEL=${SIM_MODEL:-default})"
