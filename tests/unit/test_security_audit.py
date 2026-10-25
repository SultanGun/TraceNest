"""Security audit and hardening regression tests for TraceNest."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tracenest.adapters.opencode import OpenCodeAdapter
from tracenest.config import AIConfig, TraceNestConfig
from tracenest.core.diff import is_path_safe
from tracenest.core.report import generate_json_report
from tracenest.exceptions import (
    DataSharingNotAllowedError,
    ProviderError,
)
from tracenest.models import ChangeType, FileChange, FindingSeverity
from tracenest.providers.base import is_local_endpoint
from tracenest.providers.ollama import OllamaProvider
from tracenest.providers.openai_compatible import OpenAICompatibleProvider
from tracenest.scanners.rules import run_all_scanners
from tracenest.scanners.secrets import (
    redact_secret_string,
    redact_text,
    scan_file_for_secrets,
)
from tracenest.storage.database import Database

# ==============================================================================
# A. SSRF & AI Provider Network Privacy Tests
# ==============================================================================


def test_is_local_endpoint_valid_loopback():
    assert is_local_endpoint("http://localhost:11434") is True
    assert is_local_endpoint("https://localhost") is True
    assert is_local_endpoint("http://127.0.0.1:8000") is True
    assert is_local_endpoint("http://127.0.0.2:8000") is True
    assert is_local_endpoint("http://[::1]:8080") is True
    assert is_local_endpoint("http://sub.localhost:3000") is True
    assert is_local_endpoint("http://localhost.localdomain:8000") is True


def test_is_local_endpoint_ssrf_bypass_prevention():
    # Substring matching attacks that previous implementation permitted
    assert is_local_endpoint("http://localhost.attacker.com") is False
    assert is_local_endpoint("http://evil.com/127.0.0.1") is False
    assert is_local_endpoint("http://evil.com?target=localhost") is False
    assert is_local_endpoint("http://127.0.0.1.attacker.com") is False

    # Cloud metadata service (AWS/GCP/Azure IMDS)
    assert is_local_endpoint("http://169.254.169.254/latest/meta-data/") is False

    # Private LAN IP addresses (not local loopback)
    assert is_local_endpoint("http://192.168.1.1:8000") is False
    assert is_local_endpoint("http://10.0.0.1:8000") is False
    assert is_local_endpoint("http://172.16.0.1:8000") is False

    # Unspecified 0.0.0.0
    assert is_local_endpoint("http://0.0.0.0:8000") is False

    # Credentials embedded in URL
    assert is_local_endpoint("http://user:pass@localhost:8000") is False

    # Non-HTTP schemes
    assert is_local_endpoint("ftp://localhost") is False
    assert is_local_endpoint("gopher://localhost") is False
    assert is_local_endpoint("file:///etc/passwd") is False


def test_ollama_provider_blocks_remote_when_disallowed():
    cfg = AIConfig(
        provider="ollama",
        base_url="http://localhost.attacker.com:11434",
        allow_remote_data_sharing=False,
    )
    prov = OllamaProvider(cfg)
    with pytest.raises(DataSharingNotAllowedError):
        prov.explain_changes("diff sample", [])


def test_openai_provider_blocks_remote_when_disallowed():
    cfg = AIConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        allow_remote_data_sharing=False,
    )
    prov = OpenAICompatibleProvider(cfg)
    with pytest.raises(DataSharingNotAllowedError):
        prov.explain_changes("diff sample", [])


def test_openai_provider_allows_remote_when_explicitly_authorized(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    cfg = AIConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        allow_remote_data_sharing=True,
    )
    prov = OpenAICompatibleProvider(cfg)

    # Mock httpx.Client to prevent real network calls
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Verified advisory explanation."}}]
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.return_value = mock_resp
        mock_client_cls.return_value = mock_instance

        res = prov.explain_changes("diff", [])
        assert "Verified advisory explanation." in res
        # Verify follow_redirects is set to False
        _, kwargs = mock_client_cls.call_args
        assert kwargs.get("follow_redirects") is False


def test_provider_error_redaction():
    # If the provider throws an error containing sensitive text, verify it is redacted
    secret_in_error = "sk-1234567890abcdefghijklmnopqrstuv"
    cfg = AIConfig(
        provider="openai",
        base_url="http://127.0.0.1:8000/v1",
        allow_remote_data_sharing=True,
    )
    prov = OpenAICompatibleProvider(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = f"Internal server error reflecting secret {secret_in_error}"

    with patch.dict("os.environ", {"OPENAI_API_KEY": "valid-key"}):
        with patch("httpx.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.post.return_value = mock_resp
            mock_client_cls.return_value = mock_instance

            with pytest.raises(ProviderError) as exc_info:
                prov.explain_changes("diff", [])
            assert secret_in_error not in str(exc_info.value)
            assert "[REDACTED]" in str(exc_info.value)


# ==============================================================================
# B. Secret Detection, Redaction & Zero-Suffix-Leakage Tests
# ==============================================================================


def test_redact_secret_string_zero_suffix_leakage():
    # Verify that the trailing characters are NEVER leaked
    secret = "AKIA1234567890SECRETKEY"
    redacted = redact_secret_string(secret)
    assert secret[-4:] not in redacted
    assert "RETKEY" not in redacted
    assert redacted.endswith("[REDACTED]")


def test_secret_scanner_detects_expanded_patterns():
    diff = """
