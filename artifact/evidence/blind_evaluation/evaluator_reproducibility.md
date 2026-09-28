# Evaluator descriptive reproducibility

The repeated-pass subset contains five submissions, each reviewed in two frozen passes. Findings are grouped only when both records clearly describe the same underlying issue; unmatched issues remain separate.

| Alias | Pair | Shared issue groups | Pass 01 only | Pass 02 only | Status agreement on shared | Severity agreement on shared | Primary-category agreement | Confirmed in both passes | Semantics gap in both passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| submission_D | 002 | 3 | 0 | 0 | 1/3 | 3/3 | 3/3 | 0 | 1 |
| submission_E | 001 | 3 | 1 | 2 | 3/3 | 3/3 | 3/3 | 0 | 1 |
| submission_F | 003 | 4 | 1 | 0 | 4/4 | 4/4 | 4/4 | 0 | 2 |
| submission_G | 004 | 3 | 0 | 1 | 2/3 | 2/3 | 3/3 | 1 | 1 |
| submission_H | 003 | 4 | 0 | 2 | 4/4 | 4/4 | 4/4 | 1 | 1 |

Across the five submissions, 17 issue groups were detected by both passes, 2 only by pass 01, and 5 only by pass 02. On the 17 matched groups, status labels agreed for 14/17; severity labels agreed for 16/17. Primary engineering categories agreed for 17/17 after post-hoc category coding during the same thematic matching; this is descriptive and not an independent reliability estimate.

Two underlying issues were labelled confirmed_violation by both passes: the undeclared drain outfall endpoint in submission_G and the lower-cost REG/MTR substitutions in submission_H. In submission_D, the HDR sizing issue was labelled confirmed_violation in pass 01 and suspected_risk in pass 02. The submission_G outfall issue was confirmed by both passes, but severity differed (high vs medium).

The missing liquid-density basis was independently recorded as semantics_gap in both passes for all five double-pass submissions, and in all 13 frozen review passes across the full dataset. In addition, submission_F had a valve-isolation issue labelled semantics_gap in both passes, for six shared semantics-gap issue groups across the five submissions. These are benchmark ambiguity signals, not engineering-defect counts.

Valve/isolation semantics were independently noted in both passes for submissions D, F, and G. D and G used different taxonomy labels between passes; those differences remain in normalized_findings.json.

The repeated-pass subset is incomplete by design after the pre-reveal amendment stopped evaluation at complete submission coverage. These results describe fresh-context finding reproducibility; they are not formal inter-rater reliability statistics.
