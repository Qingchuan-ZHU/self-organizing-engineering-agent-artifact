# Blind post-hoc evaluation summary

## 1. Evaluation dataset

The primary unit is one final submission: 8 submissions, with Worker-only N=4 and Explicit collaboration N=4. The evaluator froze 13 successful blind review passes before reveal. Five submissions have two passes and three have one. There are 54 original finding records; conservative normalization yields 38 submission-level issue groups. The blind review pass is not an independent engineering sample.

The reviewer-behavior trajectory results are kept separate from final-artifact findings. Reviewer findings produced during the Worker trajectory are not included in the blind finding counts.

## 2. Pre-reveal integrity

The integrity check passed before blind_mapping.json was read:

- 13/13 frozen review manifests matched every listed file hash and each record was a successful frozen review.
- All 8 blind package brief and submission trees matched the existing package-integrity baseline.
- All 8 source final project snapshots matched their run artifact hash manifests and matched the blind submission packages as an unordered set.
- All 8 source public-brief snapshots matched the canonical 22-file public brief; all blind package briefs had the same tree hash.
- Coverage was 8/8 submissions, with five double-pass and three single-pass submissions.

The pre-reveal state is recorded in pre_reveal_integrity.json. Local HEAD and the last-known remote-tracking ref were both fe9f6985701c7946ee70e70f71b6637e967339ed. A live GitHub HEAD query failed because github.com:443 was unreachable, so the remote SHA was not freshly verified at reveal.

## 3. Reveal procedure

After the PASS record was written, the mapping file was read and hashed. The revealed alias-to-run mapping, condition, pair, and frozen pass count are recorded in revealed_mapping.json and reveal_record.md.

All blind evaluator outputs were frozen before experimental condition labels were revealed.

The original schedule was 8 × 2 = 16 reviews. The researcher stopped after complete submission coverage at 13 reviews; the protocol amendment says this decision was made before reveal and cites evaluator execution and token cost. The three unrun second passes are incomplete by design, not evaluator failures.

## 4. Finding normalization

A one-pass submission carries its findings directly. For a double-pass submission, two findings were grouped only when they clearly described the same public requirement, component, failure mechanism, or numerical inconsistency. Uncertain pairs remain separate.

The normalized file retains each original finding ID and its exact status, severity, confidence, and source review hash. Mixed pass labels are preserved. Status-specific counts can overlap when passes disagree. For submission severity counts, each issue uses the most severe severity assigned by a pass that called it confirmed_violation.

Submission_H/pass_02 finding F-005 contains two distinct liquid-report checks: the DRN-S capacity statement and reported scenario liquid totals. It is referenced in two normalized issue groups so these checks are not merged; the frozen source finding is unchanged.

## 5. Submission-level results

| Pair | Alias | Condition | Passes | Normalized issues | Confirmed high / medium / low | Unsupported | Suspected | Semantics gaps | Observations | Completion |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 001 | submission_E | Worker-only | 2 | 6 | 0 / 3 / 0 | 2 | 0 | 1 | 0 | agent_completed_without_evaluation |
| 001 | submission_A | Explicit collaboration | 1 | 3 | 0 / 1 / 0 | 1 | 0 | 1 | 0 | agent_completed_without_evaluation |
| 002 | submission_B | Worker-only | 1 | 5 | 0 / 0 / 1 | 1 | 0 | 2 | 1 | agent_completed_without_evaluation |
| 002 | submission_D | Explicit collaboration | 2 | 3 | 0 / 1 / 0 | 1 | 1 | 2 | 0 | agent_completed_without_evaluation |
| 003 | submission_F | Worker-only | 2 | 5 | 0 / 0 / 0 | 2 | 0 | 2 | 1 | terminated_without_finish_project |
| 003 | submission_H | Explicit collaboration | 2 | 6 | 0 / 1 / 1 | 3 | 0 | 1 | 0 | agent_completed_without_evaluation |
| 004 | submission_C | Worker-only | 1 | 6 | 0 / 0 / 1 | 3 | 0 | 2 | 0 | agent_completed_without_evaluation |
| 004 | submission_G | Explicit collaboration | 2 | 4 | 1 / 0 / 0 | 2 | 1 | 1 | 0 | agent_completed_without_evaluation |

Confirmed counts include a normalized issue if at least one contributing pass labelled it confirmed_violation. In submission_D, the HDR sizing issue was confirmed by pass 01 and marked suspected_risk by pass 02. Submission_G’s drain endpoint issue was confirmed by both passes, with different severity labels (high and medium).

Worker-only submission 003 ended as terminated_without_finish_project. This completion behavior is reported separately and is not automatically treated as an engineering failure; its frozen final workspace received blind review.

## 6. Pair-level comparison

| Pair | Worker-only | Explicit collaboration | Descriptive pattern |
|---:|---|---|---|
| 001 | submission_E: 3 confirmed issues | submission_A: 1 confirmed issue | Higher count in Worker-only; the findings differ, although both include an LCC alternative. |
| 002 | submission_B: 1 low confirmed issue | submission_D: 1 medium confirmed issue | Equal count; submission_D’s HDR issue has a confirmed/suspected label disagreement between passes. |
| 003 | submission_F: 0 confirmed issues | submission_H: 2 confirmed issues | Higher count in Explicit collaboration. |
| 004 | submission_C: 1 low confirmed issue | submission_G: 1 high confirmed issue | Equal count; the findings concern different issues (flow precision versus an undeclared drain port). |

