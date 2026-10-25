"""Unit tests for deterministic diff engine and change analysis."""

import subprocess
from pathlib import Path

from tracenest.config import TraceNestConfig
from tracenest.core.diff import (
    analyze_repository_changes,
    is_path_safe,
)
from tracenest.models import ChangeType


def test_clean_repository(temp_git_repo: Path, sample_config: TraceNestConfig):
    changes = analyze_repository_changes(temp_git_repo, sample_config)
    assert len(changes) == 0


def test_staged_and_unstaged_changes(temp_git_repo: Path, sample_config: TraceNestConfig):
    # Staged change
    staged_file = temp_git_repo / "staged.txt"
    staged_file.write_text("line 1\nline 2\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "staged.txt"], cwd=str(temp_git_repo), check=True, capture_output=True
    )

    # Unstaged change in existing file
    readme = temp_git_repo / "README.md"
    readme.write_text("# Test Repo Updated\nNew line\n", encoding="utf-8")

    # Untracked file
    untracked = temp_git_repo / "untracked.py"
    untracked.write_text("x = 42\n", encoding="utf-8")

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    paths = {c.path: c for c in changes}

    assert "staged.txt" in paths
    assert paths["staged.txt"].change_type == ChangeType.ADDED
    assert paths["staged.txt"].additions == 2

    assert "README.md" in paths
    assert paths["README.md"].change_type == ChangeType.MODIFIED

    assert "untracked.py" in paths
    assert paths["untracked.py"].change_type == ChangeType.UNTRACKED
    assert paths["untracked.py"].additions == 1


def test_deleted_file(temp_git_repo: Path, sample_config: TraceNestConfig):
    # Delete README.md
    readme = temp_git_repo / "README.md"
    readme.unlink()

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    assert len(changes) == 1
    assert changes[0].path == "README.md"
    assert changes[0].change_type == ChangeType.DELETED


def test_renamed_file(temp_git_repo: Path, sample_config: TraceNestConfig):
    # Rename README.md to DOCS.md using git mv
    subprocess.run(
        ["git", "mv", "README.md", "DOCS.md"],
        cwd=str(temp_git_repo),
        check=True,
        capture_output=True,
    )

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    assert len(changes) == 1
    assert changes[0].path == "DOCS.md"
    assert changes[0].old_path == "README.md"
    assert changes[0].change_type == ChangeType.RENAMED


def test_file_with_spaces_in_path(temp_git_repo: Path, sample_config: TraceNestConfig):
    spaced_file = temp_git_repo / "my space file.txt"
    spaced_file.write_text("content inside spaces\n", encoding="utf-8")

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    paths = [c.path for c in changes]
    assert "my space file.txt" in paths


def test_non_ascii_filename(temp_git_repo: Path, sample_config: TraceNestConfig):
    unicode_file = temp_git_repo / "données_élève.txt"
    unicode_file.write_text("accented content\n", encoding="utf-8")

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    paths = [c.path for c in changes]
    assert "données_élève.txt" in paths


def test_binary_file_detection(temp_git_repo: Path, sample_config: TraceNestConfig):
    bin_file = temp_git_repo / "data.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff")

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    assert len(changes) == 1
    assert changes[0].path == "data.bin"
    assert changes[0].is_binary is True
    assert "[BINARY FILE - DIFF NOT AVAILABLE]" in changes[0].diff_text


def test_large_file_size_limit(temp_git_repo: Path):
    config = TraceNestConfig()
    config.scope.max_file_size_kb = 1  # 1 KB limit

    large_file = temp_git_repo / "large.txt"
    large_file.write_text("A" * 3000, encoding="utf-8")  # ~3KB

    changes = analyze_repository_changes(temp_git_repo, config)
    assert len(changes) == 1
    assert changes[0].path == "large.txt"
    assert "exceeds configured limit" in changes[0].diff_text


def test_ignored_directories_respected(temp_git_repo: Path, sample_config: TraceNestConfig):
    node_modules = temp_git_repo / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("console.log('vendor');\n", encoding="utf-8")

    changes = analyze_repository_changes(temp_git_repo, sample_config)
    paths = [c.path for c in changes]
    assert not any("node_modules" in p for p in paths)


def test_path_safety_traversal(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = repo / "file.txt"
    outside = tmp_path / "outside.txt"

    assert is_path_safe(repo, inside) is True
    assert is_path_safe(repo, outside) is False
