# Review: gh_ggml-org_whisper.cpp_1246

**complete Maven Central registration process**

- source: https://github.com/ggml-org/whisper.cpp/issues/1246
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_ggml-org_whisper.cpp_1246.json` · raw thread: `data/github_v0/raw/gh_ggml-org_whisper.cpp_1246.json`

```mermaid
flowchart LR
    N0["<b>N0 Maven Central registration incomplete</b><br/><small>info: 1</small>"]
    N1["<b>N1 repository created, signing required</b><br/><small>info: 3</small>"]
    N2["<b>N2 upload rejected with 401</b><br/><small>info: 6</small>"]
    N3["<b>N3 Sonatype credentials corrected</b><br/><small>info: 7</small>"]
    N3_x["<b>N3_x regenerated PGP secret aftermath</b><br/><small>info: 8</small>"]
    N4["<b>N4 staging rejects undiscoverable signing key</b><br/><small>info: 11</small>"]
    N5["<b>N5 signing public key published</b><br/><small>info: 12</small>"]
    N_terminal["<b>terminal Java library released</b><br/><small>info: 13</small>"]
    N0 ==>|"⚡ Complete the Sonatype registration prerequisite by creating the empty `OSSRH-94491` GitHub repository and opening the registration issue."| N1
    linkStyle 0 stroke:#f97316,stroke-width:2px
    N1 ==>|"🔀 ❓maven_staging_put_returns_401_unauthorized + ⚡Configure GPG signing credentials so the Java jar can be signed before publication."| N2
    linkStyle 1 stroke:#a855f7,stroke-width:2px
    N2 ==>|"⚡ Replace the incorrect Sonatype deployment credentials with the maintainer's valid Sonatype account credentials."| N3
    linkStyle 2 stroke:#f97316,stroke-width:2px
    N3 ==>|"💥 blind: Regenerate the legacy `PGP_SECRET` value from the local GPG key and retry the existing workflow."| N3_x
    linkStyle 3 stroke:#ef4444,stroke-width:2px
    N3_x ==>|"⚡ Use the existing GPG private-key and passphrase secrets directly in the Java signing workflow instead of relying on the ineffective legacy `PGP_SECRET` setup."| N4
    linkStyle 4 stroke:#f97316,stroke-width:2px
    N4 ==>|"⚡ Publish the signing key's public half to a public OpenPGP keyserver so Sonatype can validate the artifact signatures."| N5
    linkStyle 5 stroke:#f97316,stroke-width:2px
    N5 ==>|"⚡ Retry and complete the Maven staging release now that Sonatype can discover the signing public key, then require confirmation that the Java artifact is actually released."| N_terminal
    linkStyle 6 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3 normal
    class N3_x normal
    class N4 normal
    class N5 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> @ggerganov, as you mentioned in my PR, you still need to create an empty GitHub repository named `OSSRH-94491` before we can publish the Java library.

## Satisfaction conditions

