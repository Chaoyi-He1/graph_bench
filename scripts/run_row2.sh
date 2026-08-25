#!/usr/bin/env bash
# One matrix row over an arbitrary task set.
#   usage: run_row2.sh <run_id> <agent_config> <sim_config> <max_turns> <tasks_glob>
#
# A new file rather than an edit of run_arm2.sh: a running wrapper reads its
# script incrementally, so rewriting one in place resumes it at a stale
# byte offset.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
run_id=$1; cfg=${2:-'{"max_tokens": 8000}'}; sim=${3:-'{}'}; turns=${4:-30}
tasks=${5:-'data/released/graphs/*.json'}
out="runs/matrix/${run_id}"; rd="${out}/${run_id}"; log="runs/matrix/${run_id}.log"
expected=$(ls $tasks | wc -l | tr -d ' ')
# Live knob, read at launch: a multi-day table should not need its queue
# restarted to retune. Throughput is latency-bound per case — one turn
# costs ~77s wall (68s of it the agent call), so N cases in flight give
# N/77s turns per second until the gateway pushes back. Where that point
# is, is measured per row rather than assumed.
CONC=$(cat /tmp/gb-v2/runs/concurrency 2>/dev/null || echo 6)

uv run --native-tls python -m graph_bench backbone run \
  --agent api --agent-config "$cfg" --sim-config "$sim" --tasks "$tasks" \
  --run-id "$run_id" --out "$out" --online --max-turns "$turns" \
  --concurrency "$CONC" >> "$log" 2>&1
rc=$?
# A transcript file appears when a case STARTS, so counting files
# accepts a run whose cases all crashed. metrics.json gains an entry only
# on completion; that is the number to check.
got=$(python3 - "$rd" <<'PYCHK'
import json, os, sys
p = os.path.join(sys.argv[1], 'metrics.json')
print(len(json.load(open(p))['testcases']) if os.path.exists(p) else 0)
PYCHK
)
# A row this long will lose the odd case to a terminal API error; judge at
# 95% rather than throwing away days of work over two crashes.
floor=$(( expected * 95 / 100 ))
if [ "$got" -lt "$floor" ]; then
  echo "== $run_id: backbone rc=$rc, ${got}/${expected} transcripts — NOT judging"
  exit 1
fi

uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 6 >> "$log" 2>&1
echo "== $run_id done (${got}/${expected}, concurrency=${CONC})"
