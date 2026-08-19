#!/usr/bin/env bash
# Everything after the main table, so the pipeline drains to done with
# nobody present. Serial by design: the gateway is the ceiling (measured —
# concurrency 12 gives 3.87 turns/min, exactly what 6 gives), so an extra
# arm only makes the table land later.
set -u
LOG=/tmp/gb-v2/runs/queue.log
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }

for i in $(seq 1 4000); do
  [ -f /tmp/gb-v6/runs/matrix/m-gpt55/m-gpt55/judgments.json ] && break
  sleep 120
done
say 'main table drained; starting E3, E8, E7'

# E3 — 60 counterfactual interventions, one case each. The main-table row
# at the same config is the baseline, so there is no separate baseline pass.
if [ ! -f /tmp/gb-v6/runs/cf/.done ]; then
  say 'E3 counterfactual interventions'
  (cd /tmp/gb-v6 && ./scripts/run_cf.sh runs/cf-plan.jsonl 30 >> runs/matrix/cf.wrapper.log 2>&1)
  mkdir -p /tmp/gb-v6/runs/cf && touch /tmp/gb-v6/runs/cf/.done
  say "E3 done ($(ls -d /tmp/gb-v6/runs/cf/cf-* 2>/dev/null | wc -l | tr -d ' ') interventions)"
fi

# E8 — the frozen config under a different simulator. A result that holds
# only under one simulator is a property of that model, not the benchmark.
if [ ! -f /tmp/gb-v6/runs/matrix/e8-simswap/e8-simswap/judgments.json ]; then
  say 'E8 simulator swap'
  (cd /tmp/gb-v6 && ./scripts/run_row3.sh e8-simswap '{"max_tokens": 8000}' '{}' 20 \
     'data/variance/graphs/*.json' 'lynx_bench_gpt_5.5' \
     >> runs/matrix/e8-simswap.wrapper.log 2>&1)
  say 'E8 done'
fi

# E7 — the no-images ablation, this time against an agent that can
# actually see them. Restricted to the 97 cases that carry screenshots:
# on the other 132 both arms are identical and would only dilute it.
I='data/images_subset/graphs/*.json'
for arm in "e7-mm-on|{}" "e7-mm-off|{\"send_images\": false}"; do
  id=${arm%%|*}; scfg=${arm#*|}
  rd=/tmp/gb-v6/runs/matrix/$id/$id
  [ -f "$rd/judgments.json" ] && { say "skip $id"; continue; }
  say "E7 $id"
  (cd /tmp/gb-v6 && ./scripts/run_row2.sh "$id" \
     '{"max_tokens": 8000, "multimodal": true}' "$scfg" 30 "$I" \
     >> "runs/matrix/${id}.wrapper.log" 2>&1)
  say "E7 $id done"
done
say 'all queued experiments drained'
