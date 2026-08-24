#!/usr/bin/env bash
# Counterfactual interventions, several at a time.
#   usage: run_cf2.sh <plan.jsonl> [max_turns] [parallel]
#
# Each intervention overrides a different answer, so they cannot share one
# backbone run — each is its own single-case invocation. Running them one
# after another wasted the gateway: the first pass took 10.5 hours for 58
# interventions at an effective concurrency of 1. This keeps N in flight,
# which is where the throughput actually is.
#
# A new file rather than an edit of run_cf.sh — a running wrapper reads its
# script incrementally and would resume at a stale byte offset.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
plan=$1; turns=${2:-30}; par=${3:-6}
log="runs/matrix/cf2.log"
started=0; skipped=0

while IFS= read -r line; do
  [ -z "$line" ] && continue
  read -r case_id info_id sim <<EOF
$(python3 -c "
import json,sys
r=json.loads(sys.argv[1])
print(r['task_id'], r['info_id'], r['sim_config'])" "$line")
EOF
  run_id="cf-${case_id}-${info_id}"
  rd="runs/cf/${run_id}/${run_id}"
  if [ -f "$rd/${case_id}.jsonl" ]; then skipped=$((skipped+1)); continue; fi
  task="data/released/graphs/${case_id}.json"
  [ -f "$task" ] || continue
  # Block until a slot frees, then launch. `wait -n` returns on the first
  # child to exit, so a slow case never holds the whole batch.
  while [ "$(jobs -rp | wc -l)" -ge "$par" ]; do wait -n; done
  started=$((started+1))
  (
    uv run --native-tls python -m graph_bench backbone run \
      --agent api --agent-config '{"max_tokens": 8000}' --sim-config "$sim" \
      --tasks "$task" --run-id "$run_id" --out "runs/cf/${run_id}" \
      --online --max-turns "$turns" --concurrency 1 >> "$log" 2>&1
  ) &
done < "$plan"
wait
echo "cf2: launched $started, skipped $skipped already-run"
