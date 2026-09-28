from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def load_release_script(name: str) -> ModuleType:
    path = PACKAGE_ROOT / "analysis" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"release_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could_not_load_release_script:{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_package_imports() -> None:
    import self_organizing_engineering_agent as package
    from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review import durable_runtime

    assert package.__version__ == "0.1.0"
    assert callable(durable_runtime.worker_tool_definitions_for_condition)


def test_release_manifest_and_public_world_hashes() -> None:
    verifier = load_release_script("verify_release_manifest")

    assert verifier.verify_package() == []
    manifest = json.loads((PACKAGE_ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    env_example_row = next(row for row in manifest["files"] if row["relative_path"] == ".env.example")
    assert env_example_row["category"] == "credential-free provider configuration template"
    assert env_example_row["frozen_or_generated"] == "generated"
    actual_world_hash, _ = verifier.public_world_hash(PACKAGE_ROOT / "cases/ugs_synth_d01/public")
    provenance = json.loads((PACKAGE_ROOT / "SOURCE_PROVENANCE.json").read_text(encoding="utf-8"))
    assert actual_world_hash == provenance["public_world_sha256"]


def test_regenerated_analysis_matches_published_tables_and_frozen_counts() -> None:
    table_builder = load_release_script("build_release_tables")
    generated = table_builder.build_tables()
    output_root = PACKAGE_ROOT / "analysis/rebuilt_tables"
    assert all((output_root / name).read_bytes() == data for name, data in generated.items())

    summary = json.loads(generated["summary_counts.json"])
    assert summary["paired_replication_count"] == 4
    assert summary["final_submissions_by_condition"] == {"explicit_collaboration": 4, "worker_only": 4}
    assert summary["interactive_reviewer_sessions_total"] == 10
    assert summary["interactive_reviewer_sessions_by_explicit_pair"] == {
        "001": 2,
        "002": 2,
        "003": 4,
        "004": 2,
    }
    assert summary["blind_review_pass_count"] == 13
    assert summary["double_pass_submission_count"] == 5
    assert summary["single_pass_submission_count"] == 3
    assert summary["normalized_confirmed_issue_groups_by_condition"] == {
        "explicit_collaboration": 5,
        "worker_only": 5,
    }
    assert summary["n1_unsupported_claim_submission_coverage_by_condition"] == {
        "explicit_collaboration": {"submission_count": 4, "submissions_with_n1_unsupported_claim": 1},
        "worker_only": {"submission_count": 4, "submissions_with_n1_unsupported_claim": 4},
    }
    assert len(summary["preserved_source_manifest_discrepancies"]) == 4


def test_security_audit_finds_no_credentials_or_env_files() -> None:
    auditor = load_release_script("audit_release_package")

    result = auditor.audit()
    assert result["status"] == "PASS"
    assert result["credential_hit_count"] == 0
    assert result["unexpected_env_file_count"] == 0
    assert result["env_example_placeholder_only"] is True
    assert result["absolute_or_temporary_path_count"] == 12


def test_reviewer_submission_is_read_only_and_review_workspace_is_writable(tmp_path: Path) -> None:
    from self_organizing_engineering_agent.experiments.pilot_1a.isolation import AgentSandbox
    from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.tools import (
        InterleavedReviewerExecutor,
        InterleavedReviewerTools,
    )

    agent_view = tmp_path / "review-agent"
    brief = agent_view / "brief"
    review = agent_view / "review"
    submission = tmp_path / "snapshot"
    brief.mkdir(parents=True)
    review.mkdir()
    submission.mkdir()
    (brief / "brief.md").write_text("public brief", encoding="utf-8")
    (review / "notes.txt").write_text("review workspace", encoding="utf-8")
    submitted_file = submission / "report.md"
    submitted_file.write_text("frozen submission", encoding="utf-8")

    sandbox = AgentSandbox(tmp_path, agent_view, brief, review)
    executor = InterleavedReviewerExecutor(
        image="test-image",
        brief_root=brief,
        project_root=review,
        submission_root=submission,
    )
    tools = InterleavedReviewerTools(
        sandbox=sandbox,
        executor=executor,
        review_number=1,
        snapshot_root=submission,
        record_formal_review=lambda _number, _result: "test-hash",
    )

    assert tools.read_file("submission/report.md")["content"] == "frozen submission"
    assert "tool_error" in tools.write_file("submission/report.md", "changed")
    assert "tool_error" in tools.write_file("brief/brief.md", "changed")
    assert tools.write_file("review/new.txt", "review output")["bytes"] == len("review output")
    assert submitted_file.read_text(encoding="utf-8") == "frozen submission"
