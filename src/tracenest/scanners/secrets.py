"""Secret and credential scanner with automated redaction."""

import hashlib
import re
from typing import List, Optional, Pattern, Tuple

from tracenest.models import Finding, FindingSeverity

# Regex definitions for sensitive credentials
SECRET_PATTERNS: List[Tuple[str, str, FindingSeverity, Pattern[str], str]] = [
    (
        "SEC-AWS-KEY",
        "AWS Access Key ID Detected",
        FindingSeverity.CRITICAL,
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
        "Revoke the AWS key and use AWS IAM roles or environment variables injected via secret management.",
    ),
    (
        "SEC-AWS-SECRET-KEY",
        "AWS Secret Access Key Detected",
        FindingSeverity.CRITICAL,
        re.compile(
            r"""(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*['"]?([A-Za-z0-9/+=]{40})['"]?"""
        ),
        "Revoke the AWS secret access key immediately and rotate all associated IAM credentials.",
    ),
    (
        "SEC-GH-TOKEN",
        "GitHub Personal Access Token Detected",
        FindingSeverity.CRITICAL,
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82}"),
        "Revoke the GitHub token immediately and store credentials in GitHub Actions secrets or a vault.",
    ),
    (
        "SEC-OPENAI-KEY",
        "OpenAI / LLM API Key Detected",
        FindingSeverity.CRITICAL,
        re.compile(r"sk-(?:proj-|ant-|admin-)?[a-zA-Z0-9_\-]{20,}"),
        "Revoke the API key and configure it securely via environment variables or a local secret store.",
    ),
    (
        "SEC-BEARER-TOKEN",
        "Bearer Authorization Token Detected",
        FindingSeverity.HIGH,
        re.compile(r"""(?i)\bbearer\s+([A-Za-z0-9_\-\.]{20,})"""),
        "Revoke the bearer token and inject auth headers dynamically from environment variables.",
    ),
    (
        "SEC-SLACK-TOKEN",
        "Slack Bot/User Token Detected",
        FindingSeverity.HIGH,
        re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*"),
        "Revoke the Slack token and store it in an encrypted secrets manager.",
    ),
    (
        "SEC-PRIVATE-KEY",
        "Private Cryptographic Key Header Detected",
        FindingSeverity.CRITICAL,
        re.compile(r"-----BEGIN (?:[A-Z0-9 -]+)?PRIVATE KEY"),
        "Do not commit private keys to version control. Use certificate managers or secure keyrings.",
    ),
    (
        "SEC-GENERIC-API-KEY",
        "High-Entropy Generic API Key Assignment",
        FindingSeverity.HIGH,
        re.compile(
            r"""(?i)(?:api_key|apikey|secret_key|auth_token|access_token)\s*[:=]\s*['"][A-Za-z0-9_\-]{20,}['"]"""
        ),
        "Avoid assigning secret values directly in code. Read from environment variables at runtime.",
    ),
    (
        "SEC-DB-URI",
        "Database Connection URI with Embedded Credentials",
        FindingSeverity.HIGH,
        re.compile(r"""(?i)(?:postgres|mysql|mongodb|redis|mssql):\/\/[^\s:]+:[^\s@]+@[^\s\/]+"""),
        "Remove cleartext credentials from connection strings. Use environment-based connection strings.",
    ),
    (
        "SEC-JWT-TOKEN",
        "JSON Web Token (JWT) Signature Detected",
        FindingSeverity.MEDIUM,
        re.compile(r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "Ensure transient session tokens or signatures are not hardcoded in source files or tests.",
    ),
]

FALSE_POSITIVE_KEYWORDS = {
    "example",
    "sample",
    "dummy",
    "test",
    "placeholder",
    "xxx",
    "fake",
    "changeme",
    "your-api-key",
}


def redact_secret_string(value: str) -> str:
    """Redact sensitive string completely without leaking the secret suffix."""
    if value.upper().startswith("-----BEGIN"):
        return "[REDACTED_PRIVATE_KEY]"
    if len(value) <= 8:
        return "[REDACTED]"
    # Keep only leading 3 chars for recognition context (e.g., 'sk-...', 'ghp...'), never the suffix!
    prefix = value[:3]
    return f"{prefix}...[REDACTED]"


def redact_line(line: str) -> str:
    """Scan and redact any known secret pattern occurrences from a text line."""
    redacted = line
    for _, _, _, pattern, _ in SECRET_PATTERNS:
        matches = list(pattern.finditer(redacted))
        for m in reversed(matches):
            raw = m.group(0)
            redacted = redacted[: m.start()] + redact_secret_string(raw) + redacted[m.end() :]
    return redacted


def redact_text(text: str) -> str:
    """Scan and redact any known secret pattern occurrences from multiline text."""
    if not text:
        return text
    # 1. Mask multiline private key blocks
    redacted = re.sub(
        r"-----BEGIN [A-Z0-9 -]+KEY-----[\s\S]*?-----END [A-Z0-9 -]+KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        text,
        flags=re.IGNORECASE,
    )
    # 2. Line-by-line redaction preserving trailing newline
    has_trailing_newline = redacted.endswith("\n")
    lines = [redact_line(line) for line in redacted.splitlines()]
    result = "\n".join(lines)
    if has_trailing_newline and not result.endswith("\n"):
        result += "\n"
    return result


def is_false_positive(snippet: str) -> bool:
    """Check if snippet looks like a documentation sample or dummy test key."""
    lower = snippet.lower()
    return any(fp in lower for fp in FALSE_POSITIVE_KEYWORDS)


def generate_finding_id(rule_id: str, file_path: str, line_no: Optional[int], snippet: str) -> str:
    """Generate a deterministic finding ID for stable cross-session identity tracking."""
    raw = f"{rule_id}:{file_path}:{line_no or 0}:{snippet.strip()}"
    return f"FND-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def scan_file_for_secrets(file_path: str, diff_text: str) -> List[Finding]:
    """Scan newly added lines in a diff for sensitive credentials."""
    findings: List[Finding] = []
    lines = diff_text.splitlines()

    line_counter = 0
    for line in lines:
        if line.startswith("@@"):
            # Extract starting line if available
            m = re.search(r"\+(\d+)", line)
            if m:
                line_counter = int(m.group(1)) - 1
            continue

        if line.startswith("+") and not line.startswith("+++"):
            line_counter += 1
            added_content = line[1:]

            for rule_id, title, severity, pattern, rec in SECRET_PATTERNS:
                match = pattern.search(added_content)
                if match:
                    raw_matched = match.group(0)
                    if is_false_positive(added_content):
                        continue

                    redacted_evidence = redact_line(added_content.strip())
                    finding_id = generate_finding_id(rule_id, file_path, line_counter, raw_matched)

                    findings.append(
                        Finding(
                            finding_id=finding_id,
                            rule_id=rule_id,
                            severity=severity,
                            title=title,
                            explanation=(
                                f"A pattern matching {title.lower()} was introduced in {file_path}. "
                                "Accidental commit of secrets exposes infrastructure and accounts."
                            ),
                            file_path=file_path,
                            line_number=line_counter,
                            evidence=redacted_evidence,
                            recommendation=rec,
                            confidence="HIGH",
                        )
                    )
        elif not line.startswith("-"):
            line_counter += 1

    return findings
