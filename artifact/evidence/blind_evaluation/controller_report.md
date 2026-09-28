# Blind evaluation controller report

**Initialized:** 2026-09-25T04:40:56.214177Z
**Ready blind packages:** 8
**Unavailable or excluded runs:** 0

## Readiness

Every included source run has a terminal run manifest, a final Worker project snapshot, and a snapshot whose file set and SHA-256 values match its frozen artifact_hashes.json entries. All included public briefs have identical file/hash manifests. Worker-only 003 is a naturally ended terminated_without_finish_project run; its frozen final project snapshot is included without relabeling it as a successful finish_project completion.

- submission_A: terminal status agent_completed_without_evaluation, end time present, final project hash matches (23 files).
- submission_B: terminal status agent_completed_without_evaluation, end time present, final project hash matches (17 files).
- submission_C: terminal status agent_completed_without_evaluation, end time present, final project hash matches (22 files).
- submission_D: terminal status agent_completed_without_evaluation, end time present, final project hash matches (16 files).
- submission_E: terminal status agent_completed_without_evaluation, end time present, final project hash matches (16 files).
- submission_F: terminal status terminated_without_finish_project, end time present, final project hash matches (16 files).
- submission_G: terminal status agent_completed_without_evaluation, end time present, final project hash matches (23 files).
- submission_H: terminal status agent_completed_without_evaluation, end time present, final project hash matches (10 files).

Unavailable/excluded source runs:

- None.

## Blind packaging

Packages are under blind_packages/; each package has exactly brief/ and submission/. The brief bytes are copied from the canonical frozen public brief; submission files are copied byte-for-byte from each final project snapshot. File timestamps were normalized for blinding. Source snapshots and run evidence were not modified. A 256-bit random seed and mapping provenance are stored only in blind_mapping.json; evaluator processes are not given that path or file.

Initial package checks: all package hashes matched, all briefs were identical, and the exact configured-credential scan found 0 matches; no environment files were copied.

## Fresh-session execution

The installed Codex CLI reports version 0.130.0. codex --help and codex exec --help confirm non-interactive exec, --ephemeral, --json, --output-schema, explicit --cd, and sandbox options. Evaluators use separate ephemeral CLI processes with the same prompt/model settings, one anonymous package per process, and no session resumption.

Initial readiness check found 8 of 8 requested final snapshots available; 0 unavailable.
