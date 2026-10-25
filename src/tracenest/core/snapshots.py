"""Git repository inspection and snapshot baseline management."""

import hashlib
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from tracenest.exceptions import GitError, GitNotFoundError, GitRepositoryError
from tracenest.models import Snapshot


def run_git_command(
    args: List[str],
    cwd: Optional[Path] = None,
    timeout: float = 20.0,
) -> Tuple[int, str, str]:
    """Execute a git command safely with subprocess argument arrays (never shell=True)."""
    work_dir = cwd or Path.cwd()
    cmd = ["git"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        raise GitNotFoundError("Git executable not found in system PATH. Ensure Git is installed.")
    except subprocess.TimeoutExpired:
        raise GitError(f"Git command timed out after {timeout} seconds: {' '.join(cmd)}")
    except Exception as e:
        raise GitError(f"Unexpected error executing git command {' '.join(cmd)}: {e}")


def get_git_root(start_dir: Optional[Path] = None) -> Path:
    """Detect and return the repository top-level root directory."""
    work_dir = start_dir or Path.cwd()
    code, stdout, stderr = run_git_command(["rev-parse", "--show-toplevel"], cwd=work_dir)
    if code != 0:
        raise GitRepositoryError(
            f"Directory is not part of a Git repository: {work_dir}",
            returncode=code,
            stderr=stderr.strip(),
        )
    root_str = stdout.strip()
    return Path(root_str).resolve()


def get_git_head(repo_root: Path) -> Optional[str]:
    """Get current HEAD commit hash, or None if the repository has no commits yet."""
    code, stdout, _ = run_git_command(["rev-parse", "HEAD"], cwd=repo_root)
    if code == 0 and stdout.strip():
        return stdout.strip()
    return None


def get_git_branch(repo_root: Path) -> Optional[str]:
    """Get the current checked-out branch name or symbolic ref."""
    code, stdout, _ = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if code == 0 and stdout.strip():
        branch = stdout.strip()
        return branch if branch != "HEAD" else "detached"
    return None


def get_repo_identifier(repo_root: Path) -> str:
    """Generate a stable, anonymous repository identifier based on the root path."""
    resolved = str(repo_root.resolve()).encode("utf-8")
    return hashlib.sha256(resolved).hexdigest()[:16]


def compute_working_tree_fingerprint(
    repo_root: Path, exclude_names: Optional[List[str]] = None
) -> Tuple[str, int]:
    """Compute a deterministic SHA-256 fingerprint of the current working tree state.

    Collects file relative paths, file sizes, and modification timestamps for all
    non-excluded files without reading their full contents into memory.
    """
    excludes = set(
        exclude_names or [".git", ".tracenest", "node_modules", "__pycache__", ".venv", "venv"]
    )
    hasher = hashlib.sha256()
    file_count = 0

    # Walk directory deterministically sorted
    for root, dirs, files in os.walk(str(repo_root)):
        # Prune excluded directories in-place
        dirs[:] = sorted([d for d in dirs if d not in excludes and not d.startswith(".tracenest")])
        for file in sorted(files):
            file_path = Path(root) / file
            try:
                rel_path = file_path.relative_to(repo_root).as_posix()
                if any(part in excludes for part in Path(rel_path).parts):
                    continue
                stat = file_path.stat()
                file_info = f"{rel_path}:{stat.st_size}:{int(stat.st_mtime)}\n"
                hasher.update(file_info.encode("utf-8", errors="replace"))
                file_count += 1
            except (OSError, ValueError):
                continue

    return hasher.hexdigest(), file_count


def create_snapshot(
    repo_root: Path,
    label: Optional[str] = None,
    note: Optional[str] = None,
    exclude_paths: Optional[List[str]] = None,
) -> Snapshot:
    """Capture a baseline snapshot of the repository."""
    root = get_git_root(repo_root)
    commit = get_git_head(root)
    branch = get_git_branch(root)
    fingerprint, count = compute_working_tree_fingerprint(root, exclude_paths)

    now_utc = datetime.now(timezone.utc).isoformat()
    random_suffix = uuid.uuid4().hex[:6]
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snap_{timestamp_slug}_{random_suffix}"

    return Snapshot(
        snapshot_id=snapshot_id,
        created_at=now_utc,
        repo_root=str(root),
        git_commit=commit,
        git_branch=branch,
        label=label,
        note=note,
        working_tree_fingerprint=fingerprint,
        file_count=count,
    )
