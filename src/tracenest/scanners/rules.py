"""Deterministic code pattern scanner and unified rules orchestrator."""

import re
from typing import List, Pattern, Tuple

from tracenest.config import TraceNestConfig
from tracenest.models import FileChange, Finding, FindingSeverity
from tracenest.scanners.scope import (
    check_dependency_modifications,
    check_scope_boundaries,
    check_sensitive_configs,
)
from tracenest.scanners.secrets import generate_finding_id, redact_line, scan_file_for_secrets

SEVERITY_ORDER = {
    FindingSeverity.CRITICAL: 5,
    FindingSeverity.HIGH: 4,
    FindingSeverity.MEDIUM: 3,
    FindingSeverity.LOW: 2,
    FindingSeverity.INFO: 1,
}

CODE_PATTERNS: List[Tuple[str, str, FindingSeverity, Pattern[str], str, str]] = [
    (
        "PAT-PY-EVAL",
        "Dynamic Code Execution (eval)",
        FindingSeverity.HIGH,
        re.compile(r"""\b(?:eval|exec)\s*\("""),
        "Dynamic code execution via eval/exec allows arbitrary code execution if untrusted input reaches it.",
        "Refactor to use ast.literal_eval for safe literals or safe parser abstractions.",
    ),
    (
        "PAT-PY-SHELL-TRUE",
        "Subprocess Execution with shell=True",
        FindingSeverity.HIGH,
        re.compile(
            r"""\bsubprocess\.(?:call|run|Popen|check_output|check_call)\s*\([^)]*shell\s*=\s*True"""
        ),
        "Invoking subprocess with shell=True exposes the application to command injection vulnerabilities.",
        "Pass arguments as an argument list (e.g. ['cmd', 'arg']) with shell=False.",
    ),
    (
        "PAT-PY-OS-SYSTEM",
        "Command Execution via os.system",
        FindingSeverity.HIGH,
        re.compile(r"""\bos\.system\s*\("""),
        "os.system executes commands directly in the shell without proper argument escaping.",
        "Use the subprocess module with argument arrays and shell=False.",
    ),
    (
        "PAT-PY-INSECURE-DESERIALIZATION",
        "Insecure Deserialization via pickle",
        FindingSeverity.CRITICAL,
        re.compile(r"""\bpickle\.(?:loads?|Unpickler)\s*\("""),
        "Deserializing untrusted pickle streams can lead to arbitrary remote code execution.",
        "Use safe serialization formats like JSON, MessagePack, or Protocol Buffers.",
    ),
    (
        "PAT-PY-UNSAFE-YAML",
        "Unsafe YAML Deserialization",
        FindingSeverity.HIGH,
        re.compile(
            r"""\byaml\.load\s*\([^,)]*(?:\)|,\s*Loader\s*=\s*(?:yaml\.)?(?:UnsafeLoader|Loader))"""
        ),
        "Unsafe PyYAML loaders instantiate arbitrary Python objects.",
        "Use yaml.safe_load(data) or yaml.load(data, Loader=yaml.SafeLoader).",
    ),
    (
        "PAT-NET-VERIFY-FALSE",
        "TLS Certificate Verification Disabled",
        FindingSeverity.HIGH,
        re.compile(r"""(?i)\bverify\s*=\s*False\b"""),
        "Disabling SSL/TLS verification allows man-in-the-middle (MITM) attacks and credential eavesdropping.",
        "Enable TLS verification and provide custom CA certificates if using self-signed internal endpoints.",
    ),
    (
        "PAT-JS-EVAL",
        "JavaScript Dynamic Evaluation (eval/Function)",
        FindingSeverity.HIGH,
        re.compile(r"""\b(?:eval\s*\(|new\s+Function\s*\()"""),
        "Dynamic code evaluation in JavaScript can cause cross-site scripting (XSS) or remote code execution.",
        "Avoid dynamic evaluation; use strict JSON parsing or dedicated data mappings.",
    ),
    (
        "PAT-JS-DANGEROUS-HTML",
        "React dangerouslySetInnerHTML Used",
        FindingSeverity.MEDIUM,
        re.compile(r"""\bdangerouslySetInnerHTML\b"""),
        "Injecting raw unescaped HTML can introduce Cross-Site Scripting (XSS) vulnerabilities.",
        "Sanitize HTML strings with DOMPurify or use standard JSX text binding.",
    ),
    (
        "PAT-NET-INSECURE-TLS-ENV",
        "Insecure TLS Rejection Disabled via Environment Variable",
        FindingSeverity.HIGH,
        re.compile(r"""NODE_TLS_REJECT_UNAUTHORIZED[^=\n]*=\s*['"]?0['"]?"""),
        "Setting NODE_TLS_REJECT_UNAUTHORIZED=0 globally disables TLS certificate verification in Node.js.",
        "Do not disable global TLS validation; configure specific trusted certificate authorities.",
    ),
]


