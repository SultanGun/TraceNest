"""Scope guard and sensitive configuration file modification checks."""

import fnmatch
from pathlib import Path
from typing import List

from tracenest.models import FileChange, Finding, FindingSeverity
from tracenest.scanners.secrets import generate_finding_id

SENSITIVE_CONFIG_PATTERNS = [
    (
        ".env*",
        FindingSeverity.CRITICAL,
        "CFG-ENV-FILE",
        "Environment Secret Configuration File Modified",
        "Environment files (.env) commonly contain production secrets, API tokens, and credentials. Avoid checking them into version control.",
    ),
    (
        ".aws/*",
        FindingSeverity.CRITICAL,
        "CFG-AWS-CONFIG",
        "Cloud Credentials File Modified",
        "AWS credential files store sensitive access keys and session tokens. Do not alter or commit cloud profile credentials.",
    ),
    (
        "*.pem",
        FindingSeverity.CRITICAL,
        "CFG-CERT-KEY",
        "Cryptographic Certificate or Key File Changed",
        "X.509 certificates and private keys should be managed through TLS automation or secure key vaults.",
    ),
    (
        "*.key",
        FindingSeverity.CRITICAL,
        "CFG-KEY-FILE",
        "Private Key File Changed",
        "Private cryptographic keys must never be committed to source code repositories.",
    ),
    (
        "credentials.json",
        FindingSeverity.HIGH,
        "CFG-CRED-JSON",
        "Service Account / Credential JSON Changed",
        "Google Cloud or general service account JSON keys allow unauthorized service access.",
    ),
    (
        ".npmrc",
        FindingSeverity.HIGH,
        "CFG-NPMRC",
        "NPM Registry Configuration Changed",
        "Modifications to .npmrc can introduce private registry tokens or alter package resolution endpoints.",
    ),
    (
        ".pypirc",
        FindingSeverity.HIGH,
        "CFG-PYPIRC",
        "PyPI Repository Configuration Changed",
        "PyPI configuration files may contain publish tokens or custom repository URLs.",
    ),
    (
        ".github/workflows/*",
        FindingSeverity.HIGH,
        "CFG-GH-WORKFLOW",
        "GitHub Actions CI/CD Workflow Changed",
        "AI agents modifying CI/CD workflows may introduce unauthorized build steps, secret leakage, or malicious runners.",
    ),
    (
        ".gitlab-ci.yml",
        FindingSeverity.HIGH,
        "CFG-GL-CI",
        "GitLab CI Configuration Changed",
        "Review CI pipeline modifications carefully to ensure no unauthorized pipelines or secret variables are accessed.",
    ),
]

DEPENDENCY_BUILD_PATTERNS = [
    (
        "requirements*.txt",
        "DEP-PY-REQ",
        "Python Requirements List Modified",
        "Verify that all newly added or upgraded dependencies are legitimate and free of typosquatting.",
    ),
    (
        "pyproject.toml",
        "DEP-PY-PROJ",
        "Python Project & Build Configuration Modified",
        "Inspect build dependencies, pinned versions, and build scripts for unexpected supply chain additions.",
    ),
    (
        "setup.py",
        "DEP-PY-SETUP",
        "Python Setup Script Modified",
        "Setup scripts execute arbitrary code during installation. Review any added packages or commands.",
    ),
    (
        "package.json",
        "DEP-JS-PKG",
        "Node.js Package Manifest Modified",
        "Inspect added npm packages and package scripts (preinstall, postinstall) for malicious dependencies.",
    ),
    (
        "Cargo.toml",
        "DEP-RUST-CARGO",
        "Rust Cargo Manifest Modified",
        "Verify Rust crate names and features to avoid supply chain vulnerabilities.",
    ),
    (
        "Dockerfile*",
        "DEP-DOCKER",
        "Container Build Specification Modified",
        "Inspect base images, RUN instructions, and exposed ports for security compliance.",
    ),
    (
        "Makefile",
        "DEP-MAKEFILE",
        "Build Makefile Modified",
        "Makefiles can execute arbitrary shell commands. Verify target definitions.",
    ),
]


def check_sensitive_configs(changes: List[FileChange]) -> List[Finding]:
    """Check if any changed file matches sensitive configuration patterns."""
    findings: List[Finding] = []
    for change in changes:
        path = change.path
        filename = Path(path).name

        for pattern, severity, rule_id, title, rec in SENSITIVE_CONFIG_PATTERNS:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                finding_id = generate_finding_id(rule_id, path, None, title)
                findings.append(
                    Finding(
                        finding_id=finding_id,
                        rule_id=rule_id,
                        severity=severity,
                        title=title,
                        explanation=f"A sensitive configuration file '{path}' was {change.change_type.value}.",
                        file_path=path,
                        line_number=None,
                        evidence=f"File status: {change.change_type.value} (+{change.additions}/-{change.deletions})",
                        recommendation=rec,
                        confidence="HIGH",
                    )
                )
                break

    return findings


def check_dependency_modifications(changes: List[FileChange]) -> List[Finding]:
    """Check if dependency or build configuration files were modified."""
    findings: List[Finding] = []
    for change in changes:
        path = change.path
        filename = Path(path).name

        for pattern, rule_id, title, rec in DEPENDENCY_BUILD_PATTERNS:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                finding_id = generate_finding_id(rule_id, path, None, title)
                findings.append(
                    Finding(
                        finding_id=finding_id,
                        rule_id=rule_id,
                        severity=FindingSeverity.MEDIUM,
                        title=title,
                        explanation=f"Build/dependency file '{path}' was {change.change_type.value} by the AI session.",
                        file_path=path,
                        line_number=None,
                        evidence=f"Status: {change.change_type.value} (+{change.additions}/-{change.deletions})",
                        recommendation=rec,
                        confidence="HIGH",
                    )
                )
                break

    return findings


def check_scope_boundaries(changes: List[FileChange], include_paths: List[str]) -> List[Finding]:
    """Check if changes occurred outside explicitly configured project scope."""
    if not include_paths:
        return []

    findings: List[Finding] = []
    for change in changes:
        path = change.path
        matched = False
        for inc in include_paths:
            clean = inc.strip("/")
            if path == clean or path.startswith(clean + "/"):
                matched = True
                break

        if not matched:
            rule_id = "SCP-OUT-OF-SCOPE"
            title = "File Modified Outside Configured Target Scope"
            finding_id = generate_finding_id(rule_id, path, None, title)
            findings.append(
                Finding(
                    finding_id=finding_id,
                    rule_id=rule_id,
                    severity=FindingSeverity.HIGH,
                    title=title,
                    explanation=(
                        f"The file '{path}' was modified, but falls outside the configured "
                        f"scope inclusion paths: {include_paths}."
                    ),
                    file_path=path,
                    line_number=None,
                    evidence=f"Path: {path}",
                    recommendation="Confirm whether the AI agent had explicit permission to modify files outside target scope.",
                    confidence="HIGH",
                )
            )

    return findings
