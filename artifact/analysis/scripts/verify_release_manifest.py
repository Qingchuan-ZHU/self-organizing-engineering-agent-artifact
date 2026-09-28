from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_NAME = "RELEASE_MANIFEST.json"
IGNORED_BUILD_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def public_world_hash(directory: Path) -> tuple[str, dict[str, str]]:
    file_hashes = {
        path.relative_to(directory).as_posix(): sha256_file(path)
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    return sha256_json(file_hashes), file_hashes


def tree_digest(directory: Path) -> str:
    rows = []
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink:{path.relative_to(PACKAGE_ROOT).as_posix()}")
        if path.is_file():
            rows.append((path.relative_to(directory).as_posix(), sha256_file(path)))
    digest = hashlib.sha256()
    for name, file_hash in sorted(rows):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def package_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.relative_to(root).as_posix() != MANIFEST_NAME
            and not any(part in IGNORED_BUILD_PARTS or part.endswith(".egg-info") for part in path.relative_to(root).parts)
            and path.suffix.lower() not in {".pyc", ".pyo", ".pyd"}
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def build_manifest(root: Path = PACKAGE_ROOT) -> dict[str, Any]:
    provenance_path = root / "SOURCE_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    source_records = provenance.get("source_files", [])
    source_by_path = {record["relative_path"]: record for record in source_records}
    if len(source_by_path) != len(source_records):
        raise ValueError("duplicate_source_file_index_paths")

    files = []
    for path in package_files(root):
        relative = path.relative_to(root).as_posix()
        source = source_by_path.get(relative)
        if source is None:
            category = (
                "credential-free provider configuration template"
                if relative == ".env.example"
                else "generated release documentation or derived analysis"
            )
            source_path = None
            source_hash = None
            state = "generated"
        else:
            category = source["category"]
            source_path = source["source_path"]
            source_hash = source["source_sha256"]
            state = source["frozen_or_generated"]
        files.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "category": category,
                "source_path": source_path,
                "source_sha256": source_hash,
                "frozen_or_generated": state,
            }
        )
    return {
        "schema_version": 1,
        "generated_at_utc": provenance["release_generation_time_utc"],
        "file_count": len(files),
        "total_size_bytes": sum(row["size_bytes"] for row in files),
        "manifest_self_reference": {
            "relative_path": MANIFEST_NAME,
            "included_in_file_count": False,
            "reason": "A manifest cannot contain its own final SHA-256; the Git commit records this file.",
        },
        "files": files,
    }


def verify_package(root: Path = PACKAGE_ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return ["release_manifest_missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        provenance = json.loads((root / "SOURCE_PROVENANCE.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"metadata_parse_error:{type(exc).__name__}"]

    rows = manifest.get("files")
    if not isinstance(rows, list):
        return ["manifest_files_not_a_list"]
    entries: dict[str, dict[str, Any]] = {}
    for row in rows:
        relative = row.get("relative_path")
        if not isinstance(relative, str):
            errors.append("manifest_entry_missing_relative_path")
            continue
        rel = PurePosixPath(relative)
        if rel.is_absolute() or any(part in {"..", ""} for part in rel.parts):
            errors.append(f"unsafe_manifest_path:{relative}")
            continue
        if relative in entries:
            errors.append(f"duplicate_manifest_path:{relative}")
            continue
        entries[relative] = row
        path = root.joinpath(*rel.parts)
        if not path.is_file() or path.is_symlink():
            errors.append(f"manifest_file_missing_or_symlink:{relative}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != row.get("sha256"):
            errors.append(f"published_hash_mismatch:{relative}")
        if path.stat().st_size != row.get("size_bytes"):
            errors.append(f"published_size_mismatch:{relative}")
        if row.get("frozen_or_generated") in {"frozen_copy", "source_copy"}:
            if row.get("source_sha256") != row.get("sha256"):
                errors.append(f"source_copy_hash_mismatch:{relative}")

    actual_paths = {path.relative_to(root).as_posix() for path in package_files(root)}
    if actual_paths != set(entries):
        missing = sorted(actual_paths - set(entries))
        stale = sorted(set(entries) - actual_paths)
        if missing:
            errors.append("unmanifested_files:" + ",".join(missing))
        if stale:
            errors.append("missing_files:" + ",".join(stale))

    expected_count = len(entries)
    expected_size = sum(row.get("size_bytes", 0) for row in rows)
    if manifest.get("file_count") != expected_count:
        errors.append("manifest_file_count_mismatch")
    if manifest.get("total_size_bytes") != expected_size:
        errors.append("manifest_total_size_mismatch")
    if manifest.get("manifest_self_reference", {}).get("included_in_file_count") is not False:
        errors.append("manifest_self_reference_policy_mismatch")

    world_path = root / "cases/ugs_synth_d01/public"
    actual_world_hash, actual_world_files = public_world_hash(world_path)
    if actual_world_hash != provenance.get("public_world_sha256"):
        errors.append("public_world_hash_mismatch")
    for config_path in sorted((root / "experiments/configurations").glob("*/freeze.json")):
        freeze = json.loads(config_path.read_text(encoding="utf-8"))
        if freeze.get("public_world_sha256") != actual_world_hash:
            errors.append(f"frozen_public_world_hash_mismatch:{config_path.parent.name}")
        if freeze.get("public_world_files") != actual_world_files:
            errors.append(f"frozen_public_world_file_map_mismatch:{config_path.parent.name}")
        if freeze.get("formal_state") != "UGS_FORMAL_STATE=NOT READY":
            errors.append(f"formal_state_changed:{config_path.parent.name}")

    index_path = root / "evidence/final_submissions/INDEX.json"
    for item in json.loads(index_path.read_text(encoding="utf-8")):
        submission = root / item["published_path"]
        if tree_digest(submission) != item["source_project_sha256"]:
            errors.append(f"final_submission_tree_hash_mismatch:{item['submission_alias']}")

    for record in provenance.get("runtime_source_hash_checks", []):
        if record.get("verified") is not True:
            errors.append(f"runtime_source_check_not_verified:{record.get('run_id')}:{record.get('source_path')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the public release file manifest.")
    parser.add_argument("--write", action="store_true", help="write RELEASE_MANIFEST.json before verification")
    args = parser.parse_args()
    manifest_path = PACKAGE_ROOT / MANIFEST_NAME
    if args.write:
        manifest = build_manifest()
        with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    errors = verify_package()
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frozen_count = sum(row.get("frozen_or_generated") == "frozen_copy" for row in manifest["files"])
    print(json.dumps({"status": "PASS", "file_count": manifest["file_count"], "total_size_bytes": manifest["total_size_bytes"], "frozen_copy_count": frozen_count}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