def scan_file_for_code_patterns(file_path: str, diff_text: str) -> List[Finding]:
    """Scan newly added lines in a diff for potentially dangerous code patterns."""
    findings: List[Finding] = []
    lines = diff_text.splitlines()

    line_counter = 0
    for line in lines:
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                line_counter = int(m.group(1)) - 1
            continue

        if line.startswith("+") and not line.startswith("+++"):
            line_counter += 1
            content = line[1:]

            for rule_id, title, severity, pattern, expl, rec in CODE_PATTERNS:
                if pattern.search(content):
                    redacted = redact_line(content.strip())
                    finding_id = generate_finding_id(rule_id, file_path, line_counter, content)
                    findings.append(
                        Finding(
                            finding_id=finding_id,
                            rule_id=rule_id,
                            severity=severity,
                            title=title,
                            explanation=f"{expl} Detected in {file_path}.",
                            file_path=file_path,
                            line_number=line_counter,
                            evidence=redacted,
                            recommendation=rec,
                            confidence="HIGH",
                        )
                    )
        elif not line.startswith("-"):
            line_counter += 1

    return findings


def run_all_scanners(changes: List[FileChange], config: TraceNestConfig) -> List[Finding]:
    """Execute all configured deterministic scanners across changed files."""
    all_findings: List[Finding] = []

    # 0. Path Traversal & Escaping Symlink Checks
    for change in changes:
        if change.diff_text and "[SECURITY ALERT: Path traversal" in change.diff_text:
            rule_id = "SCP-PATH-TRAVERSAL"
            title = "Path Traversal or Escaping Symlink Detected"
            finding_id = generate_finding_id(rule_id, change.path, None, title)
            all_findings.append(
                Finding(
                    finding_id=finding_id,
                    rule_id=rule_id,
                    severity=FindingSeverity.CRITICAL,
                    title=title,
                    explanation=(
                        f"File '{change.path}' escapes the repository boundary or targets a "
                        "filesystem location outside the repository root."
                    ),
                    file_path=change.path,
                    line_number=None,
                    evidence=change.diff_text,
                    recommendation="Investigate immediately. Remove escaping symlinks or directory traversal links.",
                    confidence="HIGH",
                )
            )

    # 1. Scope boundary checks
    if config.rules.scope_guard and config.scope.include_paths:
        all_findings.extend(check_scope_boundaries(changes, config.scope.include_paths))

    # 2. Sensitive configuration checks
    if config.rules.config_guard:
        all_findings.extend(check_sensitive_configs(changes))

    # 3. Dependency modifications
    if config.rules.dependency_guard:
        all_findings.extend(check_dependency_modifications(changes))

    # 4. Content-level scanners (Secrets & Dangerous Patterns)
    for change in changes:
        if change.is_binary or not change.diff_text:
            continue

        if config.rules.secret_detection:
            all_findings.extend(scan_file_for_secrets(change.path, change.diff_text))

        if config.rules.dangerous_patterns:
            all_findings.extend(scan_file_for_code_patterns(change.path, change.diff_text))

    # Filter by threshold and suppressions
    min_threshold_score = SEVERITY_ORDER.get(config.rules.severity_threshold, 2)
    suppressions_set = set(config.rules.suppressions)

    filtered: List[Finding] = []
    seen_ids = set()

    for finding in all_findings:
        if finding.finding_id in seen_ids:
            continue

        # Check suppressions
        if finding.finding_id in suppressions_set or finding.rule_id in suppressions_set:
            continue

        # Check severity threshold
        score = SEVERITY_ORDER.get(finding.severity, 1)
        if score < min_threshold_score:
            continue

        seen_ids.add(finding.finding_id)
        filtered.append(finding)

    # Sort deterministically by severity (highest first), then path, then line
    filtered.sort(
        key=lambda f: (-SEVERITY_ORDER.get(f.severity, 0), f.file_path, f.line_number or 0)
    )

    return filtered
