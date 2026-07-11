# LLM Provider Guide — How to Add a New Provider

## Architecture Overview

The LLM layer uses a **Registry + Factory** pattern built on an abstract base class.

```
app/llm/
├── provider.py          # ABC + all providers + ProviderRegistry
├── gateway.py           # LLMGateway — routes requests to the active provider
├── config_resolver.py   # Reads LLM_PROVIDER from env/DB, picks the right provider
├── models.py            # LLMRequest / LLMResponse
├── exceptions.py        # LLMProviderError, LLMConfigurationError, etc.
├── retry.py             # Retry logic
└── validation.py        # Response validation / JSON repair
```

## Existing Providers (already registered)

| Registry Name | Class | Env Vars Required | Type |
|---------------|-------|-------------------|------|
| `gemini`, `google` | `GeminiProvider` | `GOOGLE_API_KEY` | Cloud API |
| `vertex` | `VertexAIProvider` | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | Cloud API |
| `anthropic` | `AnthropicProvider` | `ANTHROPIC_API_KEY` | Cloud API |
| `openai` | `OpenAIProvider` | `OPENAI_API_KEY` | Cloud API |
| `azure` | `AzureOpenAIProvider` | `AZURE_OPENAI_API_KEY` | Cloud API |
| `ollama` | `OllamaProvider` | `OLLAMA_BASE_URL` | Local / Offline |
| `fireworks` | `FireworksProvider` | `FIREWORKS_API_KEY` | Cloud API |

## How to Add a New Provider

### Step 1: Create the provider class

In `app/llm/provider.py`, create a new class that extends `LLMProvider`.

**For a cloud API (e.g., Groq, Together AI, DeepSeek):**

```python
class GroqProvider(LLMProvider):
    def name(self) -> str:
        return "Groq"

    def supported_models(self) -> list[str]:
        return ["gemma2-9b-it", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]

    def is_available(self) -> bool:
        return bool(getattr(settings, "GROQ_API_KEY", None))

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {"streaming": True, "json_mode": True, "vision": False, "tool_calling": True}

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        # Follow the pattern in FireworksProvider or GeminiProvider

    async def listModels(self) -> list[dict[str, Any]]:
        return [{"name": m, "context_window": 128000, "supports_json": True}
                for m in self.supported_models()]

    def estimateCost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        return calculate_cost(model, prompt_tokens, completion_tokens)

    def supportsStreaming(self) -> bool: return True
    def supportsJSON(self) -> bool: return True
    def supportsVision(self) -> bool: return False
    def supportsToolCalling(self) -> bool: return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self, request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        # Implement HTTP call to the API
        # Follow the FireworksProvider.generate() pattern — it handles:
        #   - API key validation
        #   - Request building (system_instruction + prompt as messages)
        #   - JSON mode via response_format
        #   - Error handling (timeout, rate limit, server errors)
        #   - Token usage parsing
        #   - LLMResponse construction
```

**For a local / offline model (e.g., llama.cpp, Hugging Face Transformers, vLLM):**

```python
class MyLocalProvider(LLMProvider):
    # Follow the OllamaProvider pattern
    # - is_available() checks for a base URL or model path
    # - estimateCost() returns 0.0 (free)
    # - generate() calls the local inference server
```

### Step 2: Add settings to `app/core/settings/config.py`

Add any new env vars the provider needs:

```python
# Groq Provider
GROQ_ENABLED: bool = Field(default=False)
GROQ_API_KEY: str | None = Field(default=None)
GROQ_MODEL: str = Field(default="gemma2-9b-it")
```

### Step 3: Register in `ProviderRegistry`

In `app/llm/provider.py`, inside `ProviderRegistry.__init__()`:

```python
self.register("groq", GroqProvider())
```

The registry will **reject duplicate names** with an error message. If you see:

```
LLMConfigurationError: Provider 'groq' is already registered as 'Groq'
```

Pick a different registry name or unregister the existing one first.

### Step 4: Update `app/llm/config_resolver.py`

Add the provider to three places:

