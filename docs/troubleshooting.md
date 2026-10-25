# Troubleshooting

This document addresses common issues and error scenarios in TraceNest.

---

## 1. `Directory is not part of a Git repository`

**Cause:** You executed a TraceNest command in a directory that is not managed by Git.
**Resolution:** Run `git init` or specify the path to a valid repository using `--path`:
```bash
tracenest status --path /path/to/my-repo
```

---

## 2. `DataSharingNotAllowedError`

**Cause:** You enabled AI explanation (`--ai`) targeting an external endpoint (not localhost), but remote data sharing is disabled in your configuration.
**Resolution:** Explicitly permit remote data sharing:
```bash
tracenest review --ai --allow-remote
```
Or permanently configure it in `tracenest.toml`:
```toml
[ai]
allow_remote_data_sharing = true
```

---

## 3. `Missing API key`

**Cause:** The OpenAI-compatible provider was invoked, but the environment variable specified in `api_key_env` (default `OPENAI_API_KEY`) is unset or empty.
**Resolution:** Export your key in your environment before running the review:
```bash
# Linux/macOS
export OPENAI_API_KEY="sk-..."

# Windows PowerShell
$env:OPENAI_API_KEY = "sk-..."
```

---

## 4. `Snapshot baseline not found`

**Cause:** The baseline reference passed via `--baseline` does not match any known commit, branch, or snapshot ID.
**Resolution:** Check recorded snapshot IDs with:
```bash
tracenest snapshot list
```
And provide a valid ID, or omit `--baseline` to automatically default to the latest snapshot or Git HEAD.
