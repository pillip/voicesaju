"""App factory smoke tests (AC: App factory does not raise on import)."""

from fastapi import FastAPI


def test_create_app_returns_fastapi_instance() -> None:
    from voicesaju.main import create_app

    app = create_app()

    assert isinstance(app, FastAPI)


def test_module_app_is_fastapi_instance() -> None:
    from voicesaju.main import app

    assert isinstance(app, FastAPI)


def test_settings_load_with_defaults() -> None:
    from voicesaju.config import Settings

    settings = Settings()

    assert settings.app_name == "voicesaju"
    assert settings.environment in {"local", "dev", "staging", "prod"}
