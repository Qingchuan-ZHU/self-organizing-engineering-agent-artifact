from __future__ import annotations

import argparse
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlparse


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SECRET_PATTERNS = {
    "deepseek_or_openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_token": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "secret_assignment": re.compile(
        r"(?i)\b(?:DEEPSEEK_API_KEY|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|GITHUB_PAT)\s*[:=]\s*['\"]?(?!your_|placeholder|example|<)[A-Za-z0-9+/=_-]{20,}"
    ),
}
WINDOWS_ABSOLUTE = re.compile(r"\b[A-Za-z]:[\\/](?![\\/])[^\s\"'<>]+")
UNC_ABSOLUTE = re.compile(r"\\\\[A-Za-z0-9._-]+\\[^\s\"'<>]+")
POSIX_LOCAL = re.compile(r"(?<![A-Za-z0-9_.-])/(?:home|Users|tmp|var/tmp|private|mnt/data)/[^\s\"'<>]+")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def text_files(root: Path):
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def private_url(value: str) -> bool:
    try:
        parsed = urlparse(value.rstrip(").,;"))
        host = parsed.hostname
        if not host:
            return False
        normalized = host.lower().rstrip(".")
        if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith((".local", ".internal", ".lan")):
            return True
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            return False
        return address.is_private or address.is_loopback or address.is_link_local
    except ValueError:
        return False


def audit(root: Path = PACKAGE_ROOT) -> dict:
    findings = []
    unexpected_env = []
    for path, content in text_files(root):
        relative = path.relative_to(root).as_posix()
        if path.name.lower() == ".env":
            unexpected_env.append(relative)
        for line_number, line in enumerate(content.splitlines(), 1):
            for finding_type, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append({"type": finding_type, "path": relative, "line": line_number})
            if WINDOWS_ABSOLUTE.search(line):
                findings.append({"type": "windows_absolute_path", "path": relative, "line": line_number})
            if UNC_ABSOLUTE.search(line):
                findings.append({"type": "unc_absolute_path", "path": relative, "line": line_number})
            if POSIX_LOCAL.search(line):
                findings.append({"type": "posix_local_or_temporary_path", "path": relative, "line": line_number})
            if any(private_url(match.group(0)) for match in URL_PATTERN.finditer(line)):
                findings.append({"type": "private_or_machine_local_url", "path": relative, "line": line_number})

    example = root / ".env.example"
    example_values = {}
    if example.is_file():
        for line in example.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            example_values[key.strip()] = value.strip().strip("\"'")
    api_key = example_values.get("DEEPSEEK_API_KEY")
    template_safe = api_key == "" or bool(api_key and re.fullmatch(r"(?i)(your|placeholder|example)[A-Za-z0-9_.<>-]*", api_key))
    if not template_safe:
        findings.append({"type": "env_example_not_placeholder_only", "path": ".env.example", "line": 1})

    findings = sorted(set((item["type"], item["path"], item["line"]) for item in findings))
    finding_rows = [{"type": kind, "path": path, "line": line} for kind, path, line in findings]
    credential_hits = [row for row in finding_rows if row["type"] in SECRET_PATTERNS or row["type"] == "env_example_not_placeholder_only"]
    privacy_hits = [row for row in finding_rows if row["type"] in {"windows_absolute_path", "unc_absolute_path", "posix_local_or_temporary_path", "private_or_machine_local_url"}]
    return {
        "status": "PASS" if not credential_hits and not unexpected_env and template_safe else "FAIL",
        "credential_hit_count": len(credential_hits),
        "unexpected_env_file_count": len(unexpected_env),
        "env_example_placeholder_only": template_safe,
        "private_or_machine_local_url_count": sum(row["type"] == "private_or_machine_local_url" for row in finding_rows),
        "absolute_or_temporary_path_count": sum(row["type"] in {"windows_absolute_path", "unc_absolute_path", "posix_local_or_temporary_path"} for row in finding_rows),
        "unexpected_env_files": unexpected_env,
        "findings": finding_rows,
        "privacy_hit_count": len(privacy_hits),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan package text for credentials and machine-local references.")
    parser.add_argument("--fail-on-privacy-findings", action="store_true", help="return failure if absolute paths or private URLs are found")
    args = parser.parse_args()
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        return 1
    if args.fail_on_privacy_findings and result["privacy_hit_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
