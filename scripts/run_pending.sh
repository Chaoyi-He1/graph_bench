#!/usr/bin/env bash
# The four experiments still outstanding, run one after another.
#
# They were three separate queues, each waiting on "gateway idle" — so the
# moment the arm before them finished, all three would have started at
# once and split a gateway that sustains one run's worth of throughput.
# Ordered here instead, most consequential first: the id-rendering arm can
# invalidate the main table, so it should not be the one still waiting if
# something goes wrong overnight.
set -u
LOG=/tmp/gb-v2/runs/queue.log
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }

idle() {
  for i in $(seq 1 3000); do
    pgrep -f 'graph_bench (backbone|judge)' > /dev/null || return 0
    sleep 60
  done
}

idle
say 'FINAL 1/4: id-rendering paired arm (can invalidate the main table)'
(cd /tmp/gb-v6 && ./scripts/run_arm2.sh gpt56-idfix '{"max_tokens": 8000}' '{}' 20 \
  >> runs/matrix/gpt56-idfix.wrapper.log 2>&1)
say "FINAL 1/4 done rc=$?"

idle
say 'FINAL 2/4: E-judgeswap, re-judging the table with GLM-5.1'
for row in m-gpt56 m-kimi25 m-glm51 m-gpt55; do
  rd=/tmp/gb-v6/runs/matrix/$row/$row
  [ -f "${rd}-judged-by-lynx_ai_glm_51/judgments.json" ] && continue
  (cd /tmp/gb-v6 && set -a && . ./.env && set +a && \
    ./.venv/bin/python scripts/judge_swap.py judge "$rd" \
      --model lynx_ai_glm_5.1 --concurrency 4 \
      >> runs/matrix/e9-judgeswap.log 2>&1)
  say "  E-judgeswap $row rc=$?"
done
say 'FINAL 2/4 done'

idle
say 'FINAL 3/4: E-counterfactual v2, 60 interventions, 6 at a time'
(cd /tmp/gb-v6 && ./scripts/run_cf2.sh runs/cf-plan-v2.jsonl 30 6 \
  >> runs/matrix/cf2.wrapper.log 2>&1)
say "FINAL 3/4 done rc=$?"

idle
say 'FINAL 4/4: E-images, multimodal arms already running/complete'
# e7-mm-on is judged; e7-mm-off finishes on its own wrapper. Judge it
# here only if its wrapper died before judging.
rd=/tmp/gb-v6/runs/matrix/e7-mm-off/e7-mm-off
if [ ! -f "$rd/judgments.json" ] && [ -f "$rd/metrics.json" ]; then
  (cd /tmp/gb-v6 && set -a && . ./.env && set +a && \
    uv run --native-tls python -m graph_bench judge run "$rd" \
      --model "$GRAPH_BENCH_LLM_MODEL" --online --concurrency 4 \
      >> runs/matrix/e7-mm-off.log 2>&1)
  say "  E-images judged rc=$?"
fi
say 'FINAL 4/4 done — all four pending experiments complete'
