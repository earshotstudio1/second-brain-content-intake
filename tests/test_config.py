import os
import pytest
from pathlib import Path
from unittest.mock import patch


def test_google_provider_requires_google_api_key(tmp_path):
    """CaptureConfig raises EnvironmentError if GOOGLE_API_KEY is missing."""
    from src.config import _load_model_config
    raw_models = {"capture_processing": {"provider": "google", "model": "gemini-2.0-flash"}}
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            _load_model_config("capture_processing", raw_models)


def test_google_provider_loads_with_key(tmp_path):
    """CaptureConfig loads correctly when GOOGLE_API_KEY is set."""
    from src.config import _load_model_config
    raw_models = {"capture_processing": {"provider": "google", "model": "gemini-2.0-flash"}}
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        cfg = _load_model_config("capture_processing", raw_models)
    assert cfg.provider == "google"
    assert cfg.model == "gemini-2.0-flash"
    assert cfg.api_key == "fake-key"
