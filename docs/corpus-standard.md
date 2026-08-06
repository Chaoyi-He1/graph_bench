# Corpus membership standard

What a case must satisfy to enter the released corpus, and what the
release numbers mean. Written after a stricter review protocol overturned
an earlier round of sign-offs — the history is kept because it is the
evidence that the standard bites.

## The pipeline a case passes through

1. **Source filter** (LLM, 7 boolean gates): resolved with a confirmed
   fix, technically specific, multi-turn diagnostic, environment-bound,
   reporter engaged, safe content, annotatable.
2. **Drafting** (LLM) against the DSL rules, with a validate-and-repair
   loop: schema validators (edge-type consistency, reference integrity,
   info-state containment, required-info availability, orphan-info
   introduction, required/inferred disjointness) plus lint (terminal
   reachability, stranded nodes, blind-only starts, verification-timing,
   level consistency, image existence/uniqueness/provenance,
   future-knowledge literals in scoring fields, fix-naming in
   clarification questions).
3. **Scrub** (deterministic): role-stable pseudonyms, path usernames,
   private hostnames, review/commit metadata identities, credential
   shapes. Identity maps live outside the repository.
4. **Two-stage model review** (see below).

## Two-stage review

A single reviewer pass over-files: on a control group of cases that a
stronger model had already signed, the one-pass prompt refused 3/3 and,
after verification, still confirmed blocking findings on 5/8. Manual
adjudication of a sample showed those findings were **real** — so the
protocol is: file, then substantiate.

- **Stage 1 (reviewer)** reads the graph and the full thread and files
  findings with severity.
- **Stage 2 (verifier)** re-tests every blocking (high/medium) finding
  and marks it CONFIRMED (quotes the offending graph text and the thread
  evidence), REFUTED (sources contradict it or it misapplies a rule), or
  UNSUBSTANTIATED (plausible, no decisive quotes). Stage 2 is given the
  rules that first-pass reviewers most often misapply: the repo-snapshot
  date is a code anchor and not a knowledge cutoff; provenance URLs are
  policy; disclosed multi-user folds are allowed; engineer conclusions
  belong in the engineer-side fields; a terminal may summarize what the
  thread establishes.

Every finding — confirmed, refuted or unsubstantiated — is published per
case in `data/REVIEW_FINDINGS.json`. A reader can therefore audit the
bar, not just trust it.

## Membership

**Released corpus** = machine gates all green **and** no CONFIRMED
high-severity finding after stage 2.

Confirmed *medium* findings do not block release; they are published
per case. Rationale: mediums in this corpus are overwhelmingly
annotation-quality issues (an undisclosed fold, a redundant required id,
an over-specific counterfactual) that mislead a human reader more than
they mislead an evaluated agent, and the finding text tells a user
exactly what to distrust. Highs are different in kind — they break the
answer key: a leaked fix, an unreachable graded path, a scored root
cause the thread never accepted, or a fabricated outcome.

**Reported numbers must state both**: cases released, and cases with
zero confirmed findings of any severity ("clean"). Reporting only the
first would overstate the corpus.

## Defect classes the standard was built from

Each was found in real drafts, confirmed against sources, and then
turned into a rule, a machine gate, or both:

| Class | Now caught by |
|---|---|
| future-knowledge literals in scoring fields | machine lint (PR/version tokens absent from user-speakable channels) |
| clarification question names the fix | machine lint (terminal solution's distinctive vocabulary) + rule 4e(iv) |
| invented terminal verification | rule 4f(i) + review |
| cross-participant causal splicing | rule 4f(ii) + review |
| several problems in one thread chained into one | rule 4f(iii) + review |
| retracted hypothesis scored as root cause | rule 4e(iii) + review |
| invented mechanism for a link-only fix | rule 4e(ii) + review |
| measurement modeled as a kept system change | rule 4 + review |
| identity residue (handles, display names, review metadata, hosts, path usernames) | scrub layers + review |

## Honest limitations

- Review is model-executed. It is auditable (per-case findings, quoted
  evidence) but it is not human sign-off.
- Stage 2 shares a model family with stage 1; independence is procedural
  (fresh context, refute-first instructions, quote requirement), not
  architectural.
- Medium findings ride along with released cases by design; the
  published finding list is the mitigation.
