"""OpenAI-compatible HTTP API provider implementation."""

import os
from typing import List

import httpx

from tracenest.exceptions import (
    DataSharingNotAllowedError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from tracenest.models import Finding
from tracenest.providers.base import AIProvider, is_local_endpoint


class OpenAICompatibleProvider(AIProvider):
    """Provider for any OpenAI-compatible chat completions endpoint."""

    def explain_changes(self, diff_summary: str, findings: List[Finding]) -> str:
        base_url = self.config.base_url.rstrip("/")
        if not is_local_endpoint(base_url) and not self.config.allow_remote_data_sharing:
            raise DataSharingNotAllowedError(
                f"External endpoint '{base_url}' requested, but remote data sharing is disabled. "
                "Set allow_remote_data_sharing = true in tracenest.toml or pass --allow-remote to permit."
            )

        api_key = os.environ.get(self.config.api_key_env, "").strip()
        if not api_key:
            raise ProviderAuthError(
                f"Missing API key. Please set the environment variable '{self.config.api_key_env}'."
            )

        prompt = self.prepare_sanitized_prompt(diff_summary, findings)
        endpoint = (
            f"{base_url}/chat/completions"
            if not base_url.endswith("/chat/completions")
            else base_url
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are TraceNest, an objective code session review assistant. Be concise and factual.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1000,
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code == 401 or resp.status_code == 403:
                    raise ProviderAuthError(
                        f"Authentication failed with status {resp.status_code}. Verify your {self.config.api_key_env} key."
                    )
                if resp.status_code != 200:
                    raise ProviderError(
                        f"API provider returned error status {resp.status_code}: {resp.text[:200]}"
                    )
                data = resp.json()
                choices = data.get("choices", [])
                if not choices or "message" not in choices[0]:
                    raise ProviderError(
                        "Malformed response structure from chat completions endpoint."
                    )
                return str(choices[0]["message"]["content"]).strip()
        except httpx.TimeoutException:
            raise ProviderTimeoutError(
                f"API request timed out after {self.config.timeout_seconds}s at {endpoint}."
            )
        except httpx.RequestError as e:
            raise ProviderError(f"Network error communicating with AI provider at {endpoint}: {e}")
