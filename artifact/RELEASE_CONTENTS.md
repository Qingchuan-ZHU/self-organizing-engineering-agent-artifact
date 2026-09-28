# Release contents

| Area | Contents | Source and handling |
|---|---|---|
| Runtime | Selected Worker/Reviewer runtime, direct provider adapter, Docker executor, sandbox/tools, durable store and runner | Runtime hashes are checked against each frozen run configuration. Pair 001 source variants are retained under `experiments/runtime_variants/pair_001/`. |
| Public benchmark | UGS-SYNTH D01 brief, engineering basis, catalogs, and task contract | Exact 22-file copy verified against the frozen public-world hash. |
| Benchmark provenance | `BENCHMARK_PROVENANCE.md` file-by-file origin assessment, Git history, current source SHA-256 values, third-party-content review, and named-method reference | Repository-level provenance review; the frozen 22-file public world is unchanged. Benchmark files are licensed as scoped in `LICENSE.md`; external cited publications are not included or relicensed. |
| Configurations | Eight `freeze.json`, `pre_run_checks.json`, and `artifact_hashes.json` files | Frozen files copied byte-for-byte. |
| Final submissions | Four pairs with one Worker-only and one Explicit-collaboration submission each | Copied from the blind-evaluation packages and checked against revealed source-project tree hashes. |
| Interactive Reviewer evidence | Ten formal review records, ten snapshot manifests, sanitized trajectory events, and a session/snapshot summary table | Review records and manifests are unchanged; summary table is deterministically derived from published records. Three selected safe Reviewer-created scripts are included as an explicitly incomplete case study. |
| Blind-evaluation protocol | Exact `evaluator_prompt.md` and `review_response.schema.json` used by all thirteen successful frozen passes | Byte-for-byte copies of controller source files; both hashes match all thirteen pass manifests and are listed in `SOURCE_PROVENANCE.json`. |
| Blind-evaluation results | Thirteen `review.json`/`review.md` pairs, normalized findings, reveal mapping, protocol amendment, and pre/post integrity records | Frozen records copied unchanged. No finding taxonomy or result was reinterpreted. |
| Blind-evaluation attempts | Aggregate counts, reason categories, scheduled-job outcomes, and source-evidence hashes | Derived from controller/process metadata. Raw failed workspaces, prompts, responses, and process output remain excluded. |
| Analysis | Deterministic submission, pair, Reviewer-session, and count tables; manifest verifier; privacy scanner | Reads released evidence only; makes no model call and changes no finding labels. |
| Source provenance | Source branch/commit, run IDs, public-world hash, source-copy hashes, runtime checks, evaluator-protocol hashes, and Reviewer case-study hashes | `SOURCE_PROVENANCE.json` distinguishes exact frozen/source copies from generated summaries and documentation. |
| AI-generated-content disclosure and inventory | Role-level classification for Worker, Reviewer, blind evaluator, deterministic analysis, and release-preparation material | Group-level classification; frozen evidence remains unchanged and model findings are explicitly not engineering ground truth. |
| Provider terms review | Dated official DeepSeek and OpenAI terms review, output/input responsibilities, disclosure rules, historical applicability caveats, and the release-governance decision | Summarizes linked official terms; factual provider/tool attribution is accepted without endorsement or legal-clearance claims. |
| Licensing and attribution | `LICENSE.md`, official standard texts in `LICENSES/`, `ATTRIBUTION.md`, and `NOTICE.md` | Path-based license scope; AI evidence and third-party rights are explicitly bounded. |
| Third-party notices | `THIRD_PARTY_NOTICES.md` | No vendored third-party source requiring a separate notice was identified; external dependencies keep their own licenses. |

The package excludes credentials, hidden benchmark fixtures/reference solutions, raw provider transcripts, full run databases, failed evaluator workspaces, and the unreleased remainder of the evaluator result tree. `LICENSE.md` is the licensing scope source of truth for the staged package.
