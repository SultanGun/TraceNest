"""Unit tests for agent adapters (OpenCode)."""

from pathlib import Path

from tracenest.adapters.opencode import OpenCodeAdapter


def test_opencode_adapter_detection(tmp_path: Path):
    adapter = OpenCodeAdapter()
    assert adapter.name == "OpenCode"
    assert adapter.is_detected(tmp_path) is False

    # Create .opencode marker
    (tmp_path / ".opencode").mkdir()
    assert adapter.is_detected(tmp_path) is True


def test_opencode_adapter_capabilities():
    adapter = OpenCodeAdapter()
    caps = adapter.get_capabilities()
    assert caps["filesystem_diffs"] is True
    assert caps["secret_detection"] is True
    assert caps["realtime_telemetry_streaming"] is False
    assert caps["shell_execution_interception"] is False


def test_opencode_record_session(tmp_path: Path):
    adapter = OpenCodeAdapter()
    opencode_dir = tmp_path / ".opencode"
    opencode_dir.mkdir()

    adapter.record_session(tmp_path, "sess_123", {"note": "test"})
    history_file = opencode_dir / "tracenest_sessions.jsonl"
    assert history_file.is_file()
    assert "sess_123" in history_file.read_text(encoding="utf-8")
