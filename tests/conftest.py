"""Pytest fixtures for TraceNest tests."""

import subprocess
from pathlib import Path

import pytest

from tracenest.config import TraceNestConfig


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Fixture that initializes a temporary clean Git repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git safely
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = repo / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True, capture_output=True
    )

    return repo


@pytest.fixture
def non_git_dir(tmp_path: Path) -> Path:
    """Fixture that creates an empty directory without a Git repository."""
    d = tmp_path / "plain_dir"
    d.mkdir()
    return d


@pytest.fixture
def sample_config() -> TraceNestConfig:
    """Fixture providing a default TraceNest configuration."""
    return TraceNestConfig()
