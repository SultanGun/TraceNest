"""Unit tests for core data models."""

from tracenest.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingSeverity,
    SessionMetadata,
)


def test_models_serialization():
    change = FileChange(
        path="src/main.py",
        change_type=ChangeType.MODIFIED,
        additions=5,
        deletions=2,
        is_binary=False,
        size_bytes=120,
        diff_text="+print('hello')\n",
    )
    dumped = change.model_dump()
    assert dumped["path"] == "src/main.py"
    assert dumped["change_type"] == "modified"
    assert dumped["additions"] == 5

    finding = Finding(
        finding_id="FND-12345678",
        rule_id="SEC-001",
        severity=FindingSeverity.CRITICAL,
        title="Test Secret",
        explanation="Secret found",
        file_path="src/main.py",
        line_number=10,
        evidence="api_key = '[REDACTED]'",
        recommendation="Revoke",
        confidence="HIGH",
    )
    f_dumped = finding.model_dump()
    assert f_dumped["severity"] == "CRITICAL"
    assert f_dumped["finding_id"] == "FND-12345678"


def test_session_metadata_structure():
    session = SessionMetadata(
        session_id="sess_123",
        created_at="2026-10-24T00:00:00Z",
        repo_root="/repo",
        repo_id="abc12345",
        baseline_ref="main",
        comparison_method="git_diff",
        status="completed",
        file_changes=[],
        findings=[],
        labels=["test"],
        notes="note",
    )
    assert session.session_id == "sess_123"
    assert session.test_status is None
    assert len(session.file_changes) == 0
