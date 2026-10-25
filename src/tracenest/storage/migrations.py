"""Schema definitions and database migrations for TraceNest storage."""

import sqlite3
from typing import Tuple

CURRENT_SCHEMA_VERSION = 1

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        repo_root TEXT NOT NULL,
        git_commit TEXT,
        git_branch TEXT,
        label TEXT,
        note TEXT,
        working_tree_fingerprint TEXT NOT NULL,
        file_count INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        repo_root TEXT NOT NULL,
        repo_id TEXT NOT NULL,
        baseline_ref TEXT NOT NULL,
        comparison_method TEXT NOT NULL,
        status TEXT NOT NULL,
        labels_json TEXT NOT NULL,
        notes TEXT NOT NULL,
        ai_summary TEXT,
        test_status TEXT,
        report_paths_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS file_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        path TEXT NOT NULL,
        old_path TEXT,
        change_type TEXT NOT NULL,
        additions INTEGER NOT NULL DEFAULT 0,
        deletions INTEGER NOT NULL DEFAULT 0,
        is_binary INTEGER NOT NULL DEFAULT 0,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        diff_text TEXT NOT NULL DEFAULT '',
        old_hash TEXT,
        new_hash TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        finding_id TEXT NOT NULL,
        rule_id TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        explanation TEXT NOT NULL,
        file_path TEXT NOT NULL,
        line_number INTEGER,
        evidence TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        confidence TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_repo ON sessions(repo_id);
    CREATE INDEX IF NOT EXISTS idx_changes_session ON file_changes(session_id);
    CREATE INDEX IF NOT EXISTS idx_findings_session ON findings(session_id);
    """
}


def apply_migrations(conn: sqlite3.Connection) -> Tuple[int, int]:
    """Apply schema migrations transactionally."""
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_version = row[0] if (row and row[0] is not None) else 0

    applied_count = 0
    for v in sorted(MIGRATIONS.keys()):
        if v > current_version:
            cursor.executescript(MIGRATIONS[v])
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
                (v,),
            )
            applied_count += 1

    conn.commit()
    return current_version, CURRENT_SCHEMA_VERSION
