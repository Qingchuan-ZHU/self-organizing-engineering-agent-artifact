# Self-Organizing Engineering Agent — research artifact

AI-generated Worker, Reviewer, and blind-evaluator materials are experimental evidence, not human-certified engineering designs or formal ground truth. See [AI_GENERATED_CONTENT.md](AI_GENERATED_CONTENT.md), [AI_CONTENT_INVENTORY.csv](AI_CONTENT_INVENTORY.csv), and [PROVIDER_TERMS_REVIEW.md](PROVIDER_TERMS_REVIEW.md) for role-level classification and the dated terms review.

This is a **public release staging package** for the UGS-SYNTH D01 engineering-agent study. It contains the selected runtime, the public engineering brief, eight frozen Worker submissions, ten interactive Worker–Reviewer sessions, thirteen frozen blind post-hoc reviews, and the scripts used to verify and rebuild released tables. It is artifact documentation, not manuscript text. `UGS_FORMAL_STATE=NOT READY`.

## Study at a glance

- UGS-SYNTH D01 is a 22-file synthetic engineering brief. Its values are deterministic benchmark assumptions, not vendor data, production criteria, or engineering ground truth. The file-level source history, content assessment, and method attribution are recorded in [`BENCHMARK_PROVENANCE.md`](BENCHMARK_PROVENANCE.md); this review does not constitute rights clearance.
- The study has four paired replications: one `worker_only` run and one `explicit_collaboration` run per pair, for eight runs and eight final submissions.
- A pair uses the same public-world files, initial task prompt, model configuration, and runtime source baseline. The four pairs do not all use the same Git commit; the Pair 001 runtime boundary is documented in [`docs/experiments/PAIRED_REPLICATIONS.md`](docs/experiments/PAIRED_REPLICATIONS.md).
- The frozen records establish a four-pair study design. They do not state an a priori power calculation or another sample-size rationale; the four pairs should be read as the fixed scope of this study, not as a statistical-power claim.
- The four Explicit-collaboration Workers requested 2, 2, 4, and 2 interactive reviews, respectively: ten completed sessions. Review timing and frequency were Worker-selected.
- The separate blind evaluation covers all eight submissions with thirteen frozen successful passes: five submissions have two passes and three have one. It is incomplete as a repeated-pass comparison by design after the pre-reveal amendment.

## What the agents could do

The Worker has a persistent writable `project/` workspace and a read-only public `brief/`. Its five baseline tools are `list_files`, `read_file`, `write_file`, `execute_python`, and `finish_project`. In the Explicit-collaboration condition, the Worker also receives `submit_for_review` and decides whether and when to use it.

Each review request freezes a snapshot of the Worker project. The Reviewer runs with an independent model context and persistent `review/` workspace. It receives the public brief and the frozen snapshot through read-only mounts. Its tools are `list_files`, `read_file`, `write_file`, `execute_python`, and `finish_review`. It can write only in its own `review/` area, not in the Worker project. The Worker receives the structured findings and controls subsequent changes and review requests. See [`docs/architecture/WORKSPACE_AND_REVIEWER.md`](docs/architecture/WORKSPACE_AND_REVIEWER.md) and [`docs/reviewer/REVIEWER_BOUNDARY.md`](docs/reviewer/REVIEWER_BOUNDARY.md).

## Evidence map

- `cases/ugs_synth_d01/public/` — the 22 public brief, basis, and catalog files shared by all eight runs.
- `BENCHMARK_PROVENANCE.md` — repository-level provenance review, per-file SHA-256 and Git history, and the named-method reference; no benchmark file is modified by the review.
- `experiments/configurations/` — the eight frozen configuration, pre-run, and artifact-hash records.
- `evidence/final_submissions/` — the eight final Worker project snapshots. `INDEX.json` and tree hashes link each snapshot to its run.
- `evidence/reviewer_records/` — ten formal reviews and ten snapshot manifests. The manifests bind each review to the project snapshot supplied at that request.
- `evidence/reviewer_trajectories/trajectory_events.jsonl` — sanitized Worker and Reviewer tool/workspace events with content bodies omitted.
- `evidence/reviewer_trajectories/review_session_summary.csv` — request order, snapshot hash, finding count, and completion status for all ten sessions. Worker response indices are not included because the frozen public records do not provide a reliable index.
- `evidence/reviewer_workspace_case_study/` — three byte-identical examples of Reviewer-created checks from Pair 001 review 1. They are selected activity evidence, not a complete trajectory or ground truth.
- `evidence/blind_evaluation/` — thirteen frozen review outputs, normalized findings, reveal and integrity records, the exact evaluator prompt/schema, and the aggregate failed-attempt summary.
- `analysis/` — the deterministic table builder, manifest verifier, privacy scanner, and rebuilt outputs.

## Blind post-hoc evaluation

The evaluator performed a model-based review of one anonymous submission at a time against its public brief. It did not receive condition labels, compare submissions, or produce an overall score, winner, or ranking. Zero findings were allowed. The complete source prompt and required JSON schema are published byte-for-byte at `evidence/blind_evaluation/protocol/evaluator_prompt.md` and `evidence/blind_evaluation/protocol/review_response.schema.json`. Their source SHA-256 values and validation across all thirteen frozen passes are recorded in `SOURCE_PROVENANCE.json`.

