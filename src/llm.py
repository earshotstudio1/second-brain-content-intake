"""
LLM provider router.
Supports: anthropic, openai

To add a new provider later:
  1. Add it to _PROVIDER_ENV in config.py
  2. Add an elif branch here with a _call_<provider>() function
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ModelConfig

# Lazy imports — only the SDK you actually use needs to be installed.
try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None  # type: ignore[assignment]

try:
    import openai as _openai_sdk
except ImportError:
    _openai_sdk = None  # type: ignore[assignment]


def call_llm(model_config: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    """Route an LLM call to the correct provider. Returns the response text."""
    if model_config.provider == "anthropic":
        return _call_anthropic(model_config, system_prompt, user_prompt)
    elif model_config.provider == "openai":
        return _call_openai(model_config, system_prompt, user_prompt)
    else:
        raise ValueError(
            f"Unknown provider {model_config.provider!r}. "
            "Supported providers: anthropic, openai"
        )


def _call_anthropic(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _anthropic_sdk is None:
        raise ImportError(
            "The 'anthropic' package is not installed. "
            "Run: pip install anthropic"
        )
    client = _anthropic_sdk.Anthropic(api_key=cfg.api_key)
    response = client.messages.create(
        model=cfg.model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


def _call_openai(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _openai_sdk is None:
        raise ImportError(
            "The 'openai' package is not installed. "
            "Run: pip install openai"
        )
    client = _openai_sdk.OpenAI(api_key=cfg.api_key)
    response = client.chat.completions.create(
        model=cfg.model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
