# Privacy and Security Model

Privacy and security are treated as foundational engineering requirements in TraceNest.

---

## 1. Local-First by Default

- **Zero Unsolicited Network Calls:** When running in default mode (`provider = "disabled"`), TraceNest executes entirely offline. It does not phone home, collect telemetry, or ping external analytics.
- **Local Storage:** All session databases and reports reside within your repository's `.tracenest/` directory.
- **Git Isolation:** `.tracenest/.gitignore` is automatically maintained to prevent accidental commits of session artifacts or SQLite databases to source control.

---

## 2. Remote Data Sharing Guard

If you configure an OpenAI-compatible remote provider or a remote Ollama server:

1. **Explicit Opt-in:** TraceNest will refuse to connect to non-localhost URLs unless `allow_remote_data_sharing = true` is explicitly configured in `tracenest.toml` or `--allow-remote` is passed to the CLI.
2. **Secret Redaction:** Any string matching recognized secret patterns is replaced with a redacted token before the diff summary is transmitted to an AI provider.
3. **Diff Truncation:** Input diff summaries are capped according to `max_input_tokens` to prevent sending excessive repository content.

---

## 3. Subprocess & Execution Safety

- **No `shell=True`:** Subprocess calls always pass structured argument lists (e.g. `["git", "diff", ...]`). Untrusted filenames or branch names cannot trigger shell command injection.
- **No Automatic Code Execution:** TraceNest never executes commands suggested by AI models or found in changed repository files.
- **Path Traversal Guards:** File paths are validated with `is_relative_to` checks against the repository root. Symlinks pointing outside the repository boundary are rejected.
- **Credential Masking:** API keys configured in environment variables (such as `OPENAI_API_KEY`) are never printed in error messages, console logs, or stored reports.
