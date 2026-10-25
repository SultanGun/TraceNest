"""Provider factory and registry for AI explanations."""

from typing import Optional

from tracenest.config import AIConfig
from tracenest.providers.base import AIProvider
from tracenest.providers.ollama import OllamaProvider
from tracenest.providers.openai_compatible import OpenAICompatibleProvider


def get_ai_provider(config: AIConfig) -> Optional[AIProvider]:
    """Instantiate the configured AI provider, or None if disabled."""
    provider_name = config.provider.lower().strip()
    if provider_name == "disabled":
        return None
    elif provider_name == "ollama":
        return OllamaProvider(config)
    elif provider_name == "openai":
        return OpenAICompatibleProvider(config)
    return None
