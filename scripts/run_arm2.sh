#!/usr/bin/env bash
# One arm on the 50-case variance subset, with every knob an experiment
# varies exposed as a parameter.
#   usage: run_arm2.sh <run_id> [agent_config] [sim_config] [max_turns]
#
# A new file rather than an edit of run_arm.sh: a running wrapper reads its
# script incrementally, so rewriting one in place resumes it at a stale
# byte offset.
#
# The metrics/judge steps run ONLY if the backbone finished on its own and
# produced a transcript for every task, so a killed run never leaves this
# wrapper to judge the *next* run's partial output.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
run_id=$1; cfg=${2:-'{"max_tokens": 8000}'}; sim=${3:-'{}'}; turns=${4:-20}
out="runs/matrix/${run_id}"; rd="${out}/${run_id}"; log="runs/matrix/${run_id}.log"
tasks='data/variance/graphs/*.json'
expected=$(ls $tasks | wc -l | tr -d ' ')

uv run --native-tls python -m graph_bench backbone run \
  --agent api --agent-config "$cfg" --sim-config "$sim" --tasks "$tasks" \
  --run-id "$run_id" --out "$out" --online --max-turns "$turns" \
  --concurrency 6 >> "$log" 2>&1
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
if [ "$rc" -ne 0 ] || [ "$got" -ne "$expected" ]; then
  echo "== $run_id: backbone rc=$rc, ${got}/${expected} transcripts — NOT judging"
  exit 1
fi

uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 6 >> "$log" 2>&1
echo "== $run_id done"