Across the four pairs, Worker-only has the larger confirmed count in one pair, Explicit collaboration in one pair, and the counts tie in two. This is a mixed descriptive pattern, not a win/loss score.

## 7. Condition-level descriptive comparison

| Metric | Worker-only (N=4) | Explicit collaboration (N=4) |
|---|---:|---:|
| Submissions with at least one confirmed violation | 3/4 | 4/4 |
| Normalized confirmed issues | 5 | 5 |
| High confirmed issues | 0 | 1 |
| Medium confirmed issues | 3 | 3 |
| Low confirmed issues | 2 | 1 |
| Unsupported-claim issue labels | 8 | 7 |
| Suspected-risk issue labels | 0 | 2 |
| Semantics-gap issue labels | 7 | 5 |
| Observation issue labels | 2 | 0 |
| Submissions with an issue detected by both passes | 2/4 (2/2 eligible) | 3/4 (3/3 eligible) |

The conditions each have five normalized confirmed issues. Explicit collaboration has one more submission with at least one such issue, while the paired direction is mixed. Taxonomy counts may overlap for pass-disputed issues. Semantics gaps are not included in engineering-defect counts. No total quality score or significance test was used.

## 8. Double-pass evaluator reproducibility

In the five double-pass submissions, 17 issue groups were detected in both passes, 2 were detected only in pass 01, and 5 only in pass 02. Status labels agreed on 14/17 shared issues; severity labels agreed on 16/17. Post-hoc primary categories agreed on all 17 matched groups, but category coding occurred during thematic matching and is not an independent reliability statistic.

Two issues were labelled confirmed_violation by both passes: the undeclared drain endpoint in submission_G and the lower-cost REG/MTR alternatives in submission_H. Submission_D’s HDR sizing issue was confirmed in one pass and suspected in the other. The liquid-density semantics gap appeared in both passes for all five double-pass submissions.

These results describe repeated finding behavior in fresh contexts. They are not formal inter-rater reliability statistics. The complete per-submission breakdown is in evaluator_reproducibility.md.

## 9. Engineering issue categories

Counts below are normalized submission-level issue groups by one primary category; secondary categories are retained in normalized_findings.json.

| Primary category | Issue groups | Examples |
|---|---:|---|
| Benchmark semantics | 14 | Missing liquid density; unmodelled isolation semantics; one road end-cap interpretation issue. |
| LCC objective / suboptimality | 6 | Five local lower-cost catalog alternatives, plus one observation that reported LCC does not prove a global optimum. |
| N-1 reliability | 6 | Unsupported claims based on aggregate capacity or representative cases instead of all required unit-out cases. |
| Internal consistency | 5 | Report values that conflict with machine-readable quantities or catalog values. |
| Operating scenarios | 2 | Rounded flow allocations exceed the published tolerance. |
| Deliverable / reconstructability | 2 | Reproduction commands and packaged paths disagree. |
| Pipeline geometry | 1 | PGRID-INJ crosses a meter footprint. |
| Geometry / layout / roads | 1 | R-MAIN swept end extends outside the site. |
| Topology / ports | 1 | P39-P41 use an undeclared drain endpoint. |

The LCC findings identify local alternatives and do not establish a global optimum. Higher LCC alone was not treated as a violation.

## 10. Benchmark semantics gaps

The liquid-drain velocity check lacks a public liquid-density basis: all 8 submissions and all 13 frozen review passes identify this ambiguity. It is one recurring benchmark ambiguity represented in 8 submission-level groups, not 8 engineering failures.

Unmodelled isolation semantics appear in five submissions and eight review passes. The reviewers disagree in how they classify this concern; it remains a possible benchmark-level ambiguity with all source labels retained.

Road endpoint treatment appears in submission_B as a semantics gap and submission_E as a confirmed site-boundary violation for its specific route. The analyses remain separate because the source judgments differ.

## 11. Limitations

- Four submissions per condition support descriptive counts and pair patterns only.
- Three submissions have one pass. The repeat subset ended at complete primary coverage under the pre-reveal amendment.
- Codex blind findings are model-based evidence, not formal engineering ground truth. Hydraulic, geometry, outage, and LCC checks were not exhaustive in every review.
- Submission_A/pass_01 records five independent calculations but no corresponding scratch-file artifacts. The calculations are reported in the frozen evaluator output but lack corresponding scratch-file artifacts.
- Some passes disagree on status or severity. Those differences are preserved in the normalized data.
- Runtime cost values are estimates only; possible duplicate provider execution cost is excluded.
- Worker-only submission 003 did not call finish_project; this is kept as completion behavior separate from final-artifact findings.

## 12. Interpretation boundary

Trajectory evidence supports a separate behavioral result: all four explicit-collaboration Workers voluntarily used the Reviewer, completed 10 Reviewer sessions in total, and each run contains review completion, subsequent workspace changes, and a later review request.

The final-artifact comparison is descriptive: 3/4 Worker-only versus 4/4 Explicit-collaboration submissions had at least one confirmed issue, while both conditions had five normalized confirmed issues. Pair patterns are mixed. The data do not support the causal statement that the Reviewer produced better engineering quality.

UGS_FORMAL_STATE = NOT READY. Codex blind evaluation is not formal engineering ground truth.

No frozen evaluator output was changed after reveal.
