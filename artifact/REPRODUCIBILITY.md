# Reproducibility and audit guide

## 1. Verify the staged package and frozen copies

From the package root:

```text
python analysis/scripts/verify_release_manifest.py
```

The verifier checks every listed package file, the manifest self-reference policy, the public-world hash and per-file map, all eight submission tree hashes, frozen configuration identity, and the recorded runtime source-hash checks. `SOURCE_PROVENANCE.json` provides source paths and SHA-256 values for byte-identical source/frozen copies. The exact evaluator prompt and schema are under `evidence/blind_evaluation/protocol/`; the thirteen successful pass manifests record matching prompt and schema hashes:

- `evaluator_prompt.md`: `9bb4394484b3504552d9634a58d501dfd087568cd30f00f98bdb2218d1055f5c`
- `review_response.schema.json`: `174f64c77f5594dcec758e042f011bd4831c5cfcbd8ea1c9ea101f52709e4092`

The manifest excludes its own SHA-256 and lists the sizes and hashes of the other package files. Its `file_count` excludes `RELEASE_MANIFEST.json`; total package file count is that value plus one. The Git commit containing the package anchors the manifest file.

## 2. Rebuild the released tables

```text
python analysis/scripts/build_release_tables.py --output-dir analysis/rebuilt_tables
python analysis/scripts/build_release_tables.py --check
```

The four outputs are `submission_summary.csv`, `pair_comparison.csv`, `review_session_summary.csv`, and `summary_counts.json`. The script reads only released run summaries, snapshot manifests, formal review records, final submission index, blind reviews, and the already-normalized finding labels. It makes no model call and does not relabel or merge a finding.

`review_session_summary.csv` counts findings from the authoritative per-session `formal_review.json` files, records each review's frozen snapshot hash and termination reason, and compares that hash with the previous review in the same run. Equal hashes mean the submitted project snapshot was unchanged. The frozen records do not provide a reliable Worker response index or turn for each review; the table does not infer one.

The tables preserve the historical source-manifest finding-count discrepancy: all four Explicit run manifests report zero, while the formal review records contain 20, 20, 14, and 15 findings. See `KNOWN_ISSUES.md`.

## 3. Blind-evaluation protocol and acceptance boundary

The published prompt defines a blind, one-submission-at-a-time, post-hoc model review. It permits zero findings and forbids a winner, ranking, overall score, and cross-submission comparison. The published schema requires fourteen coverage areas and allows the five finding labels `confirmed_violation`, `unsupported_claim`, `suspected_risk`, `semantics_gap`, and `observation`.

The frozen successful set has thirteen passes, full primary coverage of eight submissions, five double-pass and three single-pass submissions. The selection rule accepts process-valid, schema-valid, input-unchanged, leak-checked, integrity-passing outputs; it contains no finding-favorability or finding-count criterion. `evidence/blind_evaluation/FAILED_ATTEMPT_NOTES.md` gives the aggregate failure categories, seven separate preflight failures, exact omitted jobs, and the distinction between failed attempts and frozen successful reviews.

All thirteen successful outputs were frozen before the `2026-09-28T02:41:23Z` mapping reveal. The pre-reveal record reports a passing integrity check; the post-analysis record reports that no frozen evaluator output changed after reveal. The controller/operator-context exposure during preparation is recorded as a control-plane deviation. The recorded fresh evaluator process boundary is separate; the deviation is not evidence that those evaluator sessions received condition labels or the operator context.

## 4. Run offline checks

Install the locked project dependencies and run the complete local runtime/release suite, including the real Docker container test:

```text
uv run --project . --python 3.10 --with-requirements requirements-test.txt python -m pytest tests/ugs_synth_minimal/test_runtime.py tests/ugs_synth_interleaved_review tests/test_release_package.py -q --import-mode=importlib
```

Run the package smoke tests separately:

```text
uv run --project . --python 3.10 --with-requirements requirements-test.txt python -m pytest tests/test_release_package.py -q --import-mode=importlib
```

The offline unit tests use fake providers and temporary workspaces. The complete suite finished with **52 passed** on 2026-09-28. The separate release smoke suite finished with **5 passed**. Neither suite used a provider credential, called a model, or started a research trajectory.

The real-container isolation and persistent-Python-workspace integration test is `tests/ugs_synth_minimal/test_runtime.py::test_real_container_isolation_and_persistent_python_workspace`. It has no pytest marker; earlier curated commands deselected it by name with `-k "not real_container_isolation_and_persistent_python_workspace"`. The test constructs the published minimal runtime directly and does not initialize a provider or research runner. It verifies container Python execution, persistent writable project files, the read-only brief mount, inaccessible host-only files, blocked network access, and that a `DEEPSEEK_API_KEY` sentinel is not passed into the container.

Run the Docker integration test by itself with:

```text
uv run --project . --python 3.10 --with-requirements requirements-test.txt python -m pytest tests/ugs_synth_minimal/test_runtime.py::test_real_container_isolation_and_persistent_python_workspace -v --import-mode=importlib
```

Validation completed at **2026-09-28T05:45:20Z**. Docker client **29.0.1** and Docker Desktop **4.52.0 (210994)** / Engine **29.0.1** were available on the Linux/amd64 backend (WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, `containerd` v2.1.5, `runc` 1.3.3). The targeted integration test passed: **1 passed in 1.88s**. Across this release validation, external model API calls were **0** and new research trajectories were **0**.

Run the package privacy scan with:

```text
python analysis/scripts/audit_release_package.py
```

Its expected historical absolute-path hits are described in `SECURITY_AND_PRIVACY.md`; credential and private-URL hits must remain zero.

## 5. Start a new long-horizon trajectory

To inspect the entry point and its required arguments without starting a trajectory:

```text
python scripts/run_ugs_synth_durable_replication.py --help
```

An actual new run requires a new run ID, a condition choice, Docker, and a locally configured DeepSeek API credential. It makes live provider calls and is nondeterministic. The published lockfile captures the runtime dependencies but cannot recreate model output bit for bit. No new main experiment, Reviewer trajectory, blind evaluation, or other LLM evaluation was run to prepare this package.

## 6. Interpretation boundary

The evaluator's findings and the Worker/Reviewer checks are model-generated evidence, not formal engineering ground truth. The public package does not claim that Reviewer use reduces overall confirmed violations, that the observed N-1 difference is caused by collaboration, or that either treatment is statistically superior. `UGS_FORMAL_STATE=NOT READY` remains in force.

The [AI-generated-content disclosure](AI_GENERATED_CONTENT.md) and [inventory](AI_CONTENT_INVENTORY.csv) distinguish generated artifacts, deterministic derivations, analyst-coded findings, and release-preparation edits. The [provider terms review](PROVIDER_TERMS_REVIEW.md) records the official pages and versions reviewed on 2026-09-28, including unresolved DeepSeek mark-use and Codex authentication-route questions. These disclosures do not alter or certify frozen evidence.
