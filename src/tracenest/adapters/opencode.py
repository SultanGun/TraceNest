"""OpenCode agent adapter providing documented snapshot-and-diff integration."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from tracenest.adapters.base import AgentAdapter


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
            record = {
                "session_id": session_id,
                "metadata": metadata or {},
            }
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
