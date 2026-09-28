# Release readiness report

**Status: PUBLICATION READY — technical validation, frozen-evidence integrity, benchmark provenance, AI-content disclosure, privacy review, and layered licensing are complete for the staged public research artifact.**
Audit date: 2026-09-28 UTC. `UGS_FORMAL_STATE=NOT READY` remains in force.

## Package

- Source branch: `codex/ugs-synth-d01`; frozen package source snapshot: `fa834d2836da8c4fabf9c767bc86d85e1f068a09`; governance-review baseline: `1726679dae4c8e6851eb94b2417e787f1886035f`.
- Staging directory: `release/public_package/`.
- The package contains 332 files and 7,678,853 bytes including `RELEASE_MANIFEST.json`. The manifest lists the other 331 files (7,513,397 bytes); the manifest itself is 165,456 bytes.
- `SOURCE_PROVENANCE.json` indexes 283 files: 84 byte-identical frozen copies and 199 other byte-identical source copies. The remaining 48 listed files are release documentation, tooling, indexes, license texts, the credential-free configuration template, and deterministic derived outputs.
- Contents include the 22-file public benchmark, eight final submissions, ten formal Reviewer records, ten snapshot manifests, thirteen frozen blind reviews, the exact two-file evaluator protocol, a three-file Reviewer workspace case study, and four deterministic tables.
- The source repository retains ten raw provider event streams totaling 1,490,853,659 bytes; they are excluded from the core package.

## Integrity and derived analysis

- `verify_release_manifest.py`: **PASS**; 331 listed files and 84 frozen copies verified. The manifest excludes itself; the Git commit anchors the manifest file.
- Public-world SHA-256: **PASS**, `af4260bc8e15bb44364038b6eeea9a6a6942677ae8e5e610971689415fd0880e`; all eight public-world file maps match.
- All eight final-submission tree hashes, frozen configuration copies, package source copies, and runtime source-hash checks: **PASS**.
- Exact evaluator prompt and schema copies match all thirteen successful pass manifests. Reviewer case-study copies match their source hashes and provenance records.
- `build_release_tables.py --check`: **PASS**, all four tables regenerate byte-for-byte. The Reviewer table counts formal findings from the ten session records and records snapshot repetition without inferring response indices.
- `CITATION.cff` validates against Citation File Format schema 1.2.0. Both standard license texts are unmodified official texts.
- Final package hygiene: **PASS**; no cache/bytecode directories, temporary files, SQLite state, actual `.env` or secret-named files, HTML pages, binary files, symlinks, or Git LFS pointers. Raw provider logs and failed evaluator workspaces remain excluded.
- The package contains no vendored dependency directories or binary assets. `release/public_package/.gitattributes` preserves packaged bytes, and release JSON writers now emit stable LF output.

## Benchmark provenance

- `BENCHMARK_PROVENANCE.md` reviews all 22 public-world files: 19 JSON files with synthetic provenance markers and three Markdown rule documents. Source and release copies are byte-identical.
- Git history records staged development: initial JSON files in `6961bc83b39f67e294241704d07b6caba326a195`, public-world reset and calculation basis in `dc783bf9e6bf56dceb4966ff1e7c77c8ae358356`, then the v1.1 semantic closure in `b2c673c6ae2784d29a8b826811e140db16ad50f1`. The provenance document records first appearance, semantic-history notes, and current source SHA-256 for every file.
- Named vendor/product IDs or regulatory-standard references found: **none identified**. Copied vendor or regulatory-standard tables/text found: **none identified**. This is a repository-level review, not proof that no unrecorded source exists.
- Generic engineering relations are distinguished from benchmark-specific coefficients, proxies, constraints, and semantics. The named Swamee–Jain method reference was verified against the ASCE bibliographic record and added to the provenance documentation; no public-world file was changed.
- Public-world SHA-256 before and after: `af4260bc8e15bb44364038b6eeea9a6a6942677ae8e5e610971689415fd0880e`; changed public-world files: **0**. Provenance findings and the owner-directed path-level license decision are recorded; this is not a legal-clearance claim.

## AI-generated content and provider terms

- Frozen configurations identify DeepSeek API / deepseek-flash for all eight Workers and all four Explicit-collaboration Reviewers. The package contains eight final Worker snapshots with 143 files, ten formal Reviewer records, and three selected Reviewer scripts.
- Thirteen blind reviews were run through OpenAI Codex CLI. Frozen records report gpt-5.5 as the requested/reported model value, but do not attest the provider-side identity or preserve the ChatGPT, API, or organization authentication route. Exact underlying model identifier is not established by the frozen evidence.
- The four deterministic analysis tables do not make model judgments. `normalized_findings.json` is analyst-coded post-hoc thematic matching. Worker outputs, Reviewer findings, and blind reviews are not engineering ground truth.
- Official DeepSeek and OpenAI terms were reviewed as of 2026-09-28. The package uses factual, non-promotional provider/tool attribution. The owner has accepted that attribution for this staged artifact; historical terms and authentication-route caveats remain documented and are not publication blockers. This is not a claim of provider endorsement or legal clearance.
- OpenAI Service Terms state that Codex code-generation output may be subject to third-party licenses, including open-source licenses. The owner has selected path-level licenses for project software and evidence; `LICENSE.md` preserves third-party rights and the frozen-evidence rights boundary.
- A bounded screen of 192 text files across published model outputs found four URL matches, all W3C SVG namespace declarations, and no email patterns, common vendor-name matches, or long quotation candidates. This is not exhaustive rights review.

