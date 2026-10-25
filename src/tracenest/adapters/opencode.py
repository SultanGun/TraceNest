"""OpenCode agent adapter providing documented snapshot-and-diff integration."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tracenest.adapters.base import AgentAdapter
from tracenest.scanners.secrets import redact_line


def _sanitize_metadata(data: Any) -> Any:
    """Recursively sanitize metadata strings to redact potential credentials."""
    if isinstance(data, dict):
        return {str(k): _sanitize_metadata(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_metadata(v) for v in data]
    elif isinstance(data, str):
        return redact_line(data)
    return data


class OpenCodeAdapter(AgentAdapter):
    """Adapter for OpenCode agent workflows.

    Integration Model:
    Because OpenCode relies on file edits and terminal tool executions within the workspace,
    TraceNest interacts with OpenCode via a documented snapshot-and-diff lifecycle.

    What TraceNest Observes:
    - Files created, modified, deleted, or renamed by OpenCode during a session.
    - Deterministic policy violations and secrets introduced into repository files.
    - Working tree state delta between task start and completion.

    What TraceNest Cannot Observe:
    - In-memory agent thoughts, prompts, or intermediate streaming reasoning.
    - Terminal commands or scripts executed that did not alter the repository filesystem.
    - External network traffic initiated by the agent.
    """

    @property
    def name(self) -> str:
        return "OpenCode"

    def is_detected(self, repo_root: Path) -> bool:
        """Detect if the workspace contains OpenCode configurations or artifacts."""
        markers = [
            repo_root / ".opencode",
            repo_root / "opencode.json",
            repo_root / ".opencode.json",
        ]
        return any(p.exists() for p in markers)

    def get_capabilities(self) -> Dict[str, bool]:
        """Explicitly declare integration observation capabilities."""
        return {
            "filesystem_diffs": True,
            "secret_detection": True,
            "scope_verification": True,
            "realtime_telemetry_streaming": False,
            "shell_execution_interception": False,
            "prompt_inspection": False,
        }

    def record_session(
        self,
        repo_root: Path,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a session reference within .opencode directory if present."""
        opencode_dir = repo_root / ".opencode"
        if opencode_dir.is_dir():
            history_file = opencode_dir / "tracenest_sessions.jsonl"
            clean_metadata = _sanitize_metadata(metadata or {})
            record = {
                "session_id": session_id,
                "metadata": clean_metadata,
            }
            try:
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
                    f.flush()
            except OSError:
                pass

    def attach_session_summary(
        self,
        repo_root: Path,
        session_id: str,
        files_changed_count: int,
        findings_count: int,
        critical_findings_count: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record structured review outcome to .opencode/tracenest_sessions.jsonl."""
        opencode_dir = repo_root / ".opencode"
        if not opencode_dir.is_dir():
            return False
        history_file = opencode_dir / "tracenest_sessions.jsonl"
        clean_metadata = _sanitize_metadata(metadata or {})
        record = {
            "session_id": session_id,
            "files_changed": files_changed_count,
            "findings_count": findings_count,
            "critical_findings_count": critical_findings_count,
            "has_critical": critical_findings_count > 0,
            "metadata": clean_metadata,
        }
        try:
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
                f.flush()
            return True
        except OSError:
            return False

    def read_session_history(self, repo_root: Path) -> List[Dict[str, Any]]:
        """Safely read session records from .opencode/tracenest_sessions.jsonl, ignoring malformed lines."""
        history_file = repo_root / ".opencode" / "tracenest_sessions.jsonl"
        if not history_file.is_file():
            return []
        records = []
        try:
            with open(history_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if isinstance(record, dict):
                            records.append(record)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            return []
        return records
