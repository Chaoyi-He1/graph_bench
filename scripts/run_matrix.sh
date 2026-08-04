#!/usr/bin/env bash
# Model-matrix driver (WP2 main table): for each (agent config, round),
# run backbone -> recorder metrics -> judge into a fresh run dir.
#
# Usage:
#   scripts/run_matrix.sh <matrix.tsv> <tasks_glob> <rounds>
# matrix.tsv lines: <name>\t<agent_config_json>   ('#' comments allowed)
#   the special json {} uses the GRAPH_BENCH_LLM_* env fallbacks.
#
# Comparability: the simulator and judge are pinned via SIM_MODEL /
# JUDGE_MODEL (falling back to GRAPH_BENCH_LLM_MODEL) — only the agent
# varies across rows. Each (name, round) gets its own out dir, so reruns
# after a crash resume per the runner's metrics.json/retry-ledger rules;
# a completed (name, round) with judgments.json is skipped entirely.
#
# macOS ships bash 3.2: no mapfile/associative arrays here.
set -u

MATRIX=${1:?matrix.tsv path}
TASKS=${2:?tasks glob}
ROUNDS=${3:-2}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

set -a; . ./.env 2>/dev/null || true; set +a

while IFS=$'\t' read -r name cfg; do
    case "$name" in ''|'#'*) continue;; esac
    r=1
    while [ "$r" -le "$ROUNDS" ]; do
        run_id="${name}-r${r}"
        out="runs/matrix/${run_id}"
        if [ -f "${out}/${run_id}/judgments.json" ]; then
            echo "== ${run_id}: already judged, skipping"
            r=$((r + 1)); continue
        fi
        echo "== ${run_id}: backbone"
        uv run --native-tls python -m graph_bench backbone run \
            --agent api --agent-config "${cfg}" \
            --tasks "${TASKS}" --run-id "${run_id}" --out "${out}" \
            --online --max-turns 20 --concurrency 4 \
            > "runs/matrix/${run_id}.log" 2>&1
        echo "== ${run_id}: metrics + judge"
        uv run --native-tls python -m graph_bench recorder metrics \
            "${out}/${run_id}" >> "runs/matrix/${run_id}.log" 2>&1
        uv run --native-tls python -m graph_bench judge run \
            "${out}/${run_id}" --model "${JUDGE_MODEL:-$GRAPH_BENCH_LLM_MODEL}" \
            --online --concurrency 6 >> "runs/matrix/${run_id}.log" 2>&1
        tail -1 "runs/matrix/${run_id}.log"
        r=$((r + 1))
    done
done < "$MATRIX"
echo "matrix complete"
