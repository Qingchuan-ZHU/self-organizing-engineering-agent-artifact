# Manuscript scope

## Titles

- **English:** Persistent Workspaces and Autonomous Review for Long-Horizon Agents: A Trajectory-Based Behavioral Study
- **中文：** 面向长期任务智能体的持久工作区与自主审查：一项轨迹行为研究

## Study framing and research questions

This is a **trajectory-based behavioral study** of autonomous review
invocation and subsequent Worker behavior during a long-horizon task. It
examines an evolving persistent project workspace in which the Worker decides
whether and when to invoke an independent Reviewer, then controls its own
response to the returned review.

**RQ1.** In long-horizon tasks without fixed review checkpoints, when and how
does the acting agent autonomously invoke independent review?

**RQ2.** After review results are returned, what observable response patterns
appear in the persistent workspace and the subsequent execution trajectory?

The study's contribution is the combination of:

- a persistent, evolving Worker project workspace;
- Worker-controlled review invocation;
- immutable snapshots at review requests;
- separate Worker and Reviewer contexts, with Reviewer writes isolated to its
  own review workspace;
- Worker-controlled post-review response; and
- auditable long-horizon trajectories.

Persistent workspace alone is not the sole or primary novelty claimed here.

## Analysis scope

The primary behavioral analysis covers the four `explicit_collaboration`
trajectories. Their formal Reviewer session counts are **2 / 2 / 4 / 2**, for
ten completed sessions. The corresponding frozen formal review records contain
**20 / 20 / 14 / 15 finding records**, totaling 69. The original run manifests'
zero-valued Reviewer finding aggregate is a documented historical aggregation
bug; the frozen manifests remain unchanged.

The four paired `worker_only` runs are an **auxiliary baseline** for
descriptive context. The analysis concerns observable trajectory patterns and
does not estimate a causal treatment effect or establish statistical
superiority.

## Pair 003: same-state resubmission and output recovery

Pair 003 reviews 2 and 3 use the same Worker snapshot SHA-256:

`e3c14acc5e726b866e8989fe6106cc391960f97851548f303248265a7bcd25a6`

The frozen trajectory records Reviewer file reads, Python checks, and workspace
analysis during review 2. At the formal `finish_review` stage, three attempts
were schema-invalid. The eventual frozen review 2 result is unusually brief:
one low-severity `observation` and a placeholder-style summary. The Worker did
not change `project/` before immediately requesting review again. Review 3
used the same snapshot while the long-running Reviewer context and review
workspace persisted, and it produced three substantive `confirmed_violation`
findings. The Worker later changed the project, and review 4 recorded those
findings as resolved.

This sequence is described as a **same-state review resubmission /
review-output recovery**. It shows that the Worker can invoke review again
without a project-state change and that a review invocation can serve a
control-flow recovery role. Reviews 2 and 3 are not treated as independent
from-scratch repetitions, and this sequence is not direct evidence of Reviewer
nondeterminism.

## Interpretation limits

The study does not claim:

- a causal effect of Reviewer availability or use;
- statistical superiority of `explicit_collaboration` over `worker_only`;
- that Reviewer use reduces all final violations; or
- that Worker, Reviewer, or blind-evaluator findings are engineering truth.

UGS-SYNTH-D01 is a synthetic complex-task testbed for studying long-horizon
agent behavior. This is not a paper proposing an underground gas storage
engineering design method. `UGS_FORMAL_STATE=NOT READY` remains in effect.

## Relationship to the frozen artifact

The evidence and analyses under [`artifact/`](artifact/README.md) remain
frozen. This repository-level document records the current manuscript framing;
it does not rewrite historical runs, findings, manifests, or aggregate
results. See [`PUBLICATION_SOURCE.md`](PUBLICATION_SOURCE.md) for source
provenance and the boundary between repository framing and the frozen package.
