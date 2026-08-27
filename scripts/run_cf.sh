#!/usr/bin/env bash
# E3: run each counterfactual intervention as a single-case run.
#   usage: run_cf.sh <plan.jsonl> [max_turns]
#
# One case per invocation, because an intervention overrides one answer in
# one case. The baseline to compare against is the main-table row for the
# same model and turn budget — same config, no overrides — so no separate
# baseline pass is needed.
set -u
mkdir -p "${GB_OPS_DIR:-$HOME/graph_bench_runs/ops}"
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
plan=$1; turns=${2:-30}
CONC=$(cat "${GB_OPS_DIR:-$HOME/graph_bench_runs/ops}"/concurrency 2>/dev/null || echo 6)
log="runs/matrix/cf.log"

n=0
while IFS= read -r line; do
  case_id=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['task_id'])" "$line")
  info_id=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['info_id'])" "$line")
  sim=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['sim_config'])" "$line")
  run_id="cf-${case_id}-${info_id}"
  rd="runs/cf/${run_id}/${run_id}"
  [ -f "$rd/${case_id}.jsonl" ] && continue
  task=$(ls data/released/graphs/${case_id}.json 2>/dev/null) || continue
  n=$((n + 1))
  uv run --native-tls python -m graph_bench backbone run \
    --agent api --agent-config '{"max_tokens": 8000}' --sim-config "$sim" \
    --tasks "$task" --run-id "$run_id" --out "runs/cf/${run_id}" \
    --online --max-turns "$turns" --concurrency 1 >> "$log" 2>&1
  echo "$(date '+%H:%M:%S') cf $n: $run_id" >> "$log"
done < "$plan"
echo "== ran $n interventions"
