"""Unit tests for cross-session comparison engine."""

from tracenest.core.sessions import compare_sessions
from tracenest.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingSeverity,
    SessionMetadata,
)


def test_compare_sessions_delta():
    # Session A: has file1 and file2, with finding1
    session_a = SessionMetadata(
        session_id="sess_a",
        created_at="2026-10-24T10:00:00Z",
        repo_root="/repo",
        repo_id="repo_1",
        baseline_ref="main",
        comparison_method="git_diff",
        file_changes=[
            FileChange(
                path="file1.py",
                change_type=ChangeType.MODIFIED,
                additions=5,
                deletions=2,
                diff_text="A",
            ),
            FileChange(
                path="file2.py",
                change_type=ChangeType.ADDED,
                additions=10,
                deletions=0,
                diff_text="B",
            ),
        ],
        findings=[
            Finding(
                finding_id="FND-001",
                rule_id="SEC-001",
                severity=FindingSeverity.HIGH,
                title="Finding 1",
                explanation="Old issue",
                file_path="file1.py",
                line_number=2,
            )
        ],
    )

    # Session B: file2 removed, file3 added, file1 modified more; finding1 resolved, finding2 introduced
    session_b = SessionMetadata(
        session_id="sess_b",
        created_at="2026-10-24T11:00:00Z",
        repo_root="/repo",
        repo_id="repo_1",
        baseline_ref="main",
        comparison_method="git_diff",
        file_changes=[
            FileChange(
                path="file1.py",
                change_type=ChangeType.MODIFIED,
                additions=8,
                deletions=3,
                diff_text="A2",
            ),
            FileChange(
                path="file3.py",
                change_type=ChangeType.ADDED,
                additions=20,
                deletions=0,
                diff_text="C",
            ),
        ],
        findings=[
            Finding(
                finding_id="FND-002",
                rule_id="SEC-002",
                severity=FindingSeverity.CRITICAL,
                title="Finding 2",
                explanation="New issue",
                file_path="file3.py",
                line_number=10,
            )
        ],
    )

    result = compare_sessions(session_a, session_b)
    assert result.baseline_compatible is True
    assert result.files_added == ["file3.py"]
    assert result.files_removed == ["file2.py"]
    assert result.files_modified == ["file1.py"]

    assert len(result.new_findings) == 1
    assert result.new_findings[0].finding_id == "FND-002"

    assert len(result.resolved_findings) == 1
    assert result.resolved_findings[0].finding_id == "FND-001"


def test_compare_incompatible_sessions_warning():
    sess_a = SessionMetadata(
        session_id="sess_a",
        created_at="2026-10-24T10:00:00Z",
        repo_root="/repo1",
        repo_id="repo_1",
        baseline_ref="main",
        comparison_method="git_diff",
    )
    sess_b = SessionMetadata(
        session_id="sess_b",
        created_at="2026-10-24T11:00:00Z",
        repo_root="/repo2",
        repo_id="repo_2",  # Different repo ID
        baseline_ref="feat/branch",
        comparison_method="git_diff",
    )

    result = compare_sessions(sess_a, sess_b)
    assert result.baseline_compatible is False
    assert any("Repository IDs do not match" in w for w in result.warnings)
    assert any("Baselines differ" in w for w in result.warnings)
