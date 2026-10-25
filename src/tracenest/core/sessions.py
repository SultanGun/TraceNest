"""Session lifecycle orchestration and session comparison logic."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from tracenest.config import TraceNestConfig
from tracenest.core.diff import analyze_repository_changes
from tracenest.core.snapshots import get_git_head, get_repo_identifier
from tracenest.models import (
    ComparisonResult,
    SessionMetadata,
)
from tracenest.scanners.rules import run_all_scanners
from tracenest.scanners.secrets import redact_text
from tracenest.storage.database import Database


def create_review_session(
    repo_root: Path,
    config: TraceNestConfig,
    db: Database,
    baseline_ref: Optional[str] = None,
    comparison_method: str = "git_diff_working_tree",
    labels: Optional[List[str]] = None,
    notes: str = "",
    ai_summary: Optional[str] = None,
    test_status: Optional[str] = None,
) -> SessionMetadata:
    """Analyze current working tree against baseline and persist a new review session."""
    effective_baseline = baseline_ref or get_git_head(repo_root) or "INITIAL_TREE"
    repo_id = get_repo_identifier(repo_root)

    # 1. Analyze working tree changes
    changes = analyze_repository_changes(
        repo_root=repo_root,
        config=config,
        baseline_commit=effective_baseline if effective_baseline != "INITIAL_TREE" else None,
    )

    # 2. Run deterministic scanners
    findings = run_all_scanners(changes, config)

    # 3. Redact sensitive values from diff_text before persistence or export
    for change in changes:
        if change.diff_text:
            change.diff_text = redact_text(change.diff_text)

    # 4. Create SessionMetadata
    now_utc = datetime.now(timezone.utc).isoformat()
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_id = f"sess_{timestamp_slug}_{uuid.uuid4().hex[:6]}"

    session = SessionMetadata(
        session_id=session_id,
        created_at=now_utc,
        repo_root=str(repo_root),
        repo_id=repo_id,
        baseline_ref=effective_baseline,
        comparison_method=comparison_method,
        status="completed",
        file_changes=changes,
        findings=findings,
        labels=labels or [],
        notes=notes,
        ai_summary=ai_summary,
        test_status=test_status,
        report_paths={},
    )

    db.save_session(session)
    return session


def compare_sessions(
    session_a: SessionMetadata,
    session_b: SessionMetadata,
) -> ComparisonResult:
    """Compare two recorded review sessions and calculate delta in changes and findings."""
    warnings: List[str] = []
    baseline_compatible = True

    if session_a.repo_id != session_b.repo_id:
        baseline_compatible = False
        warnings.append(
            f"Repository IDs do not match (Session A: {session_a.repo_id}, Session B: {session_b.repo_id}). "
            "Comparison may not be meaningful."
        )

    if session_a.baseline_ref != session_b.baseline_ref:
        warnings.append(
            f"Baselines differ between sessions: '{session_a.baseline_ref}' vs '{session_b.baseline_ref}'. "
            "Findings and diffs reflect differing reference points."
        )

    files_a = {c.path: c for c in session_a.file_changes}
    files_b = {c.path: c for c in session_b.file_changes}

    files_added_in_b = sorted(list(set(files_b.keys()) - set(files_a.keys())))
    files_removed_in_b = sorted(list(set(files_a.keys()) - set(files_b.keys())))
    common_files = set(files_a.keys()) & set(files_b.keys())

    files_modified: List[str] = []
    for p in sorted(common_files):
        ca = files_a[p]
        cb = files_b[p]
        if (
            (ca.additions != cb.additions)
            or (ca.deletions != cb.deletions)
            or (ca.diff_text != cb.diff_text)
        ):
            files_modified.append(p)

    findings_a_map = {f.finding_id: f for f in session_a.findings}
    findings_b_map = {f.finding_id: f for f in session_b.findings}

    new_finding_ids = set(findings_b_map.keys()) - set(findings_a_map.keys())
    resolved_finding_ids = set(findings_a_map.keys()) - set(findings_b_map.keys())
    persistent_ids = set(findings_a_map.keys()) & set(findings_b_map.keys())

    new_findings = [findings_b_map[fid] for fid in new_finding_ids]
    resolved_findings = [findings_a_map[fid] for fid in resolved_finding_ids]
    persistent_findings = [findings_b_map[fid] for fid in persistent_ids]

    summary: Dict[str, object] = {
        "session_a": {
            "id": session_a.session_id,
            "created_at": session_a.created_at,
            "file_count": len(session_a.file_changes),
            "findings_count": len(session_a.findings),
        },
        "session_b": {
            "id": session_b.session_id,
            "created_at": session_b.created_at,
            "file_count": len(session_b.file_changes),
            "findings_count": len(session_b.findings),
        },
        "net_file_change": len(session_b.file_changes) - len(session_a.file_changes),
        "net_findings_change": len(session_b.findings) - len(session_a.findings),
    }

    return ComparisonResult(
        session_a_id=session_a.session_id,
        session_b_id=session_b.session_id,
        baseline_compatible=baseline_compatible,
        warnings=warnings,
        files_added=files_added_in_b,
        files_removed=files_removed_in_b,
        files_modified=files_modified,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        persistent_findings=persistent_findings,
        summary=summary,
    )
