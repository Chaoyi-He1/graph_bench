"""Does the judge-free metric depend on the matcher?

Re-derives premature proposals with the DETERMINISTIC offline matcher.

Every run used the online matcher, which is an LLM call -- so the metrics
the paper calls "model-free" are only judge-free. This replays each stored
agent turn through the offline heuristic at the node the transcript records,
giving a version with no model anywhere in the loop.
"""
import json, glob, os, sys, statistics as st
from math import sqrt, comb
sys.path.insert(0, 'src')
from graph_bench.user_simulator.matching import classify_turn, match_edge
from graph_bench.oncall_graph.models import Edge

CORPUS = 'data/released/graphs'
M = 'runs/matrix'
graphs = {}
for p in glob.glob(CORPUS + '/*.json'):
    graphs[os.path.basename(p)[:-5]] = json.load(open(p))['graph']

def offline_premature(run):
    out = {}
    for path in glob.glob(os.path.join(run, '*.jsonl')):
        case = os.path.basename(path)[:-6]
        g = graphs.get(case)
        if g is None:
            continue
        by_from = {}
        for e in g['edges']:
            by_from.setdefault(e['from'], []).append(e)
        offers = {e['from'] for e in g['edges']
                  if e['edge_type'] in ('solution_only', 'mixed')}
        n = 0
        for line in open(path):
            row = json.loads(line)
            ev = row.get('event') or {}
            agent = row.get('agent') or {}
            text = agent.get('text')
            node = ev.get('node_before')
            if not text or node is None:
                continue
            comp = classify_turn(text, online=False)
            if not comp.has_solution:
                continue
            cands = [Edge(**e) for e in by_from.get(node, [])
                     if e['edge_type'] in ('solution_only', 'mixed')]
            res = match_edge(text, 'solution_only', cands, online=False)
            if res.type == 'none' and node not in offers:
                n += 1
        out[case] = n
    return out

def sign_p(d):
    pos = sum(1 for x in d if x > 0); neg = sum(1 for x in d if x < 0)
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

EXCLUDE = {'m-glm51': {'pg_bug_17928', 'gh_nodejs_node_47207'}}
ROWS = {}
for name, r in (('gpt-5.6','m-gpt56'),('gpt-5.5','m-gpt55'),
                ('GLM-5.1','m-glm51'),('Kimi-2.5','m-kimi25')):
    d = offline_premature(f'{M}/{r}/{r}')
    for k in EXCLUDE.get(r, set()): d.pop(k, None)
    ROWS[name] = d

print('premature proposals per case, OFFLINE deterministic matcher')
for n, c in ROWS.items():
    print(f'  {n:10} {st.mean(c.values()):.2f}  n={len(c)}')
print()
for a, b in [('gpt-5.6','Kimi-2.5'),('gpt-5.6','GLM-5.1'),('gpt-5.5','GLM-5.1'),
             ('gpt-5.6','gpt-5.5'),('GLM-5.1','Kimi-2.5')]:
    ca, cb = ROWS[a], ROWS[b]
    k = sorted(set(ca) & set(cb))
    d = [cb[c] - ca[c] for c in k]
    m, sd = st.mean(d), st.stdev(d)
    t = m / (sd / sqrt(len(d))); p = sign_p(d)
    print(f"  {a+' < '+b:22} n={len(d):3} diff={m:+.3f} t={t:6.2f} p={p:8.2e} "
          f"{'REAL' if abs(t) > 2.6 and p < 0.01 else 'not called'}")
