# Workspace and Reviewer architecture

## Worker workspace

The runtime mounts `brief/` read-only and `project/` read-write for the Worker. The Worker can create its own files, scripts, models, calculations, reports, validation logic, and intermediate artifacts. The public brief defines the engineering world; the runtime does not prescribe a design workflow or a project-state schema.

The five baseline Worker tools are `list_files`, `read_file`, `write_file`, `execute_python`, and `finish_project`. In the Explicit-collaboration condition, the Worker also receives `submit_for_review`. The Worker chooses whether and when to request a review and may supply a short request note.

## Reviewer workspace

Each request captures a frozen project snapshot and starts a review session in the independent Reviewer context. The Reviewer can read the public brief and the snapshot through read-only mounts. Its separate persistent `review/` workspace is writable across requests. The Reviewer tools are `list_files`, `read_file`, `write_file`, `execute_python`, and `finish_review`.

The Reviewer cannot write the Worker project. It does not receive Worker conversation history or hidden reasoning. A request may include only the Worker-authored note and the frozen snapshot. When the Reviewer completes a review, structured findings return to the Worker, which decides what to inspect, accept, reject, change, and whether to request another review.

The frozen explicit-collaboration records show no context reset between review requests. The ten formal records, the ten snapshot manifests, and the derived order/snapshot table are under `evidence/reviewer_records/` and `evidence/reviewer_trajectories/`. Three selected Reviewer-created scripts are under `evidence/reviewer_workspace_case_study/`; they illustrate activity but are not a complete workspace or ground truth.

The runtime and boundary tests are under `src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/` and `tests/ugs_synth_interleaved_review/`.
