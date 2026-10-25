"""Unit tests for configuration loader and models."""

from pathlib import Path

import pytest

from tracenest.config import (
    TraceNestConfig,
    find_config_file,
    generate_default_toml,
    load_config,
)
from tracenest.exceptions import ConfigurationError
from tracenest.models import FindingSeverity


def test_default_config_values():
    cfg = TraceNestConfig()
    assert cfg.scope.max_file_size_kb == 512
    assert cfg.rules.secret_detection is True
    assert cfg.rules.severity_threshold == FindingSeverity.LOW
    assert cfg.storage.dir_name == ".tracenest"
    assert cfg.ai.provider == "disabled"
    assert cfg.ai.allow_remote_data_sharing is False


def test_load_config_from_file(tmp_path: Path):
    cfg_file = tmp_path / "tracenest.toml"
    content = """
    [scope]
    max_file_size_kb = 1024
    include_paths = ["src"]

    [rules]
    severity_threshold = "HIGH"
    secret_detection = false

    [ai]
    provider = "ollama"
    model = "mistral"
    """
    cfg_file.write_text(content, encoding="utf-8")

    loaded = load_config(cfg_file)
    assert loaded.scope.max_file_size_kb == 1024
    assert loaded.scope.include_paths == ["src"]
    assert loaded.rules.severity_threshold == FindingSeverity.HIGH
    assert loaded.rules.secret_detection is False
    assert loaded.ai.provider == "ollama"
    assert loaded.ai.model == "mistral"


def test_load_invalid_toml(tmp_path: Path):
    cfg_file = tmp_path / "tracenest.toml"
    cfg_file.write_text("invalid = [broken toml", encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(cfg_file)
    assert "Failed to parse config file" in str(exc_info.value)


def test_invalid_provider_rejected(tmp_path: Path):
    cfg_file = tmp_path / "tracenest.toml"
    cfg_file.write_text('[ai]\nprovider = "unsupported_cloud"', encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_config(cfg_file)


def test_find_config_file_hierarchical(tmp_path: Path):
    root_cfg = tmp_path / "tracenest.toml"
    root_cfg.write_text(generate_default_toml(), encoding="utf-8")

    sub_dir = tmp_path / "a" / "b" / "c"
    sub_dir.mkdir(parents=True)

    found = find_config_file(sub_dir)
    assert found is not None
    assert found.resolve() == root_cfg.resolve()
