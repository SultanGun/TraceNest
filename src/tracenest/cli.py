"""Typer-based command-line interface for TraceNest."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tracenest import __product_name__, __version__
from tracenest.config import (
    TraceNestConfig,
    generate_default_toml,
    load_config,
)
from tracenest.core.diff import analyze_repository_changes
from tracenest.core.report import generate_json_report, generate_markdown_report, save_reports
from tracenest.core.sessions import compare_sessions, create_review_session
from tracenest.core.snapshots import (
    create_snapshot,
    get_git_branch,
    get_git_head,
    get_git_root,
)
from tracenest.exceptions import (
    GitRepositoryError,
    ProviderError,
    SessionNotFoundError,
)
from tracenest.models import FindingSeverity
from tracenest.providers import get_ai_provider
from tracenest.storage.database import Database, ensure_storage_dir

app = typer.Typer(
    name="tracenest",
    help="Understand every change your AI agent makes. Cross-platform AI coding session reviewer CLI.",
    add_completion=False,
    no_args_is_help=True,
)
snapshot_app = typer.Typer(help="Manage repository baseline snapshots.")
app.add_typer(snapshot_app, name="snapshot")

console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        console.print(
            f"[bold cyan]{__product_name__}[/bold cyan] version [bold green]v{__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show product version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """TraceNest CLI entry point."""


def get_db(repo_root: Path, config: TraceNestConfig) -> Database:
    storage_dir = ensure_storage_dir(repo_root, config.storage.dir_name)
    db_path = storage_dir / config.storage.db_name
    return Database(db_path)


@app.command()
def init(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root directory (defaults to current working directory).",
    ),
) -> None:
    """Initialize TraceNest storage and configuration in the target repository."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 1. Ensure storage directory and internal .gitignore
    storage_dir = ensure_storage_dir(repo_root, ".tracenest")
    db_path = storage_dir / "tracenest.db"
    Database(db_path)

    # 2. Generate tracenest.toml if missing
    config_file = repo_root / "tracenest.toml"
    if not config_file.exists():
        config_file.write_text(generate_default_toml(), encoding="utf-8")
        console.print(
            f"[green]✓[/green] Created configuration file: [bold]{config_file.name}[/bold]"
        )
    else:
        console.print(f"[dim]ℹ Existing configuration preserved: {config_file.name}[/dim]")

    console.print(
        Panel.fit(
            f"[bold green]TraceNest initialized successfully![/bold green]\n\n"
            f"• Repository: [cyan]{repo_root}[/cyan]\n"
            f"• Storage: [cyan]{storage_dir}[/cyan]\n"
            f"• Database: [cyan]{db_path.name}[/cyan]\n\n"
            f"Next steps:\n"
            f"  [bold]tracenest status[/bold]          - Check repo status\n"
            f"  [bold]tracenest snapshot create[/bold] - Record a baseline before AI starts\n"
            f"  [bold]tracenest review[/bold]          - Review modifications made by your agent",
            title=f"✨ {__product_name__} Ready",
            border_style="green",
        )
    )


@app.command()
def status(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root directory.",
    ),
) -> None:
    """Show current repository inspection status, changes, and recent sessions."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    branch = get_git_branch(repo_root) or "detached/none"
    head = get_git_head(repo_root) or "No commits yet"
    db = get_db(repo_root, config)

    # Inspect current changes
    changes = analyze_repository_changes(repo_root, config)
    snapshots = db.list_snapshots(limit=1)
    sessions = db.list_sessions(limit=1)

    table = Table(title="TraceNest Repository Status", border_style="cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Repository Root", str(repo_root))
    table.add_row("Active Branch", branch)
    table.add_row("HEAD Commit", head[:10] if head != "No commits yet" else head)
    table.add_row("Pending Changes", f"{len(changes)} files modified/added/untracked")

    if snapshots:
        s = snapshots[0]
        table.add_row("Latest Snapshot", f"{s.snapshot_id} ({s.created_at[:19]})")
    else:
        table.add_row("Latest Snapshot", "None recorded")

    if sessions:
        sess = sessions[0]
        table.add_row("Latest Session", f"{sess.session_id} ({sess.created_at[:19]})")
    else:
        table.add_row("Latest Session", "None recorded")

    console.print(table)


@snapshot_app.command("create")
def snapshot_create(
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Optional label for snapshot."),
    note: Optional[str] = typer.Option(None, "--note", "-m", help="Optional description note."),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Repository root directory."),
) -> None:
    """Capture a new baseline snapshot of the current repository state."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    db = get_db(repo_root, config)

    snap = create_snapshot(
        repo_root=repo_root,
        label=label,
        note=note,
        exclude_paths=config.scope.exclude_paths,
    )
    db.save_snapshot(snap)

    console.print(
        Panel.fit(
            f"[bold green]✓ Baseline Snapshot Created[/bold green]\n\n"
            f"• Snapshot ID: [bold cyan]{snap.snapshot_id}[/bold cyan]\n"
            f"• Branch: [dim]{snap.git_branch or 'N/A'}[/dim]\n"
            f"• Commit: [dim]{(snap.git_commit or 'Initial')[:10]}[/dim]\n"
            f"• Tracked Files: {snap.file_count}\n"
            f"• Fingerprint: [dim]{snap.working_tree_fingerprint[:16]}...[/dim]\n"
            f"• Label: {snap.label or 'None'}",
            border_style="green",
        )
    )


