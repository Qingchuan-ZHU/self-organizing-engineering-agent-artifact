# Blind-evaluator attempt and freeze notes

The source controller scheduled 16 jobs. The final frozen set contains 13 successful reviews covering all eight submissions: five submissions have two successful passes and three have one. The aggregate below was derived from controller progress plus failed-attempt process/manifest metadata; it omits raw prompts, responses, reasoning, credentials, machine paths, and failed workspaces. `failed_attempt_summary.json` records source-file hashes and a digest of the inspected attempt metadata.

## Failed and preflight attempt counts

The controller recorded 262 failed evaluator attempts and seven preflight failures. The categories for the 262 failed evaluator attempts are:

| Recorded process category | Count |
|---|---:|
| CLI did not produce a final response file | 255 |
| Broken-pipe exception | 2 |
| Operator interruption before completion | 2 |
| Process/controller finalization remained incomplete | 3 |
| **Failed evaluator attempts** | **262** |

The seven separate preflight failures were ACL boundary setup failures recorded before a successful evaluator launch. They are not included in the 262. These are execution and recording failures, not engineering findings about the submissions.

## Successful-review freeze rule

The recorded controller implementation freezes a review after the evaluator process exits successfully, its response parses and conforms to the required JSON schema, the frozen brief and submission input hashes are unchanged, the condition/run-ID string check finds no leak, and the controller's other boundary, validity, and manifest-integrity checks pass. The thirteen frozen process records have exit code zero, valid output, unchanged input trees, no detected condition/run-ID string, a fresh ephemeral session, and a passing out-of-scope read-denial probe.

The controller's recorded acceptance rule does not use whether findings are favorable or unfavorable, or whether they are numerous or sparse. This is a description of the implemented selection rule, not a guarantee of evaluator accuracy. The prompt explicitly allows zero findings, and the schema does not require a non-empty `findings` array.

## Scheduled jobs without a frozen successful review

The three scheduled jobs without a frozen successful review were:

- `submission_A/pass_02`: four unsuccessful/interrupted evaluator attempts occurred before closeout; no successful review was frozen.
- `submission_B/pass_02`: not run after the pre-reveal amendment.
- `submission_C/pass_01`: not run after the pre-reveal amendment.

The original amendment describes the remaining work as “second-pass jobs.” The schedule shows that one omitted job was specifically `submission_C/pass_01`, so this note names the actual jobs. The amendment decision followed full primary coverage and was made before reveal. No omitted job was rerun after reveal; all thirteen frozen review manifests predate the reveal, and the post-analysis integrity record reports that no frozen evaluator output changed after reveal.

The amendment stopped after the final primary-coverage review, `submission_A/pass_01`, following twelve previously frozen reviews. It cited evaluator execution and token cost. The amendment did not use the revealed condition or review result as a stopping criterion.

## What these counts do not mean

The 262 attempts are not 262 additional reviews and contain no additional accepted engineering findings. Failed workspaces and raw process output remain excluded. The frozen set is 13 successful process/integrity passes, not 16; no missing pass was completed or regenerated after reveal. The evaluator is a post-hoc model-based reviewer, not a formal engineering oracle.
