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
from tracenest.scanners.secrets import redact_line


class OllamaProvider(AIProvider):
    """Local inference provider communicating with Ollama REST API."""

    def explain_changes(self, diff_summary: str, findings: List[Finding]) -> str:
        base_url = self.config.base_url.rstrip("/")
        is_local = is_local_endpoint(base_url)
        if not is_local and not self.config.allow_remote_data_sharing:
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
            with httpx.Client(
                timeout=self.config.timeout_seconds,
                follow_redirects=False,
                trust_env=not is_local,
            ) as client:
                resp = client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    safe_err = redact_line(resp.text[:200])
                    raise ProviderError(
                        f"Ollama returned HTTP status {resp.status_code}: {safe_err}"
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
            safe_e = redact_line(str(e))
            raise ProviderError(f"Failed to communicate with local Ollama at {endpoint}: {safe_e}")
