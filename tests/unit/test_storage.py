"""Unit tests for SQLite database storage and migrations."""

from pathlib import Path

import pytest

from tracenest.exceptions import (
    DatabaseCorruptionError,
    SessionNotFoundError,
    SnapshotNotFoundError,
)
from tracenest.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingSeverity,
    SessionMetadata,
    Snapshot,
)
from tracenest.storage.database import Database, ensure_storage_dir


def test_ensure_storage_dir_and_gitignore(tmp_path: Path):
    s_dir = ensure_storage_dir(tmp_path, ".tracenest")
    assert s_dir.is_dir()

    gi = s_dir / ".gitignore"
    assert gi.is_file()
    assert "*" in gi.read_text(encoding="utf-8")


def test_save_and_get_snapshot(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    snap = Snapshot(
        snapshot_id="snap_20261024_001",
        created_at="2026-10-24T00:00:00Z",
        repo_root=str(tmp_path),
        git_commit="abcdef123456",
        git_branch="main",
        label="test-snap",
        note="note",
        working_tree_fingerprint="1234567890abcdef",
        file_count=10,
    )
    db.save_snapshot(snap)

    loaded = db.get_snapshot("snap_20261024_001")
    assert loaded.snapshot_id == snap.snapshot_id
    assert loaded.git_commit == "abcdef123456"
    assert loaded.file_count == 10


def test_snapshot_not_found(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    with pytest.raises(SnapshotNotFoundError):
        db.get_snapshot("non_existent_snapshot")


def test_save_and_retrieve_session(tmp_path: Path):
    db = Database(tmp_path / "test.db")

    session = SessionMetadata(
        session_id="sess_test_1",
        created_at="2026-10-24T01:00:00Z",
        repo_root=str(tmp_path),
        repo_id="repo123",
        baseline_ref="main",
        comparison_method="git_diff",
        status="completed",
        file_changes=[
            FileChange(
                path="app.py",
                change_type=ChangeType.MODIFIED,
                additions=10,
                deletions=2,
                diff_text="+code",
            )
        ],
        findings=[
            Finding(
                finding_id="FND-001",
                rule_id="SEC-AWS-KEY",
                severity=FindingSeverity.CRITICAL,
                title="AWS Key Found",
                explanation="Exposed key",
                file_path="app.py",
                line_number=5,
                evidence="AKIA...",
                recommendation="Revoke",
                confidence="HIGH",
            )
        ],
        labels=["feature-x"],
        notes="A test session",
    )

    db.save_session(session)

    loaded = db.get_session("sess_test_1")
    assert loaded.session_id == "sess_test_1"
    assert len(loaded.file_changes) == 1
    assert loaded.file_changes[0].path == "app.py"
    assert len(loaded.findings) == 1
    assert loaded.findings[0].severity == FindingSeverity.CRITICAL


def test_session_not_found(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    with pytest.raises(SessionNotFoundError):
        db.get_session("invalid_session_id")


def test_corrupted_database(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.db"
    corrupt_file.write_bytes(b"not a valid sqlite file header garbage")

    with pytest.raises(DatabaseCorruptionError):
        Database(corrupt_file)
