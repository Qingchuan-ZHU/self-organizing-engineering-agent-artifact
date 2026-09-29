# Self-Organizing Engineering Agent — Research Artifact

This repository publishes the frozen research artifact for the
Self-Organizing Engineering Agent project and the manuscript:

**Agents for Long-Horizon Tasks: Persistent Workspaces and Autonomous Review**

## Manuscript analysis scope

The manuscript's primary behavioral analysis focuses on the four frozen
`explicit_collaboration` long-horizon trajectories. In those runs, the Worker
had access to an independent Reviewer and autonomously decided whether and when
to request review and how to respond to returned findings.

The frozen study also contains four matched `worker_only` runs. They are
retained as auxiliary paired baselines and as part of the complete experimental
record, but they are not the primary object of the manuscript's behavioral
analysis. The manuscript does not use the four pairs to claim a causal treatment
effect, statistical superiority, or that model-based review constitutes
engineering ground truth.

See [MANUSCRIPT_SCOPE.md](MANUSCRIPT_SCOPE.md) for the full interpretation
boundary.

## Frozen publication artifact

The canonical frozen package is under:

`artifact/`

It contains all eight frozen runs, eight final submissions, ten interactive
Worker–Reviewer sessions, blind post-hoc evaluation, reproducibility material,
and evidence limitations.

The files under `artifact/` are intentionally left unchanged by repository-level
manuscript-framing updates so that `artifact/RELEASE_MANIFEST.json` and its
integrity checks remain valid.

Publication-ready source baseline:

`04eb16d796b553e606abf82393cf130fbe7220d3`

UGS-SYNTH-D01 public-world SHA-256:

`af4260bc8e15bb44364038b6eeea9a6a6942677ae8e5e610971689415fd0880e`

Artifact release status:

**PUBLICATION READY**

See:

- `MANUSCRIPT_SCOPE.md`
- `artifact/README.md`
- `artifact/REPRODUCIBILITY.md`
- `artifact/LICENSE.md`
- `artifact/CITATION.cff`
- `RELEASE_READINESS_REPORT.md`

This repository is a research artifact, not a production engineering package.
Interactive Reviewer and blind-evaluator findings are model-generated evidence,
not formal engineering ground truth. `UGS_FORMAL_STATE=NOT READY`.
