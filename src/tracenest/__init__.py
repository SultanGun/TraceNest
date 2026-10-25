"""TraceNest - Understand every change your AI agent makes.

A production-minded, cross-platform, open-source CLI tool for reviewing
changes made during AI-assisted coding sessions.
"""

__version__ = "0.1.0"
__product_name__ = "TraceNest"
__author__ = "TraceNest Maintainers"
__license__ = "MIT"

from tracenest.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingSeverity,
    SessionMetadata,
    Snapshot,
)

__all__ = [
    "__version__",
    "ChangeType",
    "FileChange",
    "Finding",
    "FindingSeverity",
    "SessionMetadata",
    "Snapshot",
]
