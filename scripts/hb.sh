#!/usr/bin/env bash
cd "$(dirname "$0")/.."
{
  echo "=== HB $(date '+%H:%M')"
  for r in gpt56 gpt55 glm51 kimi25; do
    python3 - "$r" <<'PY'
import json, os, sys, glob
r = sys.argv[1]
d = f'runs/matrix/{r}-r1/{r}-r1'
mp, jp = os.path.join(d, 'metrics.json'), os.path.join(d, 'judgments.json')
fin = res = 0
if os.path.exists(mp):
    tc = json.load(open(mp))['testcases']
    fin = len(tc)
    res = sum(1 for v in tc.values()
              if v['metrics']['final_user_satisfaction'] == 'resolved')
judged = len(json.load(open(jp))['testcases']) if os.path.exists(jp) else 0
turns = empty = 0
for f in glob.glob(os.path.join(d, '*.jsonl')):
    for line in open(f):
        t = (json.loads(line).get('agent') or {}).get('text')
        if t is not None:
            turns += 1
            empty += (not t.strip())
er = f'{100 * empty / turns:.1f}%' if turns else '-'
print(f'{r:<7} fin={fin:3d}/229 resolved={res:3d} judged={judged:3d} empty={er}')
PY
  done
  echo "procs backbone=$(ps aux | grep -c '[b]ackbone run') judge=$(ps aux | grep -c '[j]udge run')"
} >> runs/heartbeat.log 2>&1
tail -7 runs/heartbeat.log