@snapshot_app.command("list")
def snapshot_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum snapshots to display."),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Repository root directory."),
) -> None:
    """List recorded baseline snapshots."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    db = get_db(repo_root, config)
    snapshots = db.list_snapshots(limit=limit)

    if not snapshots:
        console.print("[dim]No snapshots recorded yet. Run `tracenest snapshot create`.[/dim]")
        return

    table = Table(title="Baseline Snapshots", border_style="cyan")
    table.add_column("Snapshot ID", style="bold cyan")
    table.add_column("Created (UTC)")
    table.add_column("Branch")
    table.add_column("Commit")
    table.add_column("Files", justify="right")
    table.add_column("Label")

    for s in snapshots:
        table.add_row(
            s.snapshot_id,
            s.created_at[:19].replace("T", " "),
            s.git_branch or "-",
            (s.git_commit or "Initial")[:8],
            str(s.file_count),
            s.label or "-",
        )

    console.print(table)


@app.command()
def review(
    baseline: Optional[str] = typer.Option(
        None,
        "--baseline",
        "-b",
        help="Baseline Git commit, ref, or snapshot ID.",
    ),
    ai: bool = typer.Option(
        False,
        "--ai",
        help="Enable optional AI provider explanation.",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Override AI provider ('ollama' or 'openai').",
    ),
    allow_remote: bool = typer.Option(
        False,
        "--allow-remote",
        help="Explicitly permit transmitting sanitized diffs to remote AI provider.",
    ),
    label: Optional[str] = typer.Option(
        None,
        "--label",
        "-l",
        help="Label for this review session.",
    ),
    note: Optional[str] = typer.Option(
        "",
        "--note",
        "-m",
        help="Notes regarding this session.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to save generated Markdown and JSON reports.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root directory.",
    ),
) -> None:
    """Analyze current repository changes, evaluate deterministic rules, and save review session."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    if provider:
        config.ai.provider = provider
    if allow_remote:
        config.ai.allow_remote_data_sharing = True

    db = get_db(repo_root, config)

    # Resolve baseline
    resolved_baseline = baseline
    if not resolved_baseline:
        # Check if there is a recent snapshot
        recent_snapshots = db.list_snapshots(limit=1)
        if recent_snapshots:
            resolved_baseline = recent_snapshots[0].git_commit or recent_snapshots[0].snapshot_id

    # 1. Analyze changes & scanners
    session = create_review_session(
        repo_root=repo_root,
        config=config,
        db=db,
        baseline_ref=resolved_baseline,
        labels=[label] if label else [],
        notes=note or "",
    )

    # 2. Optional AI enrichment
    if ai:
        if config.ai.provider == "disabled":
            console.print(
                "[yellow]Notice: AI requested but provider is 'disabled'. Defaulting to deterministic review.[/yellow]"
            )
        else:
            try:
                ai_prov = get_ai_provider(config.ai)
                if ai_prov:
                    with console.status(
                        f"[cyan]Consulting {config.ai.provider} for advisory summary...[/cyan]"
                    ):
                        # Format compact diff summary
                        diff_summary_lines = []
                        for c in session.file_changes[:20]:
                            diff_summary_lines.append(f"File: {c.path} ({c.change_type.value})")
                            if c.diff_text and not c.is_binary:
                                diff_summary_lines.append(c.diff_text[:500])
                        diff_summary = "\n".join(diff_summary_lines)

                        explanation = ai_prov.explain_changes(diff_summary, session.findings)
                        session.ai_summary = explanation
                        db.save_session(session)
            except ProviderError as pe:
                err_console.print(f"[yellow]⚠ AI Provider Notice: {pe}[/yellow]")
                console.print("[dim]Continuing with deterministic review findings.[/dim]")

    # 3. Save reports
    report_directory = output_dir or (repo_root / config.storage.dir_name / "reports")
    save_reports(session, report_directory, config.reporting.default_formats)

    # 4. Render Terminal UI
    console.print(f"\n[bold]Session ID:[/bold] [cyan]{session.session_id}[/cyan]")
    console.print(f"[bold]Baseline:[/bold] [dim]{session.baseline_ref}[/dim]\n")

    # Files Table
    files_table = Table(title="Changed Files", border_style="blue")
    files_table.add_column("Status", style="bold")
    files_table.add_column("File Path")
    files_table.add_column("Additions", justify="right", style="green")
    files_table.add_column("Deletions", justify="right", style="red")

    for c in session.file_changes:
        old_info = f" [dim](renamed from {c.old_path})[/dim]" if c.old_path else ""
        bin_info = " [yellow](binary)[/yellow]" if c.is_binary else ""
        files_table.add_row(
            c.change_type.value.upper(),
            f"{c.path}{old_info}{bin_info}",
            f"+{c.additions}",
            f"-{c.deletions}",
        )

    if session.file_changes:
        console.print(files_table)
    else:
        console.print("[green]No changes detected in working tree.[/green]")

    # Findings Rendering
    console.print("\n[bold]Deterministic Review Findings:[/bold]")
    if not session.findings:
        console.print("[green]✓ No security or policy violations detected.[/green]")
    else:
        for f in session.findings:
            sev_color = {
                FindingSeverity.CRITICAL: "bold white on red",
                FindingSeverity.HIGH: "bold red",
                FindingSeverity.MEDIUM: "yellow",
                FindingSeverity.LOW: "cyan",
                FindingSeverity.INFO: "dim",
            }.get(f.severity, "white")

            loc = f"{f.file_path}:{f.line_number}" if f.line_number else f.file_path
            panel_text = (
                f"[bold]Severity:[/bold] [{sev_color}]{f.severity.value}[/{sev_color}]  "
                f"[bold]Rule:[/bold] {f.rule_id}  [bold]ID:[/bold] [dim]{f.finding_id}[/dim]\n"
                f"[bold]Location:[/bold] {loc}\n"
                f"[bold]Explanation:[/bold] {f.explanation}\n\n"
                f"[bold]Evidence:[/bold]\n[dim]{f.evidence or 'N/A'}[/dim]\n\n"
                f"[bold]Recommendation:[/bold] [italic]{f.recommendation}[/italic]"
            )
            console.print(
                Panel(
                    panel_text,
                    title=f"[{sev_color}] {f.title} [/{sev_color}]",
                    border_style="red"
                    if f.severity in {FindingSeverity.CRITICAL, FindingSeverity.HIGH}
                    else "yellow",
                )
            )

    if session.ai_summary:
        console.print(
            Panel(
                session.ai_summary,
                title="🤖 AI Advisory Explanation (Untrusted/Advisory)",
                border_style="magenta",
            )
        )

    console.print(f"\n[green]✓ Reports exported to:[/green] [dim]{report_directory}[/dim]")


