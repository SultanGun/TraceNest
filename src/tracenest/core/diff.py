"""Deterministic diff engine for repository changes and file inspection."""

import mimetypes
from pathlib import Path
from typing import List, Optional, Set, Tuple

from tracenest.config import TraceNestConfig
from tracenest.core.snapshots import get_git_head, run_git_command
from tracenest.exceptions import FileScopeError
from tracenest.models import ChangeType, FileChange

KNOWN_BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".webp",
    ".bmp",
    ".tiff",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".iso",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".pyc",
    ".pyd",
    ".pyo",
    ".class",
    ".jar",
}


def is_path_safe(base_dir: Path, target_path: Path) -> bool:
    """Check that target_path is within base_dir and does not escape via symlink or traversal."""
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return resolved_target.is_relative_to(resolved_base)
    except (ValueError, RuntimeError):
        return False


def is_binary_file(file_path: Path, max_check_bytes: int = 8192) -> bool:
    """Detect if a file is binary using extension heuristics and null-byte inspection."""
    if file_path.suffix.lower() in KNOWN_BINARY_EXTS:
        return True

    mime, _ = mimetypes.guess_type(str(file_path))
    if mime and not (
        mime.startswith("text/")
        or mime in {"application/json", "application/xml", "application/javascript"}
    ):
        if any(part in mime for part in ["octet-stream", "zip", "pdf", "image", "audio", "video"]):
            return True

    if not file_path.is_file():
        return False

    try:
        with open(file_path, "rb") as f:
            chunk = f.read(max_check_bytes)
            if b"\x00" in chunk:
                return True
    except OSError:
        return False

    return False


def count_diff_lines(diff_text: str) -> Tuple[int, int]:
    """Count additions (+) and deletions (-) in unified diff text."""
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


def filter_path_allowed(
    rel_path: str,
    include_paths: List[str],
    exclude_paths: List[str],
) -> bool:
    """Check whether a path matches configured inclusion and exclusion rules."""
    path_obj = Path(rel_path)
    parts = set(path_obj.parts)

    for exc in exclude_paths:
        clean_exc = exc.strip("/")
        if clean_exc in parts:
            return False
        if any(part.startswith(clean_exc) for part in parts):
            return False
        if clean_exc.startswith("*") and rel_path.endswith(clean_exc[1:]):
            return False

    if include_paths:
        matched = False
        for inc in include_paths:
            clean_inc = inc.strip("/")
            if clean_inc in parts or rel_path.startswith(clean_inc):
                matched = True
                break
        if not matched:
            return False

    return True


def get_file_diff(
    repo_root: Path,
    rel_path: str,
    change_type: ChangeType,
    baseline_commit: Optional[str] = None,
    max_size_bytes: int = 512 * 1024,
) -> Tuple[str, int, int, bool, int]:
    """Generate diff text, additions, deletions, binary flag, and size for a changed file."""
    full_path = repo_root / rel_path
    if not is_path_safe(repo_root, full_path):
        raise FileScopeError(f"Path traversal detected: {rel_path} escapes repo root.")

    size_bytes = 0
    if full_path.exists() and not full_path.is_symlink():
        try:
            size_bytes = full_path.stat().st_size
        except OSError:
            size_bytes = 0

    if size_bytes > max_size_bytes:
        msg = f"[DIFF OMITTED: File size {size_bytes} bytes exceeds configured limit of {max_size_bytes} bytes]"
        return msg, 0, 0, False, size_bytes

    if change_type == ChangeType.DELETED:
        # File was deleted in working tree
        if baseline_commit:
            code, stdout, _ = run_git_command(
                ["show", f"{baseline_commit}:{rel_path}"], cwd=repo_root
            )
            if code == 0:
                lines = stdout.splitlines(keepends=True)
                diff = "".join(f"-{line}" for line in lines)
                return diff, 0, len(lines), False, len(stdout.encode("utf-8", errors="replace"))
        return f"--- a/{rel_path}\n+++ /dev/null\n@@ -1 +0,0 @@\n-[deleted file]", 0, 1, False, 0

    if is_binary_file(full_path):
        return "[BINARY FILE - DIFF NOT AVAILABLE]", 0, 0, True, size_bytes

    # If it's an untracked or newly added file without git history
    if change_type in {ChangeType.UNTRACKED, ChangeType.ADDED} and not baseline_commit:
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.splitlines(keepends=True)
            diff = "".join(f"+{line}" for line in lines)
            return diff, len(lines), 0, False, size_bytes
        except OSError:
            return "", 0, 0, False, size_bytes

    # Tracked file: invoke git diff safely
    diff_args = ["diff", "-u"]
    if baseline_commit:
        diff_args.extend([baseline_commit, "--", rel_path])
    else:
        diff_args.extend(["HEAD", "--", rel_path])

    code, stdout, stderr = run_git_command(diff_args, cwd=repo_root)
    if code == 0 and stdout:
        adds, dels = count_diff_lines(stdout)
        return stdout, adds, dels, False, size_bytes

    # If git diff against HEAD failed (e.g. no commits yet), compare against empty
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.splitlines(keepends=True)
        diff = "".join(f"+{line}" for line in lines)
        return diff, len(lines), 0, False, size_bytes
    except OSError:
        return "", 0, 0, False, size_bytes


