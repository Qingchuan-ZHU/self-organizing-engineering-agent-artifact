# Reveal record

- Reveal time (UTC): 2026-09-28T02:41:23Z
- Git HEAD at reveal: fe9f6985701c7946ee70e70f71b6637e967339ed
- Mapping file SHA-256: 429e3479f0697a30300f5c2a0d995950051da8bc28bf0ebc1610c32b7e1ba985
- Pre-reveal integrity file SHA-256: 7fdcb748fb422e804e902608b52d2edceec7dcf54483fcc1144a5112413a452a
- Remote HEAD: last-known tracking SHA fe9f6985701c7946ee70e70f71b6637e967339ed; live remote verification was unavailable before reveal.

All blind evaluator outputs were frozen before experimental condition labels were revealed.

## Revealed assignments

| Pair | Alias | Original run | Condition | Frozen passes |
|---|---|---|---|---:|
| 001 | submission_A | ugs_synth_explicit_collaboration_replication_001 | explicit_collaboration | 1 |
| 001 | submission_E | ugs_synth_worker_only_replication_001 | worker_only | 2 |
| 002 | submission_D | ugs_synth_explicit_collaboration_replication_002 | explicit_collaboration | 2 |
| 002 | submission_B | ugs_synth_worker_only_replication_002 | worker_only | 1 |
| 003 | submission_H | ugs_synth_explicit_collaboration_replication_003 | explicit_collaboration | 2 |
| 003 | submission_F | ugs_synth_worker_only_replication_003 | worker_only | 2 |
| 004 | submission_G | ugs_synth_explicit_collaboration_replication_004 | explicit_collaboration | 2 |
| 004 | submission_C | ugs_synth_worker_only_replication_004 | worker_only | 1 |

## Protocol amendment

The original schedule was 8 submissions × 2 passes = 16 reviews. The final dataset has 13 frozen reviews, covering all 8 submissions; 5 have two passes and 3 have one pass.

The decision to stop after complete submission coverage was made before the condition mapping was revealed. The amendment cites evaluator execution and token cost; the remaining second-pass jobs were not run.

No mapping data was read before the pre-reveal integrity check passed. The frozen results tree remains the immutable source for all post-hoc finding groups.