@app.command()
def report(
    session_id: Optional[str] = typer.Option(
        None,
        "--session",
        "-s",
        help="Session ID to export (defaults to most recent session).",
    ),
    format_type: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Report format: 'markdown' or 'json'.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (prints to stdout if omitted).",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root directory.",
    ),
) -> None:
    """Generate and display or export a report for a specific review session."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    db = get_db(repo_root, config)

    target_session_id = session_id
    if not target_session_id:
        sessions = db.list_sessions(limit=1)
        if not sessions:
            err_console.print(
                "[red]No sessions found in database. Run `tracenest review` first.[/red]"
            )
            raise typer.Exit(code=1)
        target_session_id = sessions[0].session_id

    try:
        session = db.get_session(target_session_id)
    except SessionNotFoundError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    fmt = format_type.lower().strip()
    if fmt in {"json", "js"}:
        content = generate_json_report(session)
    else:
        content = generate_markdown_report(session)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]✓ Report written to {output}[/green]")
    else:
        sys.stdout.write(content)


@app.command()
def compare(
    session_a: str = typer.Argument(..., help="First session ID (earlier session)."),
    session_b: str = typer.Argument(..., help="Second session ID (later session)."),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root directory.",
    ),
) -> None:
    """Compare two review sessions to inspect progress, resolved issues, and new findings."""
    try:
        repo_root = get_git_root(path)
    except GitRepositoryError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    config = load_config(project_root=repo_root)
    db = get_db(repo_root, config)

    try:
        sess_a = db.get_session(session_a)
        sess_b = db.get_session(session_b)
    except SessionNotFoundError as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    result = compare_sessions(sess_a, sess_b)

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]⚠ Warning:[/yellow] {w}")

    table = Table(title=f"Session Comparison: {session_a} vs {session_b}", border_style="cyan")
    table.add_column("Category", style="bold")
    table.add_column("Delta / Details")

    table.add_row(
        "Files Added", ", ".join(result.files_added) if result.files_added else "[dim]None[/dim]"
    )
    table.add_row(
        "Files Removed",
        ", ".join(result.files_removed) if result.files_removed else "[dim]None[/dim]",
    )
    table.add_row(
        "Files Modified",
        ", ".join(result.files_modified) if result.files_modified else "[dim]None[/dim]",
    )
    table.add_row("New Findings Introduced", f"[red]{len(result.new_findings)}[/red]")
    table.add_row("Findings Resolved", f"[green]{len(result.resolved_findings)}[/green]")
    table.add_row("Persistent Findings", f"{len(result.persistent_findings)}")

    console.print(table)

    if result.new_findings:
        console.print("\n[bold red]Newly Introduced Findings in Session B:[/bold red]")
        for f in result.new_findings:
            console.print(
                f"  • [{f.severity.value}] {f.title} at {f.file_path}:{f.line_number or ''}"
            )

    if result.resolved_findings:
        console.print("\n[bold green]Resolved Findings from Session A:[/bold green]")
        for f in result.resolved_findings:
            console.print(f"  • [{f.severity.value}] {f.title} at {f.file_path}")


if __name__ == "__main__":
    app()
