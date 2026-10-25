"""Base abstraction and security guards for optional AI providers."""

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
    """Check if the provided URL points to localhost or loopback."""
    lower = url.lower()
    return "localhost" in lower or "127.0.0.1" in lower or "::1" in lower or "0.0.0.0" in lower
