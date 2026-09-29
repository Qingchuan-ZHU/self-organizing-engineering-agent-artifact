# Persistent Workspaces and Autonomous Review for Long-Horizon Agents: A Trajectory-Based Behavioral Study

**中文题目：** 面向长期任务智能体的持久工作区与自主审查：一项轨迹行为研究

This repository contains a **frozen research artifact** for a trajectory-based
behavioral study using the synthetic UGS-SYNTH-D01 long-horizon task. It
examines how an acting Worker invokes an independent Reviewer and how the
Worker responds to review results over an evolving, persistent project
workspace.

## Study at a glance

- The primary behavioral analysis covers four `explicit_collaboration`
  trajectories. The Worker controls whether and when to request a review.
- The analysis focuses on review-invocation timing and observable post-review
  workspace and trajectory responses.
- Four `worker_only` runs are an auxiliary paired baseline for descriptive
  context.
- Pair 003 includes a same-state review resubmission that served as
  review-output recovery. It is not treated as an independent repeated-review
  experiment or direct evidence of Reviewer nondeterminism.
- The study does not claim a Reviewer causal effect, statistical superiority,
  that Reviewer use reduces all final violations, or that model outputs are
  engineering ground truth.

## What is included

[`artifact/`](artifact/README.md) contains the frozen benchmark, eight final
Worker submissions, ten formal Reviewer session records, thirteen frozen blind
post-hoc reviews, provenance and limitations, and deterministic analysis tools.
The four Explicit-collaboration runs contain 2, 2, 4, and 2 formal Reviewer
sessions. The frozen run-manifest aggregate bug and the authoritative
finding-record totals (20, 20, 14, and 15) are documented without changing the
original records.

The `artifact/` directory is frozen evidence. This repository-level manuscript
framing does not revise its evidence, labels, or results.
`UGS_FORMAL_STATE=NOT READY` remains in effect; this artifact is not a
production engineering package.

## Start here

- [Manuscript scope and research questions](MANUSCRIPT_SCOPE.md)
- [Artifact overview](artifact/README.md)
- [Reproducibility instructions](artifact/REPRODUCIBILITY.md)
- [Known issues and evidence limits](artifact/KNOWN_ISSUES.md)
- [Release-readiness report](RELEASE_READINESS_REPORT.md)
- [Publication source and provenance](PUBLICATION_SOURCE.md)
- [Path-level license scope](artifact/LICENSE.md)
- [Artifact citation metadata](artifact/CITATION.cff); publication citation
  details remain pending.

For integrity and privacy checks, follow the commands in
[`artifact/REPRODUCIBILITY.md`](artifact/REPRODUCIBILITY.md) from the
`artifact/` directory. These checks use the frozen package and do not require
a model API call.
