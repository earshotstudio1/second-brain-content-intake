"""
Configuration loader.
Reads config.yaml and environment variables, validates paths, creates
vault directories if they don't already exist.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"

# Maps provider name → expected environment variable name.
# Add new providers here when extending src/llm.py.
_PROVIDER_ENV: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass
class ModelConfig:
    """Holds everything needed to make a single LLM call."""
    provider: str
    model: str
    api_key: str


@dataclass
class Config:
    vault_path: Path
    input_dir: Path
    output_dir: Path
    tracking_file: Path
    supported_extensions: List[str]
    models: Dict[str, ModelConfig]  # workflow name → model config


def _load_model_config(workflow: str, raw_models: dict) -> ModelConfig:
    """Parse and validate one workflow entry from the models: section."""
    entry = raw_models.get(workflow)
    if not entry:
        raise ValueError(
            f"models.{workflow} is not configured in config.yaml. "
            f"Add a provider and model for it."
        )

    provider = str(entry.get("provider", "")).strip().lower()
    model = str(entry.get("model", "")).strip()

    if not provider:
        raise ValueError(f"models.{workflow}.provider is required in config.yaml")
    if not model:
        raise ValueError(f"models.{workflow}.model is required in config.yaml")

    env_var = _PROVIDER_ENV.get(provider)
    if env_var is None:
        raise ValueError(
            f"models.{workflow}.provider is {provider!r}, which is not supported. "
            f"Supported providers: {', '.join(_PROVIDER_ENV)}"
        )

    api_key = os.environ.get(env_var, "").strip()
    if not api_key:
        raise EnvironmentError(
            f"{env_var} is not set. "
            f"Add it to your .env file (required for provider '{provider}', "
            f"used by models.{workflow})."
        )

    return ModelConfig(provider=provider, model=model, api_key=api_key)


def load_config() -> Config:
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {_CONFIG_FILE}. "
            "Copy config.yaml.example to config.yaml and edit it."
        )

    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    vault_path = Path(raw["vault_path"])
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")

    input_dir = vault_path / raw["input_folder"]
    output_dir = vault_path / raw["output_folder"]
    tracking_file = vault_path / raw["tracking_file"]

    output_dir.mkdir(parents=True, exist_ok=True)
    tracking_file.parent.mkdir(parents=True, exist_ok=True)

    raw_models = raw.get("models", {})
    models = {
        "transcript_processing": _load_model_config("transcript_processing", raw_models),
    }

    return Config(
        vault_path=vault_path,
        input_dir=input_dir,
        output_dir=output_dir,
        tracking_file=tracking_file,
        supported_extensions=raw.get("supported_extensions", [".txt"]),
        models=models,
    )
