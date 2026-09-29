# Manuscript analysis scope

This repository contains a frozen research artifact and supporting evidence for the manuscript:

**Agents for Long-Horizon Tasks: Persistent Workspaces and Autonomous Review**

## Primary manuscript question

The manuscript primarily studies how an execution agent operating over a persistent workspace can autonomously decide whether and when to request an independent review, and how review becomes part of a long-horizon task trajectory.

The main behavioral analysis therefore focuses on the four frozen `explicit_collaboration` trajectories, in which the Worker had access to `submit_for_review` and controlled:

- whether to request review;
- when to request review;
- what to ask the Reviewer to focus on;
- how to respond to returned findings;
- whether to modify the workspace, continue working, request another review, or finish.

Across those four trajectories, the Worker initiated 2, 2, 4, and 2 review sessions, respectively.

## Role of the Worker-only runs

The frozen study also contains four matched `worker_only` runs, one for each paired replication. These runs are retained as auxiliary paired baselines and as part of the complete released evidence.

They are **not** the primary object of the manuscript's behavioral analysis, because they do not contain autonomous Reviewer invocation.

The manuscript does not use the four pairs to claim:

- a causal treatment effect of Reviewer availability;
- statistical superiority of one condition;
- that Reviewer use reduces overall engineering violations;
- or that model-based review constitutes engineering ground truth.

The paired runs remain useful for contextual comparison and for preserving the complete experimental record.

## Relationship to the frozen artifact

The canonical frozen package remains under `artifact/`.

That package records all eight runs, all frozen submissions, the ten interactive Worker–Reviewer sessions, blind post-hoc evaluation, configuration hashes, runtime hashes, and known evidence limitations.

The files under `artifact/` are intentionally left unchanged by this manuscript-framing update so that `artifact/RELEASE_MANIFEST.json` and its integrity checks remain valid.

Repository-level manuscript framing may evolve without rewriting the frozen evidence package.

## Interpretation boundary

The synthetic UGS-SYNTH-D01 task is used as a complex multi-file test environment for long-horizon agent behavior. The manuscript is not a paper about underground gas-storage design methods, and it does not claim that generated designs are production-ready engineering designs.

Interactive Reviewer findings and blind-evaluator findings are model-generated evidence, not formal engineering ground truth. `UGS_FORMAL_STATE=NOT READY` remains in force.
