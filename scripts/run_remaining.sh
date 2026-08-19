#!/usr/bin/env bash
# Everything left after the main table, so the pipeline drains to done
# without anyone present. Waits for queue7 to finish rather than racing
# it — the gateway is the ceiling (measured: concurrency 12 gives 3.87
# turns/min, exactly what 6 gives), so an extra arm only slows the table.
set -u
LOG=/tmp/gb-v2/runs/queue.log
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }

# The table is done when its last row is judged.
for i in $(seq 1 4000); do
  [ -f /tmp/gb-v6/runs/matrix/m-gpt55/m-gpt55/judgments.json ] && break
  sleep 120
done
say 'main table drained; starting E3 + E8'

# E3: 60 counterfactual interventions, one case each.
if [ ! -f /tmp/gb-v6/runs/cf/.done ]; then
  say 'E3 counterfactual interventions'
  (cd /tmp/gb-v6 && ./scripts/run_cf.sh runs/cf-plan.jsonl 30 >> runs/matrix/cf.wrapper.log 2>&1)
  touch /tmp/gb-v6/runs/cf/.done 2>/dev/null || true
  say "E3 done ($(ls -d /tmp/gb-v6/runs/cf/cf-* 2>/dev/null | wc -l | tr -d ' ') interventions)"
fi

# E8: the frozen config on the variance subset under a different
# simulator. A result that only holds under one simulator is a property
# of that model, not of the benchmark.
rd=/tmp/gb-v6/runs/matrix/e8-simswap/e8-simswap
if [ ! -f "$rd/judgments.json" ]; then
  say 'E8 simulator swap (SIM_MODEL=lynx_bench_gpt_5.5)'
  (cd /tmp/gb-v6 && ./scripts/run_row3.sh e8-simswap '{"max_tokens": 8000}' '{}' 20 \
     'data/variance/graphs/*.json' 'lynx_bench_gpt_5.5' \
     >> runs/matrix/e8-simswap.wrapper.log 2>&1)
  say "E8 done rc=$?"
fi
say 'all queued experiments drained'
