# Getting Started with TraceNest

This guide walks you through using TraceNest to monitor and review changes made by AI coding agents.

---

## 1. Installation

Ensure you have Python 3.12 or newer installed:

```bash
python --version
```

Install TraceNest via pip:

```bash
pip install tracenest
```

---

## 2. Setting Up a Repository

Navigate to any Git repository and initialize TraceNest:

```bash
cd /path/to/my-project
tracenest init
```

TraceNest will:
1. Verify the Git repository structure.
2. Create the local storage directory `.tracenest/`.
3. Create `.tracenest/.gitignore` to keep review data out of your Git history.
4. Generate a default `tracenest.toml` configuration.

---

## 3. Workflow Walkthrough

### Step A: Capture a Baseline Snapshot
Before giving a task or prompt to an AI agent (e.g. OpenCode, Claude Code, Cursor, Cline), capture the working tree baseline:

```bash
tracenest snapshot create --label "pre-auth-refactor"
```

This records a deterministic fingerprint of tracked files and uncommitted changes.

### Step B: Run Your AI Agent
Allow the AI agent to edit files, implement features, or refactor code.

### Step C: Review Changes
When the agent finishes, run:

```bash
tracenest review
```

TraceNest performs:
- Diff calculation against the baseline.
- Scanning for leaked secrets, AWS keys, or API tokens.
- Validation that changes stayed within authorized project scope.
- Detection of dangerous code execution patterns (e.g. `eval()`, `verify=False`).
- Terminal summary with colorized severity highlights.
- Report export to `.tracenest/reports/report_<session_id>.md` and `.json`.

### Step D: Inspect or Export Reports
Export in Markdown or JSON format:

```bash
# Print Markdown report to stdout
tracenest report

# Export structured JSON to a specific file
tracenest report --format json --output audit.json
```

### Step E: Comparing Sessions
If the agent makes subsequent revisions, compare the sessions:

```bash
tracenest compare sess_20261024_100000_abc123 sess_20261024_101500_def456
```