The output taxonomy is `confirmed_violation`, `unsupported_claim`, `suspected_risk`, `semantics_gap`, and `observation`. These are evaluator labels, not engineering ground truth. The evaluator required fourteen review areas to be marked `full`, `sampled`, or `not_checked`; the protocol and schema define the actual coverage and output requirements.

The original schedule had sixteen jobs. The final set has thirteen successful frozen reviews and full primary coverage of eight submissions. `submission_A/pass_02` had four unsuccessful/interrupted attempts before closeout; `submission_B/pass_02` and `submission_C/pass_01` were not run after the pre-reveal amendment. No omitted job was rerun after reveal. The exact attempt categories and freeze criteria are in [`evidence/blind_evaluation/FAILED_ATTEMPT_NOTES.md`](evidence/blind_evaluation/FAILED_ATTEMPT_NOTES.md).

All thirteen successful review records used the published prompt and schema hashes. Their recorded process exit codes were zero; output validation passed; frozen input trees were unchanged; no condition/run-ID string was detected in an output; and controller manifest/integrity checks passed. The controller's recorded acceptance rule concerns process validity and integrity. It does not select a review according to whether its findings are favorable, unfavorable, numerous, or sparse.

All evaluator outputs were frozen before the condition mapping was revealed at `2026-09-28T02:41:23Z`. The post-analysis integrity record reports that no frozen evaluator output changed after reveal.

## Results and limits

The released normalized records contain five confirmed issue groups in each condition. Unsupported N-1 evidence appears in four of four Worker-only submissions and one of four Explicit-collaboration submissions in this available blind evaluation. An Explicit submission retains a high-severity port-reference defect. The issue profiles differ; the evaluator also disagreed across repeated passes on some status and severity labels. These observations do not establish that Reviewer use reduces overall violations, causes the N-1 difference, or makes either condition statistically superior.

The Pair 003 Worker-only run ended as `terminated_without_finish_project`; its final artifacts and status are retained. The interactive Reviewer findings are advisory. The Codex blind evaluation is model-based post-hoc evidence, not formal engineering ground truth. See [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for the frozen run-manifest count bug, review-session snapshot repetition, evaluator limitations, and remaining evidence gaps.

## Verify and reproduce

Run these commands from this directory with Python 3.10 or newer:

```text
python analysis/scripts/verify_release_manifest.py
python analysis/scripts/build_release_tables.py --output-dir analysis/rebuilt_tables
python analysis/scripts/build_release_tables.py --check
python analysis/scripts/audit_release_package.py
```

In this staging snapshot, the manifest lists 331 files; adding `RELEASE_MANIFEST.json` gives 332 package files. The manifest's `file_count` excludes itself, and the Git commit anchors the manifest file. See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the offline test and Docker commands.

To inspect the long-horizon runner's required arguments without starting a run:

```text
python scripts/run_ugs_synth_durable_replication.py --help
```

To start a new trajectory, replace the example ID with a unique run ID and select one condition:

```text
python scripts/run_ugs_synth_durable_replication.py --run-id <unique-run-id> --condition explicit_collaboration
```

The other condition is `worker_only`; `--env-file` and `--image` are optional runner arguments. Starting a trajectory requires Docker and a locally configured DeepSeek credential. It makes provider calls, costs may be material and change over time, and outputs are nondeterministic. The release-preparation checks make no provider calls and start no trajectory. This package does not claim bit-for-bit replication of model output.

Run the curated offline tests from this package directory with Python 3.10 and `uv`:

```text
uv run --project . --python 3.10 --with-requirements requirements-test.txt python -m pytest tests/ugs_synth_minimal/test_runtime.py tests/ugs_synth_interleaved_review tests/test_release_package.py -q --import-mode=importlib -k "not real_container_isolation_and_persistent_python_workspace"
uv run --project . --python 3.10 --with-requirements requirements-test.txt python -m pytest tests/test_release_package.py -q --import-mode=importlib
```

These tests use fake providers and temporary workspaces; they do not call a model. The Docker-dependent integration command and its execution boundary are documented in [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## License

- Software, runtime, tests, and release tooling: Apache-2.0.
- UGS-SYNTH benchmark and authored documentation: CC BY 4.0.
- Frozen experimental evidence: CC BY 4.0 to the extent applicable rights exist and are held by the repository owner.

See [LICENSE.md](LICENSE.md) for path-level scope, [ATTRIBUTION.md](ATTRIBUTION.md) for creator attribution, [NOTICE.md](NOTICE.md) for factual notices, [AI_GENERATED_CONTENT.md](AI_GENERATED_CONTENT.md) for model-output limits, and [BENCHMARK_PROVENANCE.md](BENCHMARK_PROVENANCE.md) for benchmark provenance.

## Not included and rights status

Raw provider traces, complete Worker/Reviewer messages, failed evaluator workspaces, hidden benchmark/reference solutions, full run databases, and the unreleased remainder of the evaluator result tree are excluded. The aggregate attempt facts do not include raw prompts, responses, reasoning, credentials, or machine paths.

Provider terms and their dated review are summarized in [`PROVIDER_TERMS_REVIEW.md`](PROVIDER_TERMS_REVIEW.md). The release-governance decision accepts the factual, non-promotional provider and tool names used in this package; historical terms and authentication-route uncertainties are not publication blockers. This package is marked **PUBLICATION READY** for the staged research artifact. That status does not certify engineering designs or change `UGS_FORMAL_STATE=NOT READY`.
