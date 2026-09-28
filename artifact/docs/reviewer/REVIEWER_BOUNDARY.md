# Reviewer boundary and evidence

The interactive Reviewer is a persistent collaborator with an independent model context and its own writable `review/` area. A review request supplies the public brief and one frozen Worker project snapshot, optionally with a Worker-authored note. The Reviewer can inspect the snapshot and create checks in its own workspace; the Worker project remains outside its writable mount. Structured findings return after `finish_review`.

The Worker controls review timing and later edits. The ten completed review records are not ten distinct edit cycles: Pair 003 reviews 2 and 3 use the same snapshot SHA-256. See `../experiments/PAIRED_REPLICATIONS.md` and `../../evidence/reviewer_trajectories/review_session_summary.csv`.

The public trajectory index records relative workspace paths, hashes, turns, and review numbers while omitting tool arguments/results, Worker notes, model messages, and hidden reasoning. The selected files in `../../evidence/reviewer_workspace_case_study/` provide a small example of independent Reviewer workspace activity, not a complete trajectory or ground truth.
