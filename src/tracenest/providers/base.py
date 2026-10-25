"""Base abstraction and security guards for optional AI providers."""

import ipaddress
import urllib.parse
from abc import ABC, abstractmethod
from typing import List

from tracenest.config import AIConfig
from tracenest.models import Finding
from tracenest.scanners.secrets import redact_line


class AIProvider(ABC):
    """Abstract base class for all AI explanation providers."""

    def __init__(self, config: AIConfig):
        self.config = config

    @abstractmethod
    def explain_changes(self, diff_summary: str, findings: List[Finding]) -> str:
        """Generate an advisory summary of changed files and findings."""

    def prepare_sanitized_prompt(self, diff_summary: str, findings: List[Finding]) -> str:
        """Sanitize and truncate context before dispatching to any model."""
        # 1. Redact any accidental secret patterns in the diff summary
        sanitized_diff_lines = [redact_line(line) for line in diff_summary.splitlines()]
        clean_diff = "\n".join(sanitized_diff_lines)

        # 2. Limit input token size heuristic (~4 chars per token)
        max_chars = self.config.max_input_tokens * 4
        if len(clean_diff) > max_chars:
            clean_diff = (
                clean_diff[:max_chars] + "\n... [Diff truncated to satisfy max_input_tokens limit]"
            )

        # 3. Format findings summary
        findings_bullets = []
        for f in findings:
            findings_bullets.append(
                f"- [{f.severity.value}] {f.title} at {f.file_path}:{f.line_number or ''}"
            )
        findings_text = (
            "\n".join(findings_bullets)
            if findings_bullets
            else "No deterministic policy violations."
        )

        prompt = (
            "You are an AI session reviewer assistant for TraceNest.\n"
            "Review the following sanitized repository change summary and deterministic findings.\n"
            "Provide a concise, 2-3 paragraph objective explanation answering:\n"
            "1. What is the overarching intent of the changes made by the AI agent?\n"
            "2. Which specific changes carry the highest operational or security risk?\n"
            "3. What manual smoke test or verification step is recommended?\n\n"
            f"Findings Detected:\n{findings_text}\n\n"
            f"Diff Summary:\n{clean_diff}\n\n"
            "Respond in clear Markdown paragraphs without preamble."
        )
        return prompt


def is_local_endpoint(url: str) -> bool:
    """Check if the provided URL points safely to a local loopback address.

    Strict validation prevents SSRF, remote data leakage, and hostname/IP bypasses:
    - Only 'http' and 'https' schemes are accepted.
    - Userinfo (username/password) is rejected.
    - Hostname must be strictly 'localhost', 'localhost.localdomain', end with '.localhost',
      or resolve to an IPv4/IPv6 loopback address (127.0.0.0/8, ::1).
    - Link-local (e.g. AWS IMDS 169.254.169.254), private ranges (10.x, 192.168.x),
      and unspecified 0.0.0.0 are rejected.
    """
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    if parsed.username or parsed.password:
        return False

    host = parsed.hostname
    if not host:
        return False

    host_lower = host.lower().strip("[]").rstrip(".")

    # Standard loopback domain names per RFC 6761
    if host_lower in {"localhost", "localhost.localdomain"} or host_lower.endswith(".localhost"):
        return True

    try:
        ip = ipaddress.ip_address(host_lower)
        return ip.is_loopback
    except ValueError:
        return False
