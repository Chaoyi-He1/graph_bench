"""Data-preparation pipeline: harvest public threads, LLM-draft task graphs.

CAB-style staging (arXiv:2507.10646) with the container-synthesis stage
replaced by graph drafting + schema validation:

1. coarse repo/issue filters (search API),
2. thread profiling (reporter engagement, attachments),
3. LLM issue-level filter (yes/no gates),
4. LLM graph drafting against the causal-graph schema,
5. machine validation with a bounded repair loop,
6. human review queue (``hitl_reviewed`` stays false until reviewed).
"""
