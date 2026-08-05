# Datasheet

Following Gebru et al., *Datasheets for Datasets*. Numbers refer to
corpus v1.0 (79 cases); see `docs/dataset-stats.md` for the full tables.

## Motivation

**Why was the dataset created?** To evaluate whether an agent can run a
*diagnostic conversation* — elicit the right evidence from a human,
avoid attempts already known to fail, and ground its fix in what was
actually collected — without requiring a live execution environment.
Existing benchmarks either require containerized reproduction (which
biases toward reproducible, actively maintained projects) or script the
user's replies in advance.

**Who created it and who funded it?** Assembled by the authors from
public sources; no external funding. Drafting and review used
commercially available LLMs.

## Composition

**What do instances represent?** One instance is a resolved support
thread rewritten as a causal task graph: nodes are (system state,
information state) pairs, edges carry clarification questions with the
answers the reporter actually gave at that point, and/or solution
proposals. Attempts the thread falsified are marked as known-blind
paths. Each instance also carries satisfaction conditions and the
commit of the project's default branch at issue-creation time.

**How many instances?** 79 graphs across 7 domains (Mozilla non-UI 15,
databases 12, systems/networking 12, ML/inference 11, IoT/home
automation 11, language runtimes 9, web frameworks 9), drawn from
threads created 2021–2026 (median 48 messages, 12–185).

**Is any information missing?** Attachments that had already expired at
crawl time (dead image hosts) could not be archived; the graphs do not
reference them. Threads are captured at crawl time and do not track
later edits.

**Does the data contain confidential or offensive content?** Sources are
public bug trackers and mailing lists. A screening gate rejects threads
with security-sensitive exploit detail, harassment, or heavy personal
data. Content is technical discussion of software defects.

**Does it identify people?** Not after processing. All handles, display
names, e-mail addresses, mail signatures, filesystem-path usernames and
private hostnames are pseudonymized (`reporter`, `participantN`) or
redacted. Identity maps are kept outside the repository. Organization
and product accounts are deliberately preserved so technical content
(package names, URLs) stays intact. Residual-risk note: pseudonymization
does not defeat re-identification by anyone who searches the quoted
technical text against the public source — this is inherent to
republishing public thread content and is why the mapping is never
published.

## Collection

**How was the data acquired?** GitHub REST API, Bugzilla REST API, and
the postgresql.org list archives, all public, rate-limit respecting.
Attachments are downloaded at crawl time because signed URLs expire.

**Sampling strategy.** Repository lists chosen for domain balance; issue
search filtered to closed issues with substantial comment counts; then a
model-run screening gate requires: resolved with a confirmed fix,
technically specific, multi-turn diagnostic, environment-bound (a
maintainer could not trivially reproduce it in a container),
reporter-engaged, safe content, annotatable. Yield is deliberately low
(for the PostgreSQL list, roughly 0.25 usable threads per month).

**Who was involved?** Harvesting and drafting are automated. Review and
sign-off were performed by LLMs (see below), not by the thread
participants, who were not contacted.

**Ethical review.** No institutional review was sought; the data is
public technical discussion, republished under permissive-source terms
with identities removed. Precedents: BugsRepo (Zenodo, CC-BY-4.0),
Mozilla's own bugbug redistribution, the-stack-github-issues.

## Preprocessing

Threads are rendered role-aware (reporter comments uncapped) and drafted
into graphs by an LLM under a rule set with machine validators and lint
(schema consistency, information containment, required-info
availability, orphan information, verification timing, level
consistency, image provenance, future-knowledge literals in scoring
fields). Raw threads are kept alongside the graphs; both scrubbed
threads and graphs are published, and every raw is re-fetchable from its
public source.

## Uses

**Intended use.** Benchmarking conversational-debugging agents;
studying clarification behavior and evidence grounding; ablations on
user simulation.

**Uses to avoid.** Training data for models intended to impersonate
specific developers; any attempt to re-identify participants; treating
graph annotations as ground truth about the projects' engineering
history (they are answer keys for evaluation, reconstructed from a
thread, not maintainer-endorsed).

**Known limitations.** Machine-drafted and machine-signed: sign-off was
performed by LLM reviewers under a documented rule set, with every
verdict and finding published (`data/REVIEW_FINDINGS.json`), but no
human validated every case. English only. Open-source projects only.
Environment-bound selection means easily reproducible bugs are
under-represented by construction.

## Distribution

Code under Apache-2.0. Thread-derived data is redistributed from
permissively licensed sources with identities removed; the identity maps
and reviewer-filed identity declarations are **not** distributed. A
takedown channel is offered: open an issue on the repository and the
case will be removed.

## Maintenance

Maintained by the authors on GitHub. Corpus versions are git tags
(`corpus-v1.0`); evaluation results reference the tag they were produced
against. Re-running the harvesters reproduces the raws; the drafting
step is stochastic and reproduces the *method*, not byte-identical
graphs.
