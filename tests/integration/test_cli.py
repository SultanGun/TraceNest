"""Integration tests for TraceNest Typer CLI workflows."""

from pathlib import Path

from typer.testing import CliRunner

from tracenest.cli import app

runner = CliRunner()


def test_cli_help_and_version():
    res_help = runner.invoke(app, ["--help"])
    assert res_help.exit_code == 0
    assert "Understand every change your AI agent makes" in res_help.stdout

    res_ver = runner.invoke(app, ["--version"])
    assert res_ver.exit_code == 0
    assert "v0.1.0" in res_ver.stdout


def test_cli_init_and_status(temp_git_repo: Path):
    res_init = runner.invoke(app, ["init", "--path", str(temp_git_repo)])
    assert res_init.exit_code == 0
    assert "TraceNest initialized successfully" in res_init.stdout

    # Verify storage directory and files
    assert (temp_git_repo / ".tracenest").is_dir()
    assert (temp_git_repo / ".tracenest" / "tracenest.db").is_file()
    assert (temp_git_repo / "tracenest.toml").is_file()

    # Status check
    res_status = runner.invoke(app, ["status", "--path", str(temp_git_repo)])
    assert res_status.exit_code == 0
    assert "TraceNest Repository Status" in res_status.stdout


def test_cli_init_non_git_fails(non_git_dir: Path):
    res = runner.invoke(app, ["init", "--path", str(non_git_dir)])
    assert res.exit_code == 1
    output = (res.stdout or "") + (res.stderr or "")
    assert "not part of a Git repository" in output or "Initialization Error" in output


def test_cli_snapshot_lifecycle(temp_git_repo: Path):
    runner.invoke(app, ["init", "--path", str(temp_git_repo)])

    res_snap = runner.invoke(
        app,
        [
            "snapshot",
            "create",
            "--label",
            "base-1",
            "--note",
            "pre-test",
            "--path",
            str(temp_git_repo),
        ],
    )
    assert res_snap.exit_code == 0
    assert "Baseline Snapshot Created" in res_snap.stdout

    res_list = runner.invoke(app, ["snapshot", "list", "--path", str(temp_git_repo)])
    assert res_list.exit_code == 0
    assert "base-1" in res_list.stdout


def test_cli_review_and_report_lifecycle(temp_git_repo: Path):
    runner.invoke(app, ["init", "--path", str(temp_git_repo)])

    # Introduce a change in repository
    feature_file = temp_git_repo / "feature.py"
    original_content = "def calculate():\n    return 42\n"
    feature_file.write_text(original_content, encoding="utf-8")

    # Run review
    res_review = runner.invoke(
        app, ["review", "--path", str(temp_git_repo), "--note", "Implemented feature"]
    )
    assert res_review.exit_code == 0
    assert "Changed Files" in res_review.stdout
    assert "feature.py" in res_review.stdout

    # Verify user's file was NOT modified, deleted, or cleaned!
    assert feature_file.read_text(encoding="utf-8") == original_content

    # Export report
    res_report = runner.invoke(app, ["report", "--path", str(temp_git_repo), "--format", "json"])
    assert res_report.exit_code == 0
    assert '"$schema_version": "tracenest-report-v1"' in res_report.stdout


def test_cli_compare(temp_git_repo: Path):
    runner.invoke(app, ["init", "--path", str(temp_git_repo)])

    # Step 1: add file1
    (temp_git_repo / "step1.txt").write_text("step 1\n", encoding="utf-8")
    runner.invoke(app, ["review", "--path", str(temp_git_repo), "--label", "step1"])

    # Step 2: add file2
    (temp_git_repo / "step2.txt").write_text("step 2\n", encoding="utf-8")
    runner.invoke(app, ["review", "--path", str(temp_git_repo), "--label", "step2"])

    # Query sessions from database
    from tracenest.storage.database import Database

    db = Database(temp_git_repo / ".tracenest" / "tracenest.db")
    sessions = db.list_sessions()
    assert len(sessions) >= 2
    sess_b = sessions[0].session_id
    sess_a = sessions[1].session_id

    res_comp = runner.invoke(app, ["compare", sess_a, sess_b, "--path", str(temp_git_repo)])
    assert res_comp.exit_code == 0
    assert "Session Comparison" in res_comp.stdout
