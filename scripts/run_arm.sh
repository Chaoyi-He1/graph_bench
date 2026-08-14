#!/usr/bin/env bash
# One paired A/B row on the 50-case variance subset.
#   usage: run_arm.sh <run_id> [agent_config_json] [sim_config_json]
#
# Same as run_ab.sh but also forwards a SimulatorConfig override, for arms
# that vary the simulator rather than the agent (leak profiles, thresholds).
# Kept as a separate file because editing a shell script that a running
# wrapper is still reading resumes it at a stale byte offset.
#
# The metrics/judge steps run ONLY if the backbone finished on its own and
# produced a transcript for every task. Without that guard, killing a run
# mid-flight leaves this wrapper alive, and it walks on to judge whatever is
# in the output directory — which, after a relaunch, is the *next* run's
# partial transcripts. That silently writes a judgments.json for 6 unfinished
# cases and makes the poller believe the row is done.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
run_id=$1; cfg=${2:-'{"max_tokens": 8000}'}; sim=${3:-'{}'}
out="runs/matrix/${run_id}"; rd="${out}/${run_id}"; log="runs/matrix/${run_id}.log"
tasks='data/variance/graphs/*.json'
expected=$(ls $tasks | wc -l | tr -d ' ')

uv run --native-tls python -m graph_bench backbone run \
  --agent api --agent-config "$cfg" --sim-config "$sim" --tasks "$tasks" \
  --run-id "$run_id" --out "$out" --online --max-turns 20 --concurrency 6 >> "$log" 2>&1
rc=$?
got=$(ls "$rd"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" -ne 0 ] || [ "$got" -ne "$expected" ]; then
  echo "== $run_id: backbone rc=$rc, ${got}/${expected} transcripts — NOT judging"
  exit 1
fi

uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 6 >> "$log" 2>&1
echo "== $run_id done"