+aws_sec = "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCY1234567890'"
+bearer_token = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sometokenval12345"
+proj_key = "sk-proj-abc123def456ghi789jkl012mno345pqr678"
+private_key = "-----BEGIN RSA PRIVATE KEY-----"
"""
    findings = scan_file_for_secrets("keys.py", diff)
    rule_ids = {f.rule_id for f in findings}

    assert "SEC-AWS-SECRET-KEY" in rule_ids
    assert "SEC-BEARER-TOKEN" in rule_ids
    assert "SEC-OPENAI-KEY" in rule_ids
    assert "SEC-PRIVATE-KEY" in rule_ids


def test_redact_text_multiline_private_key():
    full_key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Yq3...
...more secret lines...
-----END RSA PRIVATE KEY-----
"""
    redacted = redact_text(full_key)
    assert "-----BEGIN RSA PRIVATE KEY-----" not in redacted
    assert "MIIEowIBAAKCAQEA0Yq3" not in redacted
    assert "[REDACTED_PRIVATE_KEY]" in redacted


# ==============================================================================
# C. Database & Report Redaction Hygiene Tests
# ==============================================================================


def test_database_and_json_report_redact_secrets_in_diff_text(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    secret = "sk-proj-SECRET1234567890abcdefghijklmnopqrstuvwxyz"
    change = FileChange(
        path="auth.py",
        change_type=ChangeType.MODIFIED,
        additions=1,
        deletions=0,
        diff_text=f"+api_key = '{secret}'\n",
    )
    from tracenest.models import SessionMetadata

    session = SessionMetadata(
        session_id="sess_leak_test",
        created_at="2026-10-25T10:00:00Z",
        repo_root=str(tmp_path),
        repo_id="test-repo",
        baseline_ref="HEAD",
        comparison_method="test",
        status="completed",
        file_changes=[change],
        findings=[],
    )

    # 1. Save session to database
    db.save_session(session)

    # Read raw database row directly from SQLite
    with db._get_connection() as conn:
        row = conn.execute(
            "SELECT diff_text FROM file_changes WHERE session_id = ?", ("sess_leak_test",)
        ).fetchone()
        stored_diff = row["diff_text"]
        assert secret not in stored_diff
        assert "[REDACTED]" in stored_diff

    # 2. Generate JSON report
    json_report = generate_json_report(session)
    assert secret not in json_report
    assert "[REDACTED]" in json_report


# ==============================================================================
# D. Path Traversal & Escaping Symlink Detection Tests
# ==============================================================================


def test_is_path_safe_traversal_detection(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    # Normal inside path
    inside_file = repo_dir / "src" / "index.py"
    assert is_path_safe(repo_dir, inside_file) is True

    # Path traversal escaping
    traversal_path = repo_dir / ".." / "outside" / "secret.txt"
    assert is_path_safe(repo_dir, traversal_path) is False


def test_path_traversal_in_changes_emits_critical_finding():
    changes = [
        FileChange(
            path="../../etc/shadow",
            change_type=ChangeType.ADDED,
            diff_text="[SECURITY ALERT: Path traversal detected: ../../etc/shadow escapes repo root.]",
        )
    ]
    config = TraceNestConfig()
    findings = run_all_scanners(changes, config)

    critical_traversal = [f for f in findings if f.rule_id == "SCP-PATH-TRAVERSAL"]
    assert len(critical_traversal) == 1
    assert critical_traversal[0].severity == FindingSeverity.CRITICAL
    assert "escapes the repository boundary" in critical_traversal[0].explanation


# ==============================================================================
# E. OpenCode Adapter Lifecycle & Verification Tests
# ==============================================================================


def test_opencode_adapter_attach_session_summary(tmp_path):
    opencode_dir = tmp_path / ".opencode"
    opencode_dir.mkdir()

    adapter = OpenCodeAdapter()
    assert adapter.is_detected(tmp_path) is True

    success = adapter.attach_session_summary(
        repo_root=tmp_path,
        session_id="sess_12345",
        files_changed_count=3,
        findings_count=1,
        critical_findings_count=1,
        metadata={"agent_task": "refactor_auth"},
    )
    assert success is True

    history_file = opencode_dir / "tracenest_sessions.jsonl"
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["session_id"] == "sess_12345"
    assert data["files_changed"] == 3
    assert data["critical_findings_count"] == 1
    assert data["has_critical"] is True
