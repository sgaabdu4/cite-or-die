const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai";

export const BASE_URL_PROVIDERS = new Set(["gemini", "openai-compatible", "ollama"]);
export const KEY_REUSE_BASE_URL_PROVIDERS = new Set(["gemini", "openai-compatible"]);

const REQUIRED_API_KEY_PROVIDERS = new Set(["gemini", "anthropic", "openai"]);
const ACCEPTED_API_KEY_PROVIDERS = new Set([
  "gemini",
  "anthropic",
  "openai",
  "openai-compatible",
]);

const PROVIDER_PRESETS = {
  fake: { label: "Offline demo", model: "", baseUrl: "" },
  gemini: { label: "Gemini", model: "gemini-3.5-flash", baseUrl: GEMINI_BASE_URL },
  openai: { label: "OpenAI", model: "gpt-5.5", baseUrl: "" },
  anthropic: { label: "Anthropic", model: "claude-sonnet-4-6", baseUrl: "" },
  "openai-compatible": { label: "OpenAI-compatible", model: "", baseUrl: "" },
  ollama: { label: "Ollama", model: "qwen3:8b", baseUrl: "http://localhost:11434" },
};

const PROVIDER_GUIDANCE = {
  fake: {
    provider: "Offline demo uses the local deterministic provider.",
    key: "No external API key, base URL, or hosted model call is needed.",
    test: "Save is available immediately; no provider connection test is required.",
  },
  gemini: {
    provider: "Gemini uses Google's official OpenAI-compatible endpoint.",
    key: "Use a Gemini API key from Google AI Studio.",
    test: "The connection test calls Gemini chat completions with a short setup check.",
  },
  openai: {
    provider: "OpenAI uses the default OpenAI API endpoint; no custom base URL is needed.",
    key: "Use an OpenAI API key. The server sends it as a bearer credential.",
    test: "The connection test calls the OpenAI Responses API with a short setup check.",
  },
  anthropic: {
    provider: "Anthropic uses the native Claude Messages API.",
    key: "Use an Anthropic API key from the Claude Console.",
    test: "The connection test calls the Claude Messages API with a short setup check.",
  },
  "openai-compatible": {
    provider: "Use this for a provider that exposes an OpenAI-compatible chat completions API.",
    key: "Use an API key only when that endpoint requires one.",
    test: "The connection test calls the configured chat completions endpoint.",
  },
  ollama: {
    provider: "Ollama runs locally against the configured local base URL.",
    key: "No API key is used for the local Ollama provider.",
    test: "The connection test calls the local Ollama generate endpoint.",
  },
};

export function providerGuidance(provider) {
  return PROVIDER_GUIDANCE[provider] || PROVIDER_GUIDANCE.fake;
}

export function setOptionalText(node, text) {
  if (!node) return;
  node.textContent = text;
}

export function setOptionalDisabled(node, disabled) {
  if (!node) return;
  node.disabled = disabled;
}

export function providerSetupView(status) {
  if (!status) return emptyProviderSetupView();
  return {
    title: `${status.displayLabel} - ${status.llm_model}`,
    state: "ready",
    action: "Change provider",
    summary: "Provider ready. Load a deal room, then run the review.",
  };
}

function emptyProviderSetupView() {
  return {
    title: "Not configured",
    state: "needed",
    action: "Configure provider",
    summary: "Connect a model provider, load sources, then run the review.",
  };
}

export function reindexRequired(status) {
  if (!status) return false;
  return Boolean(status.requires_reindex);
}

export function skipConnectionTest(savedConfigSelected, body) {
  if (savedConfigSelected) return false;
  return body === null;
}

export function providerPayloadName(provider) {
  if (provider === "gemini") return "openai-compatible";
  return provider;
}

export function providerPreset(provider) {
  return PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.fake;
}

export function shouldApplyDefault(currentValue, overwrite) {
  if (overwrite) return true;
  return !currentValue.trim();
}

export function embeddingDimension(provider) {
  if (provider === "bge-m3") return 1024;
  return 384;
}

export function providerFromStatus(status) {
  if (!status) return "fake";
  if (isGeminiStatus(status)) return "gemini";
  return status.llm_provider || "fake";
}

function isGeminiStatus(status) {
  if (status.llm_provider !== "openai-compatible") return false;
  return normalizedUrl(status.llm_base_url) === GEMINI_BASE_URL;
}

export function normalizedUrl(value) {
  return String(value || "").replace(/\/$/, "");
}

