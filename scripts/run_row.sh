#!/usr/bin/env bash
# One matrix row, standalone so rows can run in parallel.
# usage: run_row.sh <name> <agent_config_json> <tasks_glob>
#
# A case that exhausts its retry ledger is recorded as agent_failed, which
# would silently shrink this model's sample relative to the other rows. So
# after the main pass we sweep those cases: drop their metrics entry and
# ledger count, rerun them, and only then judge.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
name=$1; cfg=$2; tasks=$3
run_id="${name}-r1"; out="runs/matrix/${run_id}"; rd="${out}/${run_id}"
log="runs/matrix/${run_id}.log"
if [ -f "${rd}/judgments.json" ]; then echo "== ${run_id}: already judged"; exit 0; fi

backbone() {
  uv run --native-tls python -m graph_bench backbone run \
    --agent api --agent-config "${cfg}" --tasks "${tasks}" \
    --run-id "${run_id}" --out "${out}" --online --max-turns 20 \
    --concurrency 4 >> "$log" 2>&1
}

echo "== ${run_id}: backbone"; backbone
uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1

# Sweep agent_failed up to twice; each sweep re-opens those cases only.
for sweep in 1 2; do
  n=$(python3 - "$rd" <<'PY'
import json, os, sys
rd = sys.argv[1]
mp, rp = os.path.join(rd, 'metrics.json'), os.path.join(rd, 'retries.json')
if not os.path.exists(mp):
    print(0); raise SystemExit
batch = json.load(open(mp))
failed = [k for k, v in batch['testcases'].items()
          if v['metrics'].get('termination_reason') == 'agent_failed']
for k in failed:
    batch['testcases'].pop(k, None)
    for ext in ('.jsonl',):
        p = os.path.join(rd, k + ext)
        if os.path.exists(p):
            os.remove(p)
if failed:
    json.dump(batch, open(mp, 'w'))
    if os.path.exists(rp):
        led = json.load(open(rp))
        for k in failed:
            led.pop(k, None)
        json.dump(led, open(rp, 'w'))
print(len(failed))
PY
)
  [ "${n:-0}" -eq 0 ] && break
  echo "== ${run_id}: sweep ${sweep} reruns ${n} agent_failed case(s)"
  backbone
  uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
done

echo "== ${run_id}: judge"
uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "${JUDGE_MODEL:-$GRAPH_BENCH_LLM_MODEL}" --online --concurrency 6 \
  >> "$log" 2>&1
echo "== ${run_id}: done"