**a) Model defaults** (in `resolve_llm_config()`):
```python
elif provider == "groq":
    model = getattr(settings, "GROQ_MODEL", "gemma2-9b-it")
```

**b) API key resolution** (in `resolve_llm_config()`):
```python
elif provider == "groq":
    api_key = getattr(settings, "GROQ_API_KEY", None)
```

**c) API key validation** (in `validate_llm_config()`):
```python
elif provider == "groq":
    key = config.get("api_key") or getattr(settings, "GROQ_API_KEY", None)
    if not key:
        valid = False
```

### Step 5: Add to `.env.example`

```env
#######################################
# Groq
#######################################
GROQ_API_KEY=
GROQ_MODEL=gemma2-9b-it
```

### Step 6: Update fallback order in `app/llm/gateway.py`

Add a model mapping in the failover block:
```python
elif current_prov_name == "groq":
    provider_request.model = "gemma2-9b-it"
```

### Step 7: Test

```bash
# Set env vars, then:
python -c "from app.llm.provider import provider_registry; p = provider_registry.getProvider('groq'); print(p.name(), p.is_available())"
```

## Local / Offline Providers

To add a fully offline provider (no internet needed):

1. **Create a class** that starts a local model server (e.g., llama.cpp, Ollama, Hugging Face pipeline)
2. **Set `estimateCost()` to return `0.0`**
3. **`is_available()`** checks if the model binary exists or the local server is running
4. **Example**: `OllamaProvider` already shows this pattern — it runs locally and costs nothing

For a custom offline model (e.g., a downloaded GGUF file):
- Follow `OllamaProvider`'s structure
- Replace the HTTP call with a direct Python inference call (e.g., `llama_cpp.Llama()` or `transformers.pipeline()`)
- No API key needed — `is_available()` checks for the model file path

## Duplicate Protection

The `ProviderRegistry.register()` method checks for existing names **before** overwriting.

Trying this:
```python
self.register("gemini", MyCustomProvider())  # Error!
```
Produces:
```
LLMConfigurationError: Provider 'gemini' is already registered as 'Gemini Developer API'.
Use a different name or unregister first.
```

To replace an existing provider:
```python
registry.unregister("gemini")
registry.register("gemini", MyCustomProvider())
```

## ✅ Copy-Paste Prompt for AI Agents

Give the following prompt to any AI coding assistant (opencode, Cursor, Copilot, etc.) to automatically add a new LLM provider:

---

```
Add a new LLM provider called `{PROVIDER_NAME}` to the SafeSeedOps Lite codebase at `C:\Users\lovea\Documents\hackathon\safeseedops-lite`.

## Requirements

- Registry name (used in LLM_PROVIDER= env): `{REGISTRY_NAME}`
- Provider class name: `{PROVIDER_NAME}Provider`
- API is OpenAI-compatible (base URL: `{BASE_URL}`)
- Default model: `{MODEL_NAME}`
- Available models: `{AVAILABLE_MODELS}`

## What to do (in this exact order)

### 1. Create the provider class
In `app/llm/provider.py`, add a new `{PROVIDER_NAME}Provider` class extending `LLMProvider`.
- Follow the exact pattern of the existing `FireworksProvider` class in the same file
- Override `name()`, `supported_models()`, `is_available()`, `auth_status()`, `capabilities()`, `healthCheck()`, `listModels()`, `estimateCost()`, `generate()`
- `is_available()` checks for `settings.{REGISTRY_NAME.upper()}_API_KEY`
- `generate()` makes an HTTP POST to `{BASE_URL}` with OpenAI-compatible request/response format
- Register it in `ProviderRegistry.__init__()` as `self.register("{REGISTRY_NAME}", {PROVIDER_NAME}Provider())`
- Do NOT remove or modify any existing provider

### 2. Add settings
In `app/core/settings/config.py`, add these fields to the settings class:
- `{REGISTRY_NAME.upper()}_ENABLED: bool = Field(default=False)`
- `{REGISTRY_NAME.upper()}_API_KEY: str | None = Field(default=None)`
- `{REGISTRY_NAME.upper()}_BASE_URL: str = Field(default="{BASE_URL}")`
- `{REGISTRY_NAME.upper()}_MODEL: str = Field(default="{MODEL_NAME}")`

### 3. Update config_resolver.py
In `app/llm/config_resolver.py`:
- Add `elif provider == "{REGISTRY_NAME}":` block in `resolve_llm_config()` for model defaults
- Add `elif provider == "{REGISTRY_NAME}":` block for API key resolution
- Add `elif provider == "{REGISTRY_NAME}":` block in `validate_llm_config()` for credential validation
- Add `"{REGISTRY_NAME}"` to `fallback_order_list`

### 4. Update gateway.py
In `app/llm/gateway.py`, add a model mapping in the failover block:
```python
elif current_prov_name == "{REGISTRY_NAME}":
    provider_request.model = "{MODEL_NAME}"