export function providerLabel(provider) {
  return PROVIDER_PRESETS[provider]?.label || provider;
}

export function requiresApiKey(provider) {
  return REQUIRED_API_KEY_PROVIDERS.has(provider);
}

export function acceptsApiKey(provider) {
  return ACCEPTED_API_KEY_PROVIDERS.has(provider);
}

export function apiKeyPlaceholder(provider) {
  const labels = {
    gemini: "Gemini API key from AI Studio",
    openai: "OpenAI API key",
    anthropic: "Anthropic API key",
    "openai-compatible": "Optional provider API key",
  };
  return labels[provider] || "Write-only server secret";
}

export function updateKeyControl(button, showControls) {
  if (!button) return;
  button.hidden = !showControls;
  button.disabled = true;
  if (showControls) button.disabled = !document.getElementById("settings-llm-api-key").value;
}

export function shouldHideKey(showControls, value) {
  if (!showControls) return true;
  return !value;
}

export function keyInputType(visible) {
  if (visible) return "text";
  return "password";
}

export function updateKeyToggleState(button, visible) {
  if (!button) return;
  button.textContent = keyToggleLabel(visible);
  button.setAttribute("aria-pressed", keyTogglePressed(visible));
}

function keyToggleLabel(visible) {
  if (visible) return "Hide";
  return "Show";
}

function keyTogglePressed(visible) {
  if (visible) return "true";
  return "false";
}

export function apiKeyInputIssue(provider, value) {
  if (!value) return null;
  return credentialInputIssue(provider, value);
}

function credentialInputIssue(provider, value) {
  if (looksStructuredCredential(value)) {
    return {
      state: "warning",
      message:
        "This looks like JSON or a multi-line credential. Paste a single provider API key instead.",
    };
  }
  if (/\s/.test(value)) {
    return { state: "warning", message: whitespaceCredentialMessage(provider) };
  }
  if (isGeminiOauthToken(provider, value)) {
    return {
      state: "warning",
      message: "This looks like an OAuth token. Use a Gemini API key from AI Studio.",
    };
  }
  return null;
}

function looksStructuredCredential(value) {
  if (value.trim().startsWith("{")) return true;
  return includesLineBreak(value);
}

function includesLineBreak(value) {
  return value.includes("\n") || value.includes("\r");
}

function whitespaceCredentialMessage(provider) {
  if (provider === "gemini") {
    return "Gemini expects a single API key from AI Studio; remove spaces or line breaks.";
  }
  return "Remove spaces or line breaks before testing the key.";
}

function isGeminiOauthToken(provider, value) {
  if (provider !== "gemini") return false;
  return isOauthTokenValue(value);
}

function isOauthTokenValue(value) {
  return value.startsWith("ya29.") || value.startsWith("1//");
}

export function keyGuidanceMessage(provider, value, issue, savedKeyAvailable) {
  if (!acceptsApiKey(provider)) {
    return { state: "ready", text: "No API key is needed for the offline demo." };
  }
  if (issue) return { state: issue.state, text: issue.message };
  return keyEntryGuidance(provider, value, savedKeyAvailable);
}

function keyEntryGuidance(provider, value, savedKeyAvailable) {
  if (!value) return blankKeyGuidanceMessage(provider, savedKeyAvailable);
  return {
    state: "ready",
    text: "New write-only key entered. Test connection before saving.",
  };
}

function blankKeyGuidanceMessage(provider, savedKeyAvailable) {
  if (savedKeyAvailable) {
    return {
      state: "ready",
      text: "Saved write-only key will be reused for this provider and base URL.",
    };
  }
  if (!requiresApiKey(provider)) {
    return {
      state: "ready",
      text: "API key optional. Leave blank for a local no-auth endpoint.",
    };
  }
  return {
    state: "needed",
    text: "Paste a provider API key. It is encrypted after saving and never shown again.",
  };
}

export function setTesting(testing, message = "") {
  const button = document.getElementById("settings-test");
  if (!button) return;
  button.disabled = testing;
  keepSaveDisabledWhileTesting(testing);
  setTestingMessage(message);
}

function keepSaveDisabledWhileTesting(testing) {
  const saveButton = document.getElementById("settings-save");
  if (!saveButton) return;
  if (testing) saveButton.disabled = true;
}

function setTestingMessage(message) {
  if (!message) return;
  document.getElementById("settings-result").textContent = message;
}
