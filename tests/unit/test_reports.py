"""Unit tests for Markdown and JSON report generation."""

import json
from pathlib import Path

from tracenest.core.report import (
    REPORT_SCHEMA_VERSION,
    generate_json_report,
    generate_markdown_report,
    save_reports,
)
from tracenest.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingSeverity,
    SessionMetadata,
)


def create_sample_session() -> SessionMetadata:
    return SessionMetadata(
        session_id="sess_rep_001",
        created_at="2026-10-24T12:00:00Z",
        repo_root="/workspace/app",
        repo_id="repoid123",
        baseline_ref="v1.0.0",
        comparison_method="git_diff_working_tree",
        status="completed",
        file_changes=[
            FileChange(
                path="src/app.py",
                change_type=ChangeType.MODIFIED,
                additions=15,
                deletions=3,
                diff_text="+new_code()",
            ),
            FileChange(
                path="assets/logo.png",
                change_type=ChangeType.ADDED,
                is_binary=True,
                size_bytes=1024,
            ),
        ],
        findings=[
            Finding(
                finding_id="FND-001",
                rule_id="SEC-GH-TOKEN",
                severity=FindingSeverity.CRITICAL,
                title="GitHub Token Detected",
                explanation="A GitHub personal access token was introduced.",
                file_path="src/app.py",
                line_number=12,
                evidence="ghp_***[REDACTED]***",
                recommendation="Revoke token.",
                confidence="HIGH",
            )
        ],
        ai_summary="AI Summary: Code refactored successfully.",
    )


def test_generate_markdown_report():
    session = create_sample_session()
    md = generate_markdown_report(session)

    assert "# TraceNest Review Report" in md
    assert "sess_rep_001" in md
    assert "src/app.py" in md
    assert "(binary)" in md
    assert "[CRITICAL] GitHub Token Detected" in md
    assert "AI-Assisted Advisory Explanation" in md
    assert "Analysis Disclaimer" in md


def test_generate_json_report():
    session = create_sample_session()
    json_str = generate_json_report(session)
    data = json.loads(json_str)

    assert data["$schema_version"] == REPORT_SCHEMA_VERSION
    assert data["session"]["session_id"] == "sess_rep_001"
    assert data["metrics"]["files_changed_count"] == 2
    assert data["metrics"]["findings_count"] == 1
    assert data["metrics"]["findings_by_severity"]["CRITICAL"] == 1
    assert len(data["file_changes"]) == 2
    assert len(data["findings"]) == 1


def test_save_reports_to_disk(tmp_path: Path):
    session = create_sample_session()
    paths = save_reports(session, tmp_path, formats=["markdown", "json"])

    assert "markdown" in paths
    assert "json" in paths
    assert Path(paths["markdown"]).is_file()
    assert Path(paths["json"]).is_file()
