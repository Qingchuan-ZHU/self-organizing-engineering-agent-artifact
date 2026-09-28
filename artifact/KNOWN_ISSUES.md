# Known issues and evidence limits

This note preserves adverse and incomplete evidence. It does not revise frozen records, finding labels, or study results.

## Historical Reviewer finding-count discrepancy

Each of the four frozen Explicit-collaboration `run_manifest.json` records reports `reviewer.findings_count` as `0`. Recounting the ten published `formal_review.json` records gives:

| Pair | Finding records in formal reviews |
|---|---:|
| 001 | 20 |
| 002 | 20 |
| 003 | 14 |
| 004 | 15 |
| **Total** | **69** |

The original run manifests are preserved unchanged. The authoritative finding records are the per-session `formal_review.json` files; the deterministic release tables count those records directly. The zero is an aggregate-metadata bug, not evidence that the reviews or findings are missing.

**Confirmed code cause:** at all four frozen run heads, the runtime computed the aggregate from `reviewer/reviews.jsonl` session rows using `len(row.get("findings", []))`. Those session rows record request, snapshot, termination, and token metadata but do not contain a `findings` field, so the default empty list yields zero. This describes the recorded implementation; no run manifest was edited to repair it.

## Review sessions are not all review–modify–review cycles

The ten completed sessions are distributed 2, 2, 4, and 2 across Explicit pairs 001–004. Pair 003 has four completed sessions, but `review_0002` and `review_0003` share the same complete snapshot SHA-256. The Worker requested another review without first changing the submitted project snapshot. The compact table is `analysis/rebuilt_tables/review_session_summary.csv`; the review JSON and snapshot manifests remain authoritative.

## Blind-evaluation limits

- Both conditions have five normalized confirmed issue groups in the released comparison. The available evidence does not show that Reviewer use reduced the overall confirmed-violation count.
- An Explicit-collaboration submission retains a high-severity port-reference defect. Unsupported N-1 evidence appears in 4/4 Worker-only and 1/4 Explicit-collaboration submissions. These are descriptive model-review results and do not establish a causal Reviewer effect or statistical superiority.
- Repeated passes were not symmetric: five submissions have two frozen passes and three have one. On matched findings, some status and severity labels differ between passes. The repeated-pass subset is not a formal inter-rater reliability estimate.
- There were 262 failed evaluator attempts and seven preflight failures. The failure categories, successful-review freeze rule, and uncompleted scheduled jobs are documented in `evidence/blind_evaluation/FAILED_ATTEMPT_NOTES.md`. Raw failed workspaces are excluded.
- In `submission_A/pass_01`, the frozen response describes independent calculations but lists no evaluator-written scratch calculation files. Its calculation details therefore cannot be re-executed from a published evaluator scratch artifact.
- During controller-side preparation, an operator/controller context was exposed to snippets from an existing review artifact. Fresh ephemeral evaluator processes used separate contexts and workspaces, with recorded repository/history access blocks and condition/run-ID leak checks. This is recorded as a control-plane deviation; it is not evidence that the fresh evaluator sessions themselves were contaminated.
- Blind results were frozen before reveal. The post-analysis integrity record reports that no frozen evaluator output changed after the mapping was revealed.

## Runtime and completion boundaries

The four pairs share a runtime baseline within each pair, but Pair 001 used two runtime files that were repaired before Pair 002. The exact file-level boundary and hash comparison are in `docs/experiments/PAIRED_REPLICATIONS.md`. Pair 003 Worker-only ended as `terminated_without_finish_project`; its output and status remain part of the released evidence.

All Reviewer findings and Codex post-hoc blind reviews are model-based evidence, not formal engineering ground truth. `UGS_FORMAL_STATE=NOT READY` remains in effect.

## Rights and historical metadata

Provider terms have been reviewed as of 2026-09-28. Historical findings about DeepSeek mark wording and the unrecorded Codex authentication route are retained in `PROVIDER_TERMS_REVIEW.md`. The release-governance decision accepts factual, non-promotional provider/tool attribution and records both matters as closed and not publication blockers for this staged artifact. Path-based licenses are recorded in `LICENSE.md`; frozen-evidence rights remain limited to rights the repository owner actually holds.

The twelve historical credential-source path references in the frozen configurations were reviewed and accepted as historical metadata disclosure; they are not a publication blocker. The records remain unmodified, and any additional path finding requires review. A bounded screen of published model outputs found no email patterns, common vendor-name matches, or long quotation candidates; this is not an exhaustive third-party rights or similarity review.
