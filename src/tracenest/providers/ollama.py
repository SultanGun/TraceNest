"""Local Ollama AI provider implementation."""

from typing import List

import httpx

from tracenest.exceptions import (
    DataSharingNotAllowedError,
    ProviderError,
    ProviderTimeoutError,
)
from tracenest.models import Finding
from tracenest.providers.base import AIProvider, is_local_endpoint


class OllamaProvider(AIProvider):
    """Local inference provider communicating with Ollama REST API."""

    def explain_changes(self, diff_summary: str, findings: List[Finding]) -> str:
        base_url = self.config.base_url.rstrip("/")
        if not is_local_endpoint(base_url) and not self.config.allow_remote_data_sharing:
            raise DataSharingNotAllowedError(
                f"Ollama base URL '{base_url}' is not a local loopback address and "
                "allow_remote_data_sharing is disabled. Refusing to transmit repository diffs."
            )

        prompt = self.prepare_sanitized_prompt(diff_summary, findings)
        endpoint = f"{base_url}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Ollama returned HTTP status {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                if "response" not in data:
                    raise ProviderError("Malformed response from Ollama: missing 'response' field.")
                return str(data["response"]).strip()
        except httpx.TimeoutException:
            raise ProviderTimeoutError(
                f"Ollama request timed out after {self.config.timeout_seconds}s at {endpoint}."
            )
        except httpx.RequestError as e:
            raise ProviderError(f"Failed to communicate with local Ollama at {endpoint}: {e}")
