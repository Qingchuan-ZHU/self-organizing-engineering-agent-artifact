# Paired replication record

The released batch contains four pairs. Each pair has one `worker_only` run and one `explicit_collaboration` run; each pair shares a public-world hash, initial Worker task-prompt hash, and runtime source-hash map. Both condition runs within a pair also record the same frozen Git HEAD. The fixed four-pair design is evidenced by the frozen run records; the package does not contain an a priori power calculation or a more specific sample-size rationale.

## Frozen Git HEAD by pair

| Pair | Worker-only and Explicit-collaboration Git HEAD |
|---|---|
| 001 | `73877e3f29b0baa77453cc216c8b953402c6767d` |
| 002 | `66e29012f7d01468a2dad81c196c4bf5d6d95eca` |
| 003 | `f05652000a84a73ed93a43bfcc71397d8dbb1537` |
| 004 | `51701fdd72fd5529953b60b50d51ac2552fb9176` |

## Inputs and treatment fingerprints

All eight frozen configurations record public-world SHA-256 `af4260bc8e15bb44364038b6eeea9a6a6942677ae8e5e610971689415fd0880e` and Worker initial-task-prompt SHA-256 `93af745fa3f83615686d2efdb68c04a487769f2f023d802a0b70c2b62668adf1`.

| Property | Worker-only runs | Explicit-collaboration runs |
|---|---|---|
| Worker system-prompt hash | Same in all four: `6522afdc177054a3cd1296e35b95d42baa28c6fad888869372ca830de1ba0a2d` | Same in all four: `746bfc7dd86d92c3c00b28e900e1dd6eebaf76756e3a6274edbc4e7710e30ac4` |
| Worker tool-definition hash | Same in all four: `d580a727b6d00b227f4b543b5c2c15357ff80faa2d31493d6903a2f1867d348b` | Same in all four: `d04cc070254fed3b94d900d45dcef7a4219142eaf17f10b64111e328ff2efc83` |
| Reviewer capability statement | Absent | Same statement in all four; Worker chooses whether and when to call `submit_for_review` |
| Reviewer initial-prompt hash | Absent | Same in all four: `baf887e60de09cba2b606735503e5e2d9d1b687b04b92d13ff656e04d693a677` |
| Reviewer system-prompt hash | Absent | Same in all four: `a9053ab3cbc1dcff4eafc417ed7df0a940cbaa868014409aae1ffcd647d61c31` |
| Reviewer tool-definition hash | Absent | Same in all four: `e5782628fef7a1eb4f5887bb1024c9b83ab6ff313edd2e3390237a56d14ee497` |
| Model and limits | `deepseek-flash`; Worker up to 600 responses, 16,384 output tokens per response | Same Worker model/limits; Reviewer also uses `deepseek-flash`, up to 160 responses per review and 2,400 total |
| DBOS | 3.0.0 | 3.0.0 |

The condition-specific prompt and tool hashes are expected treatment differences: Explicit collaboration adds the voluntary review capability and its Reviewer context. Those definitions are constant across all four runs within their respective condition. The recorded public-world hash, initial task prompt, condition semantics, model, response limits, DBOS version, and condition-specific prompt/tool hashes show no change in treatment definitions across the four pairs.

## Runtime implementation boundary after Pair 001

The runtime source-hash maps in the frozen configurations were compared directly. Pair 001 and each later pair differ in only two included runtime files. Pair 002, Pair 003, and Pair 004 have identical runtime source-hash maps. Within every pair, the Worker-only and Explicit-collaboration runs have identical runtime source-hash maps.

| Runtime file | Pair 001 compared with Pair 002–004 | Recorded change |
|---|---|---|
| `src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_store.py` | Different | SQLite connections were wrapped in a context manager and closed in `finally`. |
| `src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_replication.py` | Different | A completed DBOS SQLite database is explicitly WAL-checkpointed and closed before the final manifest and artifact hashes are written. The artifact-hash file filter was also reformatted without changing its condition. |

The code diff is limited to SQLite connection lifecycle and stable checkpoint/hash capture. It is a general durability and evidence-capture repair. Hashes for the public benchmark, initial task prompt, Worker/Reviewer prompts and tools, model limits, DBOS version, and condition definitions show that it did not alter the Agent-facing treatment. The package retains the Pair 001 versions in `experiments/runtime_variants/pair_001/`; `experiments/manifests/runtime_source_hash_checks.json` records the frozen source-hash checks.

## Interactive Reviewer sessions and snapshots

The Explicit-collaboration runs contain 10 completed review sessions: Pair 001 has 2, Pair 002 has 2, Pair 003 has 4, and Pair 004 has 2. A completed session is not necessarily a review–modify–review cycle. In Pair 003, `review_0002` and `review_0003` have the same Worker snapshot SHA-256 (`e3c14acc5e726b866e8989fe6106cc391960f97851548f303248265a7bcd25a6`). The Worker requested another review without a changed submitted project snapshot between those two requests. This is a workspace-state observation only.

[`../../analysis/rebuilt_tables/review_session_summary.csv`](../../analysis/rebuilt_tables/review_session_summary.csv) lists the request order, snapshot hash, whether it matches the preceding snapshot, formal finding count, and source termination reason for each review. The frozen public summary does not record a reliable Worker response index or turn for every request, so none is inferred. The formal review JSON and snapshot manifests remain the underlying evidence.

Pair 003 Worker-only ended as `terminated_without_finish_project`. Its artifacts and terminal status are retained without relabeling it as a successful completion. All runs retain `UGS_FORMAL_STATE=NOT READY`; neither Worker-authored checks nor Reviewer findings are formal engineering ground truth.
