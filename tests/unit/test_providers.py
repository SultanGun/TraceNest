"""Unit tests for AI providers, redaction, timeouts, and privacy guards."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tracenest.config import AIConfig
from tracenest.exceptions import (
    DataSharingNotAllowedError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from tracenest.providers import get_ai_provider
from tracenest.providers.ollama import OllamaProvider
from tracenest.providers.openai_compatible import OpenAICompatibleProvider


def test_disabled_provider_no_instance():
    cfg = AIConfig(provider="disabled")
    prov = get_ai_provider(cfg)
    assert prov is None


def test_remote_data_sharing_blocked_by_default():
    cfg = AIConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        allow_remote_data_sharing=False,
    )
    prov = OpenAICompatibleProvider(cfg)

    with pytest.raises(DataSharingNotAllowedError) as exc_info:
        prov.explain_changes("diff", [])
    assert "remote data sharing is disabled" in str(exc_info.value)


def test_missing_api_key_raises_auth_error():
    cfg = AIConfig(
        provider="openai",
        base_url="http://localhost:8000/v1",
        api_key_env="NON_EXISTENT_ENV_KEY_12345",
        allow_remote_data_sharing=True,
    )
    prov = OpenAICompatibleProvider(cfg)

    with pytest.raises(ProviderAuthError) as exc_info:
        prov.explain_changes("diff", [])
    assert "Missing API key" in str(exc_info.value)
    # Ensure no secret content leaked
    assert "NON_EXISTENT_ENV_KEY_12345" in str(exc_info.value)


def test_api_key_not_leaked_on_auth_failure():
    secret_key = "super_secret_raw_key_value"
    os.environ["TEST_TRACENEST_KEY"] = secret_key
    try:
        cfg = AIConfig(
            provider="openai",
            base_url="http://localhost:8000/v1",
            api_key_env="TEST_TRACENEST_KEY",
            allow_remote_data_sharing=True,
        )
        prov = OpenAICompatibleProvider(cfg)

        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
            with pytest.raises(ProviderAuthError) as exc_info:
                prov.explain_changes("diff", [])
            # Assert raw secret key does not appear in the exception message
            assert secret_key not in str(exc_info.value)
    finally:
        os.environ.pop("TEST_TRACENEST_KEY", None)


def test_secrets_redacted_in_ai_prompt():
    cfg = AIConfig(provider="ollama", base_url="http://localhost:11434")
    prov = OllamaProvider(cfg)

    raw_aws = "AKIA1234567890ABCDEF"
    diff = f"+aws_key = '{raw_aws}'"
    prompt = prov.prepare_sanitized_prompt(diff, [])

    assert raw_aws not in prompt
    assert "[REDACTED]" in prompt


def test_ollama_success():
    cfg = AIConfig(provider="ollama", base_url="http://localhost:11434")
    prov = OllamaProvider(cfg)

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": "The changes introduce authentication logic."},
        )
        summary = prov.explain_changes("diff", [])
        assert "introduce authentication logic" in summary


def test_ollama_timeout():
    cfg = AIConfig(provider="ollama", base_url="http://localhost:11434", timeout_seconds=1.0)
    prov = OllamaProvider(cfg)

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(ProviderTimeoutError):
            prov.explain_changes("diff", [])


def test_ollama_malformed_response():
    cfg = AIConfig(provider="ollama", base_url="http://localhost:11434")
    prov = OllamaProvider(cfg)

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"unexpected": "payload"})
        with pytest.raises(ProviderError) as exc_info:
            prov.explain_changes("diff", [])
        assert "Malformed response" in str(exc_info.value)
