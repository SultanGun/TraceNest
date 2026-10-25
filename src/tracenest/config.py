"""Configuration loader and settings validation for TraceNest."""

import tomllib
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from tracenest.exceptions import ConfigurationError
from tracenest.models import FindingSeverity

DEFAULT_EXCLUDE_PATHS = [
    ".git",
    ".tracenest",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".coverage",
]


class ScopeConfig(BaseModel):
    """Configuration for repository scan scope and file limits."""

    include_paths: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_PATHS))
    max_file_size_kb: int = Field(default=512, ge=1, le=102400)


class RulesConfig(BaseModel):
    """Configuration for deterministic rule scanners."""

    secret_detection: bool = True
    config_guard: bool = True
    dangerous_patterns: bool = True
    dependency_guard: bool = True
    scope_guard: bool = True
    severity_threshold: FindingSeverity = FindingSeverity.LOW
    suppressions: List[str] = Field(default_factory=list)

    @field_validator("severity_threshold", mode="before")
    @classmethod
    def parse_severity(cls, v: Any) -> FindingSeverity:
        if isinstance(v, str):
            try:
                return FindingSeverity[v.upper()]
            except KeyError:
                raise ValueError(f"Invalid severity threshold: {v}")
        if isinstance(v, FindingSeverity):
            return v
        raise ValueError(f"Invalid severity value: {v}")


class StorageConfig(BaseModel):
    """Configuration for local SQLite database and session files."""

    dir_name: str = ".tracenest"
    db_name: str = "tracenest.db"
    retention_days: int = Field(default=30, ge=1)


class AIConfig(BaseModel):
    """Configuration for optional AI provider assistance."""

    provider: str = Field(default="disabled")  # "disabled", "ollama", "openai"
    base_url: str = "http://localhost:11434"
    model: str = "llama3"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    max_input_tokens: int = Field(default=4000, ge=100)
    allow_remote_data_sharing: bool = False

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"disabled", "ollama", "openai"}
        val = v.lower().strip()
        if val not in allowed:
            raise ValueError(f"Provider '{v}' not supported. Choose from: {sorted(allowed)}")
        return val


class ReportingConfig(BaseModel):
    """Configuration for report generation."""

    default_formats: List[str] = Field(default_factory=lambda: ["markdown", "json"])


class AdaptersConfig(BaseModel):
    """Configuration for external agent adapters."""

    opencode_enabled: bool = True


class TraceNestConfig(BaseModel):
    """Master configuration structure for TraceNest."""

    scope: ScopeConfig = Field(default_factory=ScopeConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)


def find_config_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Search upwards from start_dir for tracenest.toml or .tracenest.toml."""
    cur = (start_dir or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        for candidate in ["tracenest.toml", ".tracenest.toml"]:
            cfg = parent / candidate
            if cfg.is_file():
                return cfg
    return None


def load_config(
    config_path: Optional[Path] = None, project_root: Optional[Path] = None
) -> TraceNestConfig:
    """Load and validate configuration from TOML file, falling back to defaults."""
    target_path = config_path or find_config_file(project_root)
    if not target_path or not target_path.exists():
        return TraceNestConfig()

    try:
        with open(target_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigurationError(f"Failed to parse config file at {target_path}: {e}")

    try:
        return TraceNestConfig(**data)
    except Exception as e:
        raise ConfigurationError(f"Configuration validation failed for {target_path}: {e}")


def generate_default_toml() -> str:
    """Generate documented default TOML configuration string."""
    return """# TraceNest Configuration (tracenest.toml)
# Tagline: Understand every change your AI agent makes.

[scope]
# File paths or glob patterns to explicitly include in analysis (empty means all)
include_paths = []

# Paths and patterns to ignore during analysis
exclude_paths = [
    ".git",
    ".tracenest",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "*.egg-info",
]

# Maximum file size to analyze (in kilobytes)
max_file_size_kb = 512

[rules]
# Enable or disable individual scanner rules
secret_detection = true
config_guard = true
dangerous_patterns = true
dependency_guard = true
scope_guard = true

# Minimum severity threshold to report: INFO, LOW, MEDIUM, HIGH, CRITICAL
severity_threshold = "LOW"

# List of rule IDs or exact finding signatures to suppress
suppressions = []

[storage]
# Project directory for session databases and logs
dir_name = ".tracenest"
db_name = "tracenest.db"
# Number of days before old session cache is subject to prune
retention_days = 30

[ai]
# AI provider: "disabled" (default), "ollama" (local), or "openai" (OpenAI-compatible)
provider = "disabled"
# Base URL for the AI provider
base_url = "http://localhost:11434"
# Model identifier
model = "llama3"
# Environment variable holding the API key (for remote OpenAI-compatible endpoints)
api_key_env = "OPENAI_API_KEY"
# Request timeout in seconds
timeout_seconds = 30.0
# Privacy guard: Remote AI calls will be rejected unless explicitly permitted
allow_remote_data_sharing = false

[reporting]
default_formats = ["markdown", "json"]

[adapters]
opencode_enabled = true
"""