def analyze_repository_changes(
    repo_root: Path,
    config: TraceNestConfig,
    baseline_commit: Optional[str] = None,
) -> List[FileChange]:
    """Deterministically analyze all working tree changes in the repository."""
    head_commit = baseline_commit or get_git_head(repo_root)
    changes: List[FileChange] = []
    seen_paths: Set[str] = set()

    # Use null-delimited porcelain status to handle spaces, unicode, renames reliably
    code, stdout, stderr = run_git_command(
        ["status", "--porcelain=v1", "-z", "-uall"],
        cwd=repo_root,
    )

    if code != 0:
        # Fallback to empty if status fails
        return changes

    # Parse null-delimited tokens
    raw_tokens = stdout.split("\0")
    idx = 0
    while idx < len(raw_tokens):
        token = raw_tokens[idx]
        if not token:
            idx += 1
            continue

        if len(token) < 3:
            idx += 1
            continue

        status_code = token[:2]
        path_part = token[3:]
        old_path: Optional[str] = None

        if "R" in status_code or "C" in status_code:
            # In -z mode, for renames/copies, the first token is the new path, next token is original path
            current_path = path_part
            idx += 1
            if idx < len(raw_tokens):
                old_path = raw_tokens[idx]
            path_part = current_path

        idx += 1

        rel_path = path_part.replace("\\", "/")
        if not filter_path_allowed(
            rel_path, config.scope.include_paths, config.scope.exclude_paths
        ):
            continue

        seen_paths.add(rel_path)

        # Determine ChangeType
        if status_code == "??":
            change_type = ChangeType.UNTRACKED
        elif "D" in status_code:
            change_type = ChangeType.DELETED
        elif "R" in status_code:
            change_type = ChangeType.RENAMED
        elif "A" in status_code:
            change_type = ChangeType.ADDED
        elif "M" in status_code:
            change_type = ChangeType.MODIFIED
        else:
            change_type = ChangeType.MODIFIED

        try:
            diff_text, adds, dels, is_bin, size = get_file_diff(
                repo_root=repo_root,
                rel_path=rel_path,
                change_type=change_type,
                baseline_commit=head_commit,
                max_size_bytes=config.scope.max_file_size_kb * 1024,
            )
            changes.append(
                FileChange(
                    path=rel_path,
                    old_path=old_path.replace("\\", "/") if old_path else None,
                    change_type=change_type,
                    additions=adds,
                    deletions=dels,
                    is_binary=is_bin,
                    size_bytes=size,
                    diff_text=diff_text,
                )
            )
        except FileScopeError as fse:
            changes.append(
                FileChange(
                    path=rel_path,
                    old_path=old_path.replace("\\", "/") if old_path else None,
                    change_type=change_type,
                    additions=0,
                    deletions=0,
                    is_binary=False,
                    size_bytes=0,
                    diff_text=f"[SECURITY ALERT: {fse}]",
                )
            )
        except Exception:
            continue

    return sorted(changes, key=lambda c: c.path)
