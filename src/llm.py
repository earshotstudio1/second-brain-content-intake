"""
LLM provider router.
Supports: anthropic, openai, google (Gemini)

To add a new provider:
  1. Add it to _PROVIDER_ENV in config.py
  2. Add an elif branch here
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ModelConfig

try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None  # type: ignore[assignment]

try:
    import openai as _openai_sdk
except ImportError:
    _openai_sdk = None  # type: ignore[assignment]

try:
    import google.generativeai as _genai
except ImportError:
    _genai = None  # type: ignore[assignment]


def call_llm(model_config: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    """Route an LLM call to the correct provider. Returns the response text."""
    if model_config.provider == "anthropic":
        return _call_anthropic(model_config, system_prompt, user_prompt)
    elif model_config.provider == "openai":
        return _call_openai(model_config, system_prompt, user_prompt)
    elif model_config.provider == "google":
        return _call_google(model_config, system_prompt, user_prompt)
    else:
        raise ValueError(
            f"Unknown provider {model_config.provider!r}. "
            "Supported providers: anthropic, openai, google"
        )


def call_llm_with_video(model_config: "ModelConfig", prompt: str, video_path: Path) -> str:
    """Analyse a local video file using Gemini's multimodal capability.

    Only supported for provider='google'. Uploads the file to the Gemini
    Files API, waits for processing, then generates content.
    """
    if model_config.provider != "google":
        raise ValueError(
            f"call_llm_with_video requires provider='google', got {model_config.provider!r}"
        )
    if _genai is None:
        raise ImportError("The 'google-generativeai' package is not installed. Run: pip install google-generativeai")

    _genai.configure(api_key=model_config.api_key)

    video_file = _genai.upload_file(path=str(video_path), mime_type="video/mp4")

    # Poll until the file is ready
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = _genai.get_file(video_file.name)

    if video_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file processing failed with state: {video_file.state.name}")

    model = _genai.GenerativeModel(model_config.model)
    response = model.generate_content([prompt, video_file])

    # Clean up the uploaded file
    _genai.delete_file(video_file.name)

    return response.text.strip()


def _call_anthropic(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _anthropic_sdk is None:
        raise ImportError("The 'anthropic' package is not installed. Run: pip install anthropic")
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
        raise ImportError("The 'openai' package is not installed. Run: pip install openai")
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


def _call_google(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _genai is None:
        raise ImportError("The 'google-generativeai' package is not installed. Run: pip install google-generativeai")
    _genai.configure(api_key=cfg.api_key)
    model = _genai.GenerativeModel(
        model_name=cfg.model,
        system_instruction=system_prompt,
    )
    response = model.generate_content(user_prompt)
    return response.text.strip()
