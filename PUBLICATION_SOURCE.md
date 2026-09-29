# Publication source and manuscript framing

This repository was created as a clean artifact snapshot from a separately
maintained private development repository.

Publication artifact source commit:

`04eb16d796b553e606abf82393cf130fbe7220d3`

Source branch at publication preparation:

`codex/ugs-synth-d01`

Canonical artifact source path:

`release/public_package/`

Publication readiness report source path:

`release/RELEASE_READINESS_REPORT.md`

## Frozen package and manuscript framing

The canonical evidence package under `artifact/` remains a frozen publication
snapshot. It preserves all four paired replications, including four
`worker_only` runs and four `explicit_collaboration` runs, together with the
corresponding submissions, Reviewer records, blind post-hoc evaluation, and
integrity metadata.

Repository-level manuscript framing is documented separately in
[MANUSCRIPT_SCOPE.md](MANUSCRIPT_SCOPE.md). The manuscript's primary behavioral
analysis focuses on the four `explicit_collaboration` long-horizon trajectories;
the four matched `worker_only` runs are retained as auxiliary paired baselines.
This framing does not rewrite or remove the frozen evidence.

The private repository's Git history, private branches, raw provider
logs, failed evaluator workspaces, hidden benchmark/reference
solutions, runtime databases, local configuration, and other excluded
development material are not included in this repository.

## Current manuscript framing

The current title is **Persistent Workspaces and Autonomous Review for
Long-Horizon Agents: A Trajectory-Based Behavioral Study**. The primary
analysis is a trajectory-based behavioral study of Worker-controlled
review invocation and observable post-review responses across four
`explicit_collaboration` trajectories. The four `worker_only` runs serve
as an auxiliary paired baseline. See [MANUSCRIPT_SCOPE.md](MANUSCRIPT_SCOPE.md)
for the research questions, Pair 003 interpretation, and claim boundaries.

The files under `artifact/` are the frozen evidence package. Repository-level
framing documents state the current manuscript scope and do not change the
frozen records or results. This note does not add a complete account of study
results or amend the package's path-level license scope in
[`artifact/LICENSE.md`](artifact/LICENSE.md).
