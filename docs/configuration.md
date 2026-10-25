# Configuration Guide

TraceNest looks for a `tracenest.toml` or `.tracenest.toml` configuration file in the repository root.

---

## Configuration Schema

```toml
[scope]
# File paths or directory prefixes to restrict analysis to (empty means whole repo)
include_paths = ["src", "backend"]

# Paths, directories, and glob patterns to ignore
exclude_paths = [
    ".git",
    ".tracenest",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
]

# Maximum file size in kilobytes for diff and scanning
max_file_size_kb = 512

[rules]
# Enable/disable scanner rules
secret_detection = true
config_guard = true
dangerous_patterns = true
dependency_guard = true
scope_guard = true

# Severity threshold: INFO, LOW, MEDIUM, HIGH, CRITICAL
severity_threshold = "LOW"

# Rule IDs to suppress
suppressions = [
    "SEC-JWT-TOKEN",
]

[storage]
dir_name = ".tracenest"
db_name = "tracenest.db"
retention_days = 30

[ai]
provider = "disabled" # "disabled", "ollama", or "openai"
base_url = "http://localhost:11434"
model = "llama3"
api_key_env = "OPENAI_API_KEY"
timeout_seconds = 30.0
max_input_tokens = 4000
allow_remote_data_sharing = false

[reporting]
default_formats = ["markdown", "json"]

[adapters]
opencode_enabled = true
```

---

## Suppressing Findings

To suppress a finding that is a documented false-positive or expected in a test suite:

```toml
[rules]
suppressions = [
    "SEC-AWS-KEY",                  # Suppress all AWS key alerts
    "FND-7a8b9c0d1e2f",             # Suppress specific finding ID
]
```