```

### 5. Update .env.example
Add a new section at the bottom of `.env.example`:
```env
#######################################
# {PROVIDER_NAME}
#######################################
{REGISTRY_NAME.upper()}_API_KEY=
{REGISTRY_NAME.upper()}_BASE_URL={BASE_URL}
{REGISTRY_NAME.upper()}_MODEL={MODEL_NAME}

### 6. Verify
Run: `python -c "from app.llm.provider import provider_registry; p = provider_registry.getProvider('{REGISTRY_NAME}'); print(p.name(), p.is_available())"`
Run: `python -m pytest tests/test_allocator.py tests/test_pk_generator.py tests/test_relationship_planner.py tests/test_validator_ext.py tests/test_semantic_analyzer.py tests/test_pipeline_integration.py tests/test_batch_engine.py -q`
```

---

### Example: Filled Template for Groq

```
Add a new LLM provider called `Groq` to the SafeSeedOps Lite codebase at `C:\Users\lovea\Documents\hackathon\safeseedops-lite`.

## Requirements

- Registry name: `groq`
- Provider class name: `GroqProvider`
- API is OpenAI-compatible (base URL: `https://api.groq.com/openai/v1`)
- Default model: `gemma2-9b-it`
- Available models: `gemma2-9b-it`, `llama-3.3-70b-versatile`, `mixtral-8x7b-32768`

## What to do (in this exact order)
...
```

## Model Routing

The system supports **three modes** of provider selection:

### 1. Static (default via `LLM_PROVIDER`)

Set a single provider in `.env`:
```env
LLM_PROVIDER=fireworks
```
Every request uses this provider.

### 2. Per-request override

Set `provider` on `LLMRequest` or `RenderedPrompt`:
```python
request = LLMRequest(prompt="Generate 10 rows", provider="rocm")
```

Or from `RenderedPrompt`:
```python
prompt.provider = "fireworks"
```

### 3. Auto-routing (`LLM_AUTO_ROUTING=true`)

When **no provider** is specified on the request and `LLM_AUTO_ROUTING=true` (default), the gateway scans the `fallback_order` list, picks the **first available** provider (via `is_available()`), and skips unavailable ones.

```
LLM_AUTO_ROUTING=true
LLM_FALLBACK_ORDER=vertex,gemini,anthropic,openai,fireworks,rocm,ollama
```

On a Windows dev machine, ROCm reports unavailable → auto-router skips it → picks the next working provider. On an AMD Linux box, ROCm reports available → gets priority if it's first in the order.

### 4. Runtime failover (`LLM_AUTO_FAILOVER=true`)

Even after a provider is selected, if it **fails at runtime**, the gateway falls back through the remaining providers in the fallback order (also filtered by `is_available()`).

## Checklist Summary

| Step | File | What to Do |
|------|------|------------|
| 1 | `app/llm/provider.py` | Create provider class + register in `__init__` |
| 2 | `app/core/settings/config.py` | Add env var fields |
| 3 | `app/llm/config_resolver.py` | Add to model defaults, API key resolution, validation |
| 4 | `app/llm/gateway.py` | Add fallback model mapping |
| 5 | `.env.example` | Document env vars |
| 6 | Tests | Run `pytest tests/` to verify nothing broke |
