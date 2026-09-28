from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_bytes(columns: list[str], rows: list[dict[str, Any]]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_tables() -> dict[str, bytes]:
    evidence = PACKAGE_ROOT / "evidence"
    assignments = load_json(evidence / "blind_evaluation/revealed_mapping.json")["assignments"]
    normalized = load_json(evidence / "blind_evaluation/normalized_findings.json")
    run_summaries = load_json(PACKAGE_ROOT / "experiments/summaries/run_summaries.json")
    submission_index = load_json(evidence / "final_submissions/INDEX.json")
    review_files = sorted((evidence / "blind_evaluation/reviews").glob("submission_*/pass_*/review.json"))

    runs_by_id = {item["run_id"]: item for item in run_summaries}
    submissions_by_alias = {item["submission_alias"]: item for item in submission_index}
    review_counts: dict[str, int] = defaultdict(int)
    raw_finding_counts: dict[str, int] = defaultdict(int)
    for review_path in review_files:
        alias = review_path.parents[1].name
        review = load_json(review_path)
        review_counts[alias] += 1
        raw_finding_counts[alias] += len(review.get("findings", []))
    for alias, assignment in assignments.items():
        if review_counts[alias] != assignment.get("frozen_pass_count"):
            raise ValueError(f"frozen_pass_count_mismatch:{alias}")
        if alias not in submissions_by_alias:
            raise ValueError(f"published_submission_missing:{alias}")

    normalized_issues = normalized.get("issues", [])
    issues_by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in normalized_issues:
        issues_by_alias[issue["submission_alias"]].append(issue)

    submission_rows = []
    for alias, assignment in sorted(assignments.items()):
        run_id = assignment["original_run_id"]
        run = runs_by_id[run_id]
        issue_rows = issues_by_alias.get(alias, [])
        confirmed_count = sum("confirmed_violation" in issue.get("status_labels", []) for issue in issue_rows)
        n1_unsupported = any(
            issue.get("primary_category") == "N-1 reliability"
            and "unsupported_claim" in issue.get("status_labels", [])
            for issue in issue_rows
        )
        published = submissions_by_alias[alias]
        if published["source_project_sha256"] != assignment["source_project_sha256"]:
            raise ValueError(f"submission_hash_index_mismatch:{alias}")
        submission_rows.append(
            {
                "submission_alias": alias,
                "run_id": run_id,
                "condition": assignment["condition"],
                "pair_number": assignment["pair_number"],
                "source_project_sha256": assignment["source_project_sha256"],
                "project_file_count": assignment["project_file_count"],
                "completion_status": run["completion_status"],
                "finish_requested": str(run["finish_requested"]).lower(),
                "blind_review_pass_count": review_counts[alias],
                "raw_finding_record_count": raw_finding_counts[alias],
                "normalized_confirmed_issue_group_count": confirmed_count,
                "n1_unsupported_claim": str(n1_unsupported).lower(),
            }
        )

    condition_names = ("worker_only", "explicit_collaboration")
    conditions = {
        name: [row for row in submission_rows if row["condition"] == name]
        for name in condition_names
    }
    if any(len(rows) != 4 for rows in conditions.values()):
        raise ValueError("paired_submission_condition_coverage_mismatch")

    sessions_by_pair = {}
    for pair_number in sorted({item["pair_number"] for item in submission_rows}):
        explicit = next(
            item
            for item in run_summaries
            if item["condition"] == "explicit_collaboration" and item["pair_number"] == pair_number
        )
        sessions_by_pair[pair_number] = explicit["reviewer"]["review_count"]

    pair_rows = []
    for pair_number in sorted({item["pair_number"] for item in submission_rows}):
        worker = next(row for row in submission_rows if row["pair_number"] == pair_number and row["condition"] == "worker_only")
        explicit = next(row for row in submission_rows if row["pair_number"] == pair_number and row["condition"] == "explicit_collaboration")
        worker_run = runs_by_id[worker["run_id"]]
        explicit_run = runs_by_id[explicit["run_id"]]
        pair_rows.append(
            {
                "pair_number": pair_number,
                "worker_only_run_id": worker["run_id"],
                "explicit_collaboration_run_id": explicit["run_id"],
                "worker_only_review_sessions": worker_run["reviewer"]["review_count"],
                "explicit_collaboration_review_sessions": explicit_run["reviewer"]["review_count"],
                "worker_only_completion_status": worker["completion_status"],
                "explicit_collaboration_completion_status": explicit["completion_status"],
                "worker_only_confirmed_issue_groups": worker["normalized_confirmed_issue_group_count"],
                "explicit_collaboration_confirmed_issue_groups": explicit["normalized_confirmed_issue_group_count"],
                "worker_only_n1_unsupported_submission": worker["n1_unsupported_claim"],
                "explicit_collaboration_n1_unsupported_submission": explicit["n1_unsupported_claim"],
            }
        )

    reviewer_session_rows = []
    for run in sorted(
        (item for item in run_summaries if item["condition"] == "explicit_collaboration"),
        key=lambda item: item["run_id"],
    ):
        previous_snapshot_sha256 = None
        records = sorted(
            run["reviewer"].get("frozen_review_records", []),
            key=lambda item: int(item["review_number"]),
        )
        for record in records:
            review_path = PACKAGE_ROOT / record["formal_review_path"]
            snapshot_path = PACKAGE_ROOT / record["snapshot_manifest_path"]
            formal_review = load_json(review_path)
            snapshot_manifest = load_json(snapshot_path)
            snapshot_sha256 = record.get("snapshot_sha256")
            if snapshot_sha256 != snapshot_manifest.get("snapshot_sha256"):
                raise ValueError(f"reviewer_snapshot_hash_mismatch:{run['run_id']}:{record['review_number']}")
            same_snapshot = (
                None
                if previous_snapshot_sha256 is None
                else snapshot_sha256 == previous_snapshot_sha256
            )
            termination_reason = record.get("termination_reason")
            if not termination_reason:
                raise ValueError(f"reviewer_termination_reason_missing:{run['run_id']}:{record['review_number']}")
            reviewer_session_rows.append(
                {
                    "run_id": run["run_id"],
                    "review_request_order": record["review_number"],
                    "snapshot_sha256": snapshot_sha256,
                    "same_snapshot_as_previous_review": "" if same_snapshot is None else str(same_snapshot).lower(),
                    "project_snapshot_changed_since_previous_review": "" if same_snapshot is None else str(not same_snapshot).lower(),
                    "finding_count": len(formal_review.get("findings", [])),
                    "termination_status": termination_reason,
                    "formal_review_path": record["formal_review_path"],
                    "snapshot_manifest_path": record["snapshot_manifest_path"],
                }
            )
            previous_snapshot_sha256 = snapshot_sha256

    n1_coverage = {}
    for condition, rows in conditions.items():
        covered = sum(row["n1_unsupported_claim"] == "true" for row in rows)
        n1_coverage[condition] = {"submissions_with_n1_unsupported_claim": covered, "submission_count": len(rows)}

    confirmed_by_condition = {
        condition: sum(row["normalized_confirmed_issue_group_count"] for row in rows)
        for condition, rows in conditions.items()
    }
    findings_by_run = {
        item["run_id"]: sum(
            review.get("finding_count_in_formal_review_file", 0)
            for review in item["reviewer"].get("frozen_review_records", [])
        )
        for item in run_summaries
    }
    manifest_discrepancies = []
    for run in run_summaries:
        recorded = run["reviewer"].get("findings_count_as_recorded_in_run_manifest")
        from_reviews = findings_by_run[run["run_id"]]
        if recorded != from_reviews:
            manifest_discrepancies.append(
                {
                    "run_id": run["run_id"],
                    "findings_count_as_recorded_in_run_manifest": recorded,
                    "findings_count_in_published_formal_review_files": from_reviews,
                }
            )

    pass_distribution: dict[str, int] = defaultdict(int)
    for count in review_counts.values():
        pass_distribution[str(count)] += 1
    summary = {
        "source_boundary": "Aggregates use published run metadata, final submissions, frozen review files, and existing normalized finding labels. No reviewer judgment or taxonomy was regenerated.",
        "paired_replication_count": len(pair_rows),
        "final_submissions_by_condition": {condition: len(rows) for condition, rows in conditions.items()},
        "interactive_reviewer_sessions_total": sum(sessions_by_pair.values()),
        "interactive_reviewer_sessions_by_explicit_pair": sessions_by_pair,
        "formal_reviewer_findings_by_explicit_pair": {
            pair_number: findings_by_run[
                next(
                    item["run_id"]
                    for item in run_summaries
                    if item["condition"] == "explicit_collaboration" and item["pair_number"] == pair_number
                )
            ]
            for pair_number in sorted(sessions_by_pair)
        },
        "blind_review_pass_count": len(review_files),
        "blind_submission_pass_distribution": pass_distribution,
        "double_pass_submission_count": pass_distribution.get("2", 0),
        "single_pass_submission_count": pass_distribution.get("1", 0),
        "normalized_confirmed_issue_groups_by_condition": confirmed_by_condition,
        "n1_unsupported_claim_submission_coverage_by_condition": n1_coverage,
        "preserved_source_manifest_discrepancies": manifest_discrepancies,
    }

    submission_columns = [
        "submission_alias",
        "run_id",
        "condition",
        "pair_number",
        "source_project_sha256",
        "project_file_count",
        "completion_status",
        "finish_requested",
        "blind_review_pass_count",
        "raw_finding_record_count",
        "normalized_confirmed_issue_group_count",
        "n1_unsupported_claim",
    ]
    pair_columns = [
        "pair_number",
        "worker_only_run_id",
        "explicit_collaboration_run_id",
        "worker_only_review_sessions",
        "explicit_collaboration_review_sessions",
        "worker_only_completion_status",
        "explicit_collaboration_completion_status",
        "worker_only_confirmed_issue_groups",
        "explicit_collaboration_confirmed_issue_groups",
        "worker_only_n1_unsupported_submission",
        "explicit_collaboration_n1_unsupported_submission",
    ]
    reviewer_session_columns = [
        "run_id",
        "review_request_order",
        "snapshot_sha256",
        "same_snapshot_as_previous_review",
        "project_snapshot_changed_since_previous_review",
        "finding_count",
        "termination_status",
        "formal_review_path",
        "snapshot_manifest_path",
    ]
    return {
        "submission_summary.csv": csv_bytes(submission_columns, submission_rows),
        "pair_comparison.csv": csv_bytes(pair_columns, pair_rows),
        "review_session_summary.csv": csv_bytes(reviewer_session_columns, reviewer_session_rows),
        "summary_counts.json": (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate compact tables from released frozen evidence.")
    parser.add_argument("--output-dir", default="analysis/rebuilt_tables", help="directory relative to the package root")
    parser.add_argument("--check", action="store_true", help="compare regenerated bytes with existing output files")
    args = parser.parse_args()
    output = Path(args.output_dir)
    if not output.is_absolute():
        output = PACKAGE_ROOT / output
    artifacts = build_tables()
    if args.check:
        mismatches = [name for name, data in artifacts.items() if not (output / name).is_file() or (output / name).read_bytes() != data]
        if mismatches:
            print("FAIL: " + ", ".join(mismatches))
            return 1
        print(f"PASS: regenerated {len(artifacts)} tables byte-for-byte")
        return 0
    output.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    print(f"WROTE: {len(artifacts)} tables under {output.relative_to(PACKAGE_ROOT).as_posix() if output.is_relative_to(PACKAGE_ROOT) else output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
