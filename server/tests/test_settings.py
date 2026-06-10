from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_reject_invalid_environment() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": "invalid"})


def test_settings_reject_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(port=70000)


def test_env_example_covers_consumed_keys() -> None:
    env_example_path = Path(__file__).resolve().parents[2] / ".env.example"
    env_keys = {
        line.split("=", 1)[0].strip()
        for line in env_example_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    }

    consumed_keys = {name.upper() for name in Settings.model_fields.keys()}
    missing = consumed_keys - env_keys

    assert not missing, f"Missing keys in .env.example: {sorted(missing)}"
