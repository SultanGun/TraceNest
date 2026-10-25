"""Data models for TraceNest session metadata, diffs, and findings."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Classification of file modifications in the working tree."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNTRACKED = "untracked"
    BINARY = "binary"
    UNKNOWN = "unknown"


class FindingSeverity(str, Enum):
    """Severity levels for deterministic review findings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FileChange(BaseModel):
    """Represents a single changed file in a review session."""

    path: str
    old_path: Optional[str] = None
    change_type: ChangeType
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False
    size_bytes: int = 0
    diff_text: str = ""
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None


class Finding(BaseModel):
    """A deterministic review finding produced by rules/scanners."""

    finding_id: str
    rule_id: str
    severity: FindingSeverity
    title: str
    explanation: str
    file_path: str
    line_number: Optional[int] = None
    evidence: str = ""
    recommendation: str = ""
    confidence: str = "HIGH"


class Snapshot(BaseModel):
    """A baseline snapshot recording repository state at a point in time."""

    snapshot_id: str
    created_at: str
    repo_root: str
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    label: Optional[str] = None
    note: Optional[str] = None
    working_tree_fingerprint: str
    file_count: int = 0


class SessionMetadata(BaseModel):
    """Comprehensive metadata for an AI coding review session."""

    session_id: str
    created_at: str
    repo_root: str
    repo_id: str
    baseline_ref: str
    comparison_method: str
    status: str = "completed"
    file_changes: List[FileChange] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    notes: str = ""
    ai_summary: Optional[str] = None
    test_status: Optional[str] = None
    report_paths: Dict[str, str] = Field(default_factory=dict)


class ComparisonResult(BaseModel):
    """Comparison between two review sessions."""

    session_a_id: str
    session_b_id: str
    baseline_compatible: bool = True
    warnings: List[str] = Field(default_factory=list)
    files_added: List[str] = Field(default_factory=list)
    files_removed: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    new_findings: List[Finding] = Field(default_factory=list)
    resolved_findings: List[Finding] = Field(default_factory=list)
    persistent_findings: List[Finding] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