1. Must identify the final blocking cause: Sonatype could not validate the signed artifacts because public key `449e073f9dc10735` was not available from its configured OpenPGP keyservers.
2. The diagnosis must be grounded in the staged sequence of evidence: the initial 401 was addressed by correcting Sonatype credentials, the signing workflow was changed to use the GPG private-key and passphrase secrets, and Sonatype then explicitly reported that it could not locate the corresponding public key.
3. Must publish the signing public key to a public keyserver, confirm that it is discoverable, and retry the Maven staging release.
4. Must not treat regeneration of the legacy `PGP_SECRET` alone as the fix; that attempt was tried and the Java workflow still failed.
5. Must not declare the issue resolved merely because the repository, credentials, secrets, or public key were configured; resolution requires the reporter to verify that the Java library was actually released.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | solution_only | req_info: empty_ossrh_94491_repository_required_before_java_publication<br>elements: creates_required_empty_ossrh_repository, completes_initial_registration_prerequisite | Complete the Sonatype registration prerequisite by creating the empty `OSSRH-94491` GitHub repository and opening the registration issue. |
| `e2_N1__N2` | mixed | req_info: jar_must_be_signed_with_gpg_credentials<br>elements: configures_gpg_private_key_secret, configures_gpg_passphrase_secret, signs_jar_before_publication | Configure GPG signing credentials so the Java jar can be signed before publication. |
| `e3_N2__N3` | solution_only | req_info: wrong_jira_credentials_reproduce_same_401, maven_staging_put_returns_401_unauthorized<br>elements: corrects_sonatype_username_and_password, addresses_401_unauthorized | Replace the incorrect Sonatype deployment credentials with the maintainer's valid Sonatype account credentials. |
| `e4_N3__N3_x` | solution_only **BLIND** | req_info: jira_credentials_replaced_with_sonatype_login<br>elements: regenerates_legacy_pgp_secret | Regenerate the legacy `PGP_SECRET` value from the local GPG key and retry the existing workflow. |
| `e5_N3_x__N4` | solution_only | req_info: jar_must_be_signed_with_gpg_credentials, regenerated_pgp_secret_still_fails_workflow<br>elements: uses_gpg_private_key_and_passphrase_in_workflow, does_not_rely_on_regenerating_pgp_secret_as_the_fix | Use the existing GPG private-key and passphrase secrets directly in the Java signing workflow instead of relying on the ineffective legacy `PGP_SECRET` setup. |
| `e6_N4__N5` | solution_only | req_info: staging_validation_cannot_locate_public_key_449e073f9dc10735<br>elements: identifies_missing_public_key_as_staging_failure, publishes_signing_public_key_to_keyserver, confirms_key_is_publicly_discoverable | Publish the signing key's public half to a public OpenPGP keyserver so Sonatype can validate the artifact signatures. |
| `e7_N5__N_terminal` | solution_only | req_info: staging_validation_cannot_locate_public_key_449e073f9dc10735, signing_public_key_published_to_openpgp_keyserver<br>elements: grounds_retry_in_public_key_now_being_discoverable, retries_and_completes_staging_release, asks_user_to_verify_java_artifact_is_released | Retry and complete the Maven staging release now that Sonatype can discover the signing public key, then require confirmation that the Java artifact is actually released. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | We cannot publish the Java library yet because the required empty `OSSRH-94491` repository has not been created. |
| `N1` |  | 2 | 0 | The registration repository now exists, but the Java artifact has not been published because the jar must be signed. |
| `N2` |  | 2 | 0 | Publishing `whispercpp-1.4.0.jar` to the Sonatype staging repository returns HTTP 401 Unauthorized. I get exactly the same error when I deli |
| `N3` |  | 1 | 0 | The Sonatype credentials have been replaced, but the Java release has still not completed. |
| `N3_x` |  | 1 | 0 | I generated a new `PGP_SECRET` and reran the Java workflow from master, but the workflow still fails. |
| `N4` |  | 3 | 0 | The signed artifacts reach Sonatype staging, but validation repeatedly reports that public key `449e073f9dc10735` cannot be located on the c |
| `N5` |  | 1 | 0 | The signing public key is now available through the <redacted-host> search URL, but I have not yet confirmed the Maven Central release. |
| `N_terminal` | ✓ | 1 | 0 | The Java library is released successfully. |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **n/a** · 0 of 0 findings survived independent refutation.

__


## Review checklist

> The graph is the case's ANSWER KEY, not a transcript: edge order need
> not mirror thread chronology. Do not file chronology mismatch as a
> defect; what must be faithful is who knew what, when.

Structural (machine-checked by `scripts/validate.py`, re-verify after edits):

- [ ] validates: schema + info-containment + terminal reachability

Semantic (the defect catalog — check each against the source thread):

- [ ] **Faithful blind paths** — every `is_known_blind_path` edge corresponds
  to an attempt actually falsified in the thread (or a brush-off the
  reporter rejected). No invented failures; no ACCEPTED fix mislabeled as
  a blind path (the most common LLM defect class).
- [ ] **Gettable required info** — every id in any `solution.required_info`
  is obtainable: a clarification on some edge, or in the start node's
  info_state, or volunteered (with matching `volunteered_info` text).
  Engineer-only inference belongs in `info_inferred_by_engineer` /
  `inference_hint`, not in hard required_info.
- [ ] **Measurement-class rule** — handler-initiated measurements the user
  executed (bisections, test builds, config probes, version checks) are
  clarification edges, not solutions; their answers state what the
  measurement showed.
- [ ] **No logistics gates** — `required_elements_for_full_match` encode the
  technical diagnostic→fix chain, not release/packaging/scheduling
  remarks the engineer merely mentioned.
- [ ] **Coherent reveals** — each `user_answer_in_this_oncall` is consistent
  with the thread, delivers what it promises, and stays in the user's
  voice (no future knowledge, no diagnosis the user never made).
- [ ] **Symptoms are observations** — `symptoms_visible` contains only what
  the user can see; no causes or advice.
- [ ] **Terminal semantics** — satisfaction_conditions demand root cause +
  evidence grounding + prohibition of falsified moves + user verification;
  the terminal node is the verified-resolved state.
- [ ] **Image assignment** — referenced attachments exist and sit on the
  right hook (opening / node symptom / clarification evidence).
- [ ] **Persona** — matches the reporter's actual expertise and style.

## How to sign off

1. Edit the graph JSON if needed (authored fields only; keep
   `concrete_example` as the factual record).
2. `uv run scripts/validate.py '<graph path>'`
3. Set `metadata.hitl_reviewed: true` in the graph JSON.
4. Re-run `uv run scripts/make_review_docs.py` to refresh this page.
