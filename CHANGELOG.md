# Changelog

All notable changes to **TraceNest** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-24

### Added
- **P0 CLI Foundation**: Typer-based CLI with Rich output formatting (`init`, `status`, `snapshot`, `review`, `report`, `compare`).
- **P0 Repository Detection**: Deterministic Git repository discovery, uncommitted changes analysis, support for non-ASCII paths and paths with spaces.
- **P0 Snapshot & Baseline Engine**: Baseline snapshot capture, SHA-256 tree fingerprinting, and SQLite metadata indexing.
- **P0 Change Analysis**: Deterministic diff engine handling added, modified, deleted, renamed, untracked, and binary files with size limits and path traversal guards.
- **P0 Deterministic Rule Scanner**:
  - Sensitive credential exposure detection (AWS, GitHub, OpenAI, Slack, Private Keys, DB URIs, JWTs).
  - Automated secret redaction in terminal, logs, reports, and model prompts.
  - Sensitive configuration file modification guards (`.env*`, `.aws/`, CI workflows, certificates).
  - Dependency and build file tracking (`pyproject.toml`, `requirements.txt`, `package.json`, `Cargo.toml`, `Dockerfile`).
  - Dangerous code patterns (Python `eval`, `exec`, `shell=True`, `pickle`, unsafe YAML, TLS verification bypass).
- **P0 Report Generation**: Comprehensive Markdown and versioned structured JSON (`tracenest-report-v1`) reports.
- **P0 Session Comparison**: Stable cross-session diff engine tracking new, resolved, and persistent findings.
- **P0 Local Storage**: Versioned SQLite storage (`tracenest.db`) and automatic `.tracenest/.gitignore` generation.
- **P1 AI Providers**: Local Ollama provider and remote OpenAI-compatible API provider with strict local-first privacy guards.
- **P1 Agent Adapters**: OpenCode adapter with documented snapshot-and-diff integration workflow.
