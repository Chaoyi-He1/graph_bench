# Corpus v2.0 — 207 released cases

Frozen 2026-08-06. Every released case carries `metadata.hitl_reviewed:
true`, meaning it passed the machine gates AND a two-stage model review
with no confirmed high-severity finding. 261 graphs were drafted; 207
released, 54 held back with their findings recorded.

## Composition

207 cases across **74 distinct projects** and three sources (GitHub
issues, bugzilla.mozilla.org, postgresql-bugs). No project exceeds 5% of
the corpus — the largest are mozilla (10), ggml-org (9), grafana (7),
triton-lang (7), micropython (6), istio (6), postgresql (6).

Domains represented: language runtimes and compilers, systems and
networking, databases and storage, ML/inference stacks, cloud-native
infrastructure, editors and desktop apps, IoT and home automation, web
frameworks, data platforms.

## Membership standard

A case is released only if:
1. **Machine gates pass** — schema validators (edge-type consistency,
   reference integrity, info-state containment, required-info
   availability, orphan-info introduction, required/inferred
   disjointness) and lint (terminal reachability, stranded nodes,
   blind-only starts, verification-timing, level consistency, image
   provenance, future-knowledge literals in scoring fields, fix
   vocabulary in clarification questions).
2. **Two-stage review finds no confirmed high-severity defect** — a
   reviewer reads the graph against the full source thread and files
   findings; an independent verifier then re-checks each finding against
   the thread and marks it CONFIRMED or UNSUBSTANTIATED. Only confirmed
   findings count. This matters: a single-pass reviewer refuses
   ~95% of cases, and verification overturns most of those refusals as
   unsupported. Both stages ran on the same model (GPT-5.6 via gateway);
   the verifier sees the finding, the graph and the thread, not the
   first reviewer's reasoning.

Confirmed medium and low findings are published per case in
`data/REVIEW_FINDINGS.json` rather than silently repaired — 47 released
cases have zero confirmed findings, the rest carry annotated ones.

**Review is model-executed, not human-executed.** It is auditable, not
authoritative: every finding, verdict and verifier decision is recorded.

## What the review caught (and the corpus was rebuilt against)

The earlier v1.0 sign-off (a stronger model, single pass) was retracted:
strict re-review found real high-severity defects in cases it had
signed — invented terminal verifications, clarification questions naming
the fix mechanism, cross-participant causal splicing. All 261 graphs
were redrafted against hardened rules rather than patched:

- **Rule 4f** (long multi-party threads): no invented terminal
  resolution; no splicing one participant's setup into another's causal
  chain; one diagnostic chain per case.
- **Rule 4e** (scoring discipline): no post-snapshot fix identifiers in
  scoring fields; no invented mechanisms for link-only fixes; the scored
  root cause is the thread's final accepted diagnosis; questions never
  carry answer-key vocabulary.
- **Privacy**: identity maps are per-case only (cross-case application
  was the root cause of every identity defect this corpus suffered);
  lowercase @-mentions, private hostnames, filesystem usernames, review
  metadata identities and reviewer-filed display names are all covered.
  See `docs/data-collection-and-privacy.md`.
