"""Custom exceptions for TraceNest."""

from typing import Optional


class TraceNestError(Exception):
    """Base exception for all TraceNest errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class GitError(TraceNestError):
    """Raised when a Git command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: Optional[str] = None):
        super().__init__(message, details=stderr)
        self.returncode = returncode
        self.stderr = stderr or ""


class GitNotFoundError(GitError):
    """Raised when Git executable cannot be found in PATH."""


class GitRepositoryError(GitError):
    """Raised when the specified directory is not a valid Git repository."""


class ConfigurationError(TraceNestError):
    """Raised when configuration file is invalid or missing required settings."""


class SessionError(TraceNestError):
    """Base class for session-related errors."""


class SessionNotFoundError(SessionError):
    """Raised when a specified session ID does not exist."""


class SnapshotNotFoundError(SessionError):
    """Raised when a specified snapshot ID or baseline does not exist."""


class IncompatibleSessionError(SessionError):
    """Raised when attempting to compare sessions with incompatible baselines or versions."""


class StorageError(TraceNestError):
    """Raised on local database or file storage failure."""


class DatabaseCorruptionError(StorageError):
    """Raised when the SQLite database is corrupted."""


class SchemaVersionError(StorageError):
    """Raised when the database schema version is incompatible."""


class ProviderError(TraceNestError):
    """Raised when an AI provider fails to generate an explanation."""


class ProviderTimeoutError(ProviderError):
    """Raised when an AI provider request times out."""


class ProviderAuthError(ProviderError):
    """Raised when AI provider authentication fails."""


class DataSharingNotAllowedError(ProviderError):
    """Raised when external data sharing is disabled but a remote provider is called."""


class FileScopeError(TraceNestError):
    """Raised when file path violates configured scope boundaries."""


class FileTooLargeError(TraceNestError):
    """Raised when a file exceeds the maximum configured analysis size."""
