# AI-Generated and AI-Assisted Content Disclosure

Review date: 2026-09-28. This disclosure covers the staged public package and the release-preparation edits recorded for this review. It classifies the frozen evidence without changing it.

## Scope

The package contains experimental outputs from autonomous Worker and Reviewer roles, model-based blind post-hoc reviews, deterministic summaries, analyst-coded findings, source code, a synthetic engineering brief, and release documentation. The inventory at [AI_CONTENT_INVENTORY.csv](AI_CONTENT_INVENTORY.csv) classifies these materials by artifact group.

The synthetic brief defines benchmark assumptions. It is not vendor data, production criteria, or engineering ground truth. This disclosure does not claim that every source-code or benchmark file was or was not drafted with AI; it makes no attribution where the available provenance does not establish one.

## Experimental roles

### Worker

Eight frozen final submissions contain 143 files across the Worker project snapshots. The frozen configurations identify DeepSeek as the provider and deepseek-flash as the configured/effective model. The runtime uses DeepSeek's API through an OpenAI-compatible request protocol; this protocol compatibility does not make the provider OpenAI. These are outputs produced by autonomous experimental agents using a DeepSeek model. They are not provider-issued engineering conclusions, human-certified designs, or verified safe-to-build plans.

### Interactive Reviewer

The four Explicit-collaboration runs used the same DeepSeek provider and deepseek-flash model as their Workers; the Worker-only runs had no Reviewer. Ten frozen formal_review.json records are the experimental independent-review artifacts. Three selected Reviewer-created scripts are included as a limited workspace case study. Findings, calculations, and scripts are AI-generated review evidence, not formally verified defects or engineering ground truth. The Worker controlled whether to act on findings or request another review.

### Blind post-hoc evaluator

The package contains thirteen frozen successful review.json outputs. Frozen controller and evaluation metadata records OpenAI Codex CLI execution with gpt-5.5 as the requested/reported model value and xhigh reasoning. The frozen evidence does not independently attest the provider-side model identity or preserve whether Codex was authenticated through an individual ChatGPT account, an API route, or a business workspace. Exact underlying model identifier is not established by the frozen evidence. The reports are model-based post-hoc evaluation evidence, not formal engineering ground truth. The associated thirteen review.md files are deterministic renderings of the JSON outputs and add no separate model judgment.

## Content classification

| Artifact class | Provider or tool | Model identity | Experimental role | Ground-truth status |
|---|---|---|---|---|
| Eight final Worker snapshots, 143 files | DeepSeek API | deepseek-flash, per frozen records | Autonomous engineering-agent work product | Not ground truth; not human-certified |
| Ten formal Reviewer records and three selected Reviewer scripts | DeepSeek API | deepseek-flash, per frozen records | Interactive independent-review evidence | Advisory model findings; not verified defects or ground truth |
| Thirteen blind review JSON files | OpenAI Codex CLI | gpt-5.5 is the frozen requested/reported value; exact underlying model identity is not independently established | Blind post-hoc evaluation evidence | Not ground truth |
| Thirteen rendered blind review documents | Deterministic renderer | Not applicable | Readable views of the frozen JSON reviews | No additional judgment |
| Normalized findings | Analyst coding | Not applicable | Post-hoc thematic matching and coding of review findings | Human-coded categories; not ground truth |
| Four rebuilt CSV/JSON tables | Deterministic analysis script | Not applicable | Derived counts and comparisons from released records and normalized labels | No AI judgment; inherits source-evidence limitations |

## Deterministic derived analysis

The released table builder deterministically rebuilds submission_summary.csv, pair_comparison.csv, review_session_summary.csv, and summary_counts.json from the released records and already-normalized labels. The script makes no model call and does not relabel findings. The normalized_findings.json file is a separate post-hoc analyst coding product: its thematic groupings and labels are not AI-generated judgments and are not independent ground truth.

Sanitized trajectory events and review-session summaries are runtime/process records with content bodies omitted or summarized. Their recorded events do not certify the engineering substance of the model-generated artifacts.

## Release-preparation documentation

This disclosure, the inventory, the terms review, and the related documentation edits for this review were drafted or edited with automated coding-assistant assistance. Their preparation is release work, not part of the frozen experimental evidence. No claim of wholly human authorship is made for these edits; the repository owner directed this release-governance work and remains responsible for the package. The authorship of earlier documentation is not inferred from this review.

## Provider terms reviewed

Provider terms and their applicability limits are recorded in [PROVIDER_TERMS_REVIEW.md](PROVIDER_TERMS_REVIEW.md). This package makes factual provider/tool identifications and uses no provider logo, co-branding, endorsement, or partnership claim. The release-governance decision accepts this factual attribution for the staged artifact. The historical DeepSeek mark wording and unpreserved Codex authentication route remain documented caveats, not publication blockers or claims of legal clearance.

## Accuracy and validation limitations

AI outputs may contain errors, omissions, unsupported claims, or code and calculations that do not work outside the recorded environment. The released evidence preserves what the experimental roles produced; its inclusion does not certify engineering adequacy, safety, code quality, compliance, or originality. The blind evaluator's findings are post-hoc model assessments and must not be read as formal ground truth. The package's documented checks verify specified files, schemas, hashes, and deterministic transformations; they do not prove every engineering claim.

## Publication and labeling approach

Keep this disclosure and the group-level inventory with the package. When individual evidence files are copied elsewhere, preserve the relevant role, provider, model-identity qualification, and ground-truth status from the inventory. Do not describe any Worker output as a provider's official conclusion, any Reviewer output as a formally verified defect, or a blind finding as ground truth. The files remain byte-for-byte frozen; labeling is supplied at package level rather than by editing each frozen artifact.

## Rights and licensing boundary

Provider assignment of any rights they may hold in output is contract-specific and subject to applicable law. It does not establish universal copyrightability or authorship, clear third-party content, or select a license for this repository. The package uses path-level terms recorded in [LICENSE.md](LICENSE.md); frozen evidence is offered under CC BY 4.0 only to the extent applicable rights exist and are held by the repository owner.

## Terms-version caveat

Provider terms are time-dependent. This review records the terms available on the stated review date and is not a guarantee that future terms will remain unchanged. The review is a release-governance record, not legal advice or a guarantee regarding copyrightability, third-party rights, or future changes to provider terms.