## Licensing

- Software, runtime, tests, and release tooling use Apache-2.0. UGS-SYNTH benchmark material and authored documentation use CC-BY-4.0. Frozen experimental evidence is offered under CC-BY-4.0 only to the extent applicable rights exist and are held by the repository owner.
- The path-level scope and standard texts are in `release/public_package/LICENSE.md` and `LICENSES/`. No copyrightability or authorship determination is made for individual AI-generated outputs; no rights are created where none exist, and third-party rights are not overridden.

## Experimental transparency

- Four pairs contain one Worker-only and one Explicit-collaboration run each. Within every pair the conditions share the same runtime source-hash baseline and frozen Git head. The Pair 001 to later-pair change is confined to general SQLite connection lifecycle, WAL checkpoint, and stable artifact-capture handling; it does not change the public benchmark, initial prompt, or treatment semantics recorded in the runs.
- Explicit runs contain ten completed Reviewer sessions, distributed 2/2/4/2. Pair 003 has four sessions, not four demonstrated review–modify–review cycles; reviews 2 and 3 share the same Worker snapshot hash.
- The historical Explicit run-manifest aggregate reports zero Reviewer findings, while the authoritative formal records contain 20/20/14/15, totaling 69. The aggregate calculation bug is documented; frozen manifests remain unchanged.
- The blind set contains 13 frozen successful reviews across eight submissions: five double-pass and three single-pass. The 262 failed evaluator attempts and seven separate preflight failures are categorized from controller/process evidence. `submission_A/pass_02` had four unsuccessful/interrupted attempts; `submission_B/pass_02` and `submission_C/pass_01` were not run after the pre-reveal amendment. No omitted job was rerun after reveal.
- The exact post-hoc evaluator prompt and schema, freeze rule, taxonomy, and limitations are in the package. Both conditions have five normalized confirmed issue groups; the Explicit set retains a high-severity port-reference defect. These model-based findings do not establish ground truth, causal effects, or Reviewer superiority.
- A controller/operator context saw snippets from an existing review artifact during preparation. The recorded fresh ephemeral evaluator processes had separate workspaces and contexts, repository/history blocks, no blind mapping, and condition/run-ID leak checks. This is documented as a control-plane deviation, not as evidence of evaluator-session contamination.
- The selected Reviewer case study is a three-file activity example, not a full trajectory or ground truth. Submission A pass 01 has no evaluator-written scratch calculation files despite describing calculations.

## Reproduction checks

- Python: 3.10.11; `uv`: 0.10.2. The recorded full runtime/release suite, including the Docker integration test, completed with **52 passed** before this licensing-only update. After the update, the offline suite completed with **51 passed, 1 deselected** (the Docker integration); the separate release smoke completed with **5 passed**. These checks made **0 external model API calls** and started **0 research trajectories**.
- The durable runner `--help` completed successfully and confirms required `--run-id` and `--condition` arguments. No new trajectory, Reviewer run, blind review, or other LLM evaluation was started.
- Docker validation completed at `2026-09-28T05:45:20Z`: client **29.0.1**; Docker Desktop **4.52.0 (210994)** / Engine **29.0.1**; Linux/amd64 backend on WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, with `containerd` v2.1.5 and `runc` 1.3.3. `tests/ugs_synth_minimal/test_runtime.py::test_real_container_isolation_and_persistent_python_workspace` passed (**1 passed in 1.88s**) with the command documented in `REPRODUCIBILITY.md`. It exercised container Python, persistent project writes, read-only brief, host-path isolation, network isolation, and API-key non-forwarding.
- Commands are documented in the package `README.md` and `REPRODUCIBILITY.md`.

## Security and privacy

- Package scanner: **PASS**; credential-pattern hits 0, unexpected `.env` files 0, private or machine-local URL hits 0. `.env.example` contains only an empty API-key placeholder.
- Twelve absolute-path matches remain in the eight immutable `freeze.json` files. They refer only to the historical `.env` credential-source path: Worker credential fields in all eight files and Reviewer credential fields in the four Explicit files. The scan found no username, token, company, or internal-server path. This historical metadata disclosure is accepted for this review and is not a publication blocker; no frozen file was changed.
- The ten raw provider logs and 11,715 additional blind-batch result files (315,317,788 bytes) remain excluded. Failed evaluator workspaces, raw prompts/responses, complete run databases, hidden benchmark/reference solutions, and raw provider traces are not in the package. No LFS dependency is needed to inspect the package.

## Remaining publication blockers

None identified for the staged public research artifact.

No repository visibility change, GitHub Release, tag, DOI, external archive, or external upload was created. PUBLICATION READY refers to the staged research artifact's readiness for public release; it does not certify engineering designs or change `UGS_FORMAL_STATE=NOT READY`.
