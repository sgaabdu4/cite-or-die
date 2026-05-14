from cite_or_die.core.config import Settings
from cite_or_die.providers.anthropic import AnthropicProvider
from cite_or_die.providers.base import Provider
from cite_or_die.providers.fake import FakeLLM
from cite_or_die.providers.ollama import OllamaProvider
from cite_or_die.providers.openai import OpenAIProvider
from cite_or_die.providers.openai_compatible import OpenAICompatibleProvider

HOSTED_PROVIDERS = {"anthropic", "openai", "openai-compatible"}


def make_provider(settings: Settings) -> Provider:
    if settings.llm_provider in HOSTED_PROVIDERS and (
        settings.app_env == "prod" and not settings.allow_hosted_llm
    ):
        raise RuntimeError(
            "Hosted LLM providers receive the question and retrieved chunks. "
            "Set CITE_OR_DIE_ALLOW_HOSTED_LLM=true to enable this in production."
        )
    if settings.llm_provider == "anthropic":
        if settings.anthropic_api_key is None:
            raise RuntimeError("CITE_OR_DIE_ANTHROPIC_API_KEY is required")
        return AnthropicProvider(settings.anthropic_api_key.get_secret_value())
    if settings.llm_provider == "openai":
        if settings.openai_api_key is None:
            raise RuntimeError("CITE_OR_DIE_OPENAI_API_KEY is required")
        return OpenAIProvider(settings.openai_api_key.get_secret_value())
    if settings.llm_provider == "openai-compatible":
        api_key = (
            settings.openai_compatible_api_key.get_secret_value()
            if settings.openai_compatible_api_key is not None
            else None
        )
        return OpenAICompatibleProvider(settings.openai_compatible_base_url, api_key)
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url)
    return FakeLLM()
