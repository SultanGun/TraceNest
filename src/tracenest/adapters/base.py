"""Base interface for agent framework adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class AgentEvent:
    """Normalized representation of an external agent event."""

    def __init__(
        self,
        event_type: str,
        timestamp: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.timestamp = timestamp
        self.details = details or {}


class AgentAdapter(ABC):
    """Abstract adapter interface for coding agent toolchains."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the coding agent framework."""

    @abstractmethod
    def is_detected(self, repo_root: Path) -> bool:
        """Check if agent project artifacts, configurations, or sessions exist."""

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """Return what this adapter can observe vs what it cannot observe."""

    @abstractmethod
    def record_session(
        self,
        repo_root: Path,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record or associate session metadata with the agent environment."""
