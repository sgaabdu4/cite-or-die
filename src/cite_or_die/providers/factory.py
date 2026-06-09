from pydantic import SecretStr

from cite_or_die.core.config import Settings
from cite_or_die.core.models import ProviderConfigStored
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


def make_provider_from_override(
    base_settings: Settings, override: ProviderConfigStored
) -> Provider:
    """Build a Provider from a per-tenant override by layering it on base settings."""

    update: dict[str, object] = {
        "llm_provider": override.llm_provider,
        "llm_model": override.llm_model,
    }
    if override.llm_provider == "anthropic":
        if not override.llm_api_key_plaintext:
            raise RuntimeError("Anthropic provider requires an api_key in the tenant config")
        update["anthropic_api_key"] = SecretStr(override.llm_api_key_plaintext)
    elif override.llm_provider == "openai":
        if not override.llm_api_key_plaintext:
            raise RuntimeError("OpenAI provider requires an api_key in the tenant config")
        update["openai_api_key"] = SecretStr(override.llm_api_key_plaintext)
    elif override.llm_provider == "openai-compatible":
        if override.llm_api_key_plaintext:
            update["openai_compatible_api_key"] = SecretStr(override.llm_api_key_plaintext)
        if override.llm_base_url:
            update["openai_compatible_base_url"] = override.llm_base_url
    elif override.llm_provider == "ollama":
        if override.llm_base_url:
            update["ollama_base_url"] = override.llm_base_url
    overlay = base_settings.model_copy(update=update)
    return make_provider(overlay)
