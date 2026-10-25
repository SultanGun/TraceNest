"""Unit tests for Git repository inspection and snapshot baseline creation."""

import subprocess
from pathlib import Path

import pytest

from tracenest.core.snapshots import (
    compute_working_tree_fingerprint,
    create_snapshot,
    get_git_branch,
    get_git_head,
    get_git_root,
)
from tracenest.exceptions import GitRepositoryError


def test_get_git_root_success(temp_git_repo: Path):
    root = get_git_root(temp_git_repo)
    assert root == temp_git_repo.resolve()


def test_get_git_root_in_subdirectory(temp_git_repo: Path):
    sub = temp_git_repo / "sub" / "folder"
    sub.mkdir(parents=True)
    root = get_git_root(sub)
    assert root == temp_git_repo.resolve()


def test_get_git_root_non_git(non_git_dir: Path):
    with pytest.raises(GitRepositoryError):
        get_git_root(non_git_dir)


def test_get_git_head_and_branch(temp_git_repo: Path):
    head = get_git_head(temp_git_repo)
    assert head is not None
    assert len(head) == 40

    branch = get_git_branch(temp_git_repo)
    assert branch is not None
    assert branch in {"main", "master"}


def test_fingerprint_deterministic(temp_git_repo: Path):
    fp1, count1 = compute_working_tree_fingerprint(temp_git_repo)
    fp2, count2 = compute_working_tree_fingerprint(temp_git_repo)
    assert fp1 == fp2
    assert count1 == count2
    assert count1 >= 1


def test_create_snapshot(temp_git_repo: Path):
    snap = create_snapshot(
        repo_root=temp_git_repo,
        label="test-baseline",
        note="A unit test snapshot",
    )
    assert snap.snapshot_id.startswith("snap_")
    assert snap.label == "test-baseline"
    assert snap.note == "A unit test snapshot"
    assert snap.git_commit is not None
    assert len(snap.working_tree_fingerprint) == 64


def test_repo_with_no_commits(tmp_path: Path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(empty_repo), check=True, capture_output=True)

    head = get_git_head(empty_repo)
    assert head is None

    snap = create_snapshot(empty_repo)
    assert snap.git_commit is None
    assert snap.file_count == 0
