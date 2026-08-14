#!/usr/bin/env bash
# Drive one row to full coverage: a case that crashes fewer times than the
# retry cap leaves NO metrics entry and NO agent_failed marker — it just
# vanishes from the row. So compare against the task list itself, reset the
# ledger for anything missing, rerun, and repeat until coverage stops
# improving. Then judge.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; . ./.env 2>/dev/null || true; set +a
name=$1; cfg=$2; tasks=$3
run_id="${name}-r1"; out="runs/matrix/${run_id}"; rd="${out}/${run_id}"
log="runs/matrix/${run_id}.log"

missing_count() {
  python3 - "$rd" "$tasks" <<'PY'
import json, os, sys, glob
rd, pattern = sys.argv[1], sys.argv[2]
want = {os.path.basename(p)[:-5] for p in glob.glob(pattern)}
mp = os.path.join(rd, 'metrics.json')
have = set(json.load(open(mp))['testcases']) if os.path.exists(mp) else set()
miss = sorted(want - have)
led_path = os.path.join(rd, 'retries.json')
if miss and os.path.exists(led_path):
    led = json.load(open(led_path))
    for k in miss:
        led.pop(k, None)          # give every missing case a fresh budget
    json.dump(led, open(led_path, 'w'))
for k in miss:                    # drop partial transcripts so they restart
    p = os.path.join(rd, k + '.jsonl')
    if os.path.exists(p):
        os.remove(p)
print(len(miss))
PY
}

prev=99999
for attempt in 1 2 3 4; do
  n=$(missing_count)
  echo "== ${run_id}: attempt ${attempt}, missing ${n}"
  [ "${n:-0}" -eq 0 ] && break
  [ "${n:-0}" -ge "$prev" ] && { echo "== ${run_id}: no progress, stopping"; break; }
  prev=$n
  uv run --native-tls python -m graph_bench backbone run \
    --agent api --agent-config "${cfg}" --tasks "${tasks}" \
    --run-id "${run_id}" --out "${out}" --online --max-turns 20 \
    --concurrency 4 >> "$log" 2>&1
  uv run --native-tls python -m graph_bench recorder metrics "$rd" >> "$log" 2>&1
done

uv run --native-tls python -m graph_bench judge run "$rd" \
  --model "${JUDGE_MODEL:-$GRAPH_BENCH_LLM_MODEL}" --online --concurrency 6 \
  >> "$log" 2>&1
echo "== ${run_id}: finished"
