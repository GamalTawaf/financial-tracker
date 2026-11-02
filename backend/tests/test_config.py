"""Settings defaults."""

from financial_tracker_api.config import Settings, get_settings


def test_get_settings_fills_receipts_dir(monkeypatch, tmp_path) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("RECEIPTS_DIR", raising=False)
    settings = get_settings()
    assert settings.receipts_dir is not None
    assert settings.receipts_dir == settings.data_dir / "receipts"
    get_settings.cache_clear()

    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "custom-receipts"))
    settings = get_settings()
    assert settings.receipts_dir == tmp_path / "custom-receipts"
    get_settings.cache_clear()


def test_docs_enabled_respects_explicit_flag() -> None:
    assert Settings(environment="development", enable_docs=False).docs_enabled() is False
    assert Settings(environment="production", enable_docs=True).docs_enabled() is True
    assert Settings(environment="development", enable_docs=None).docs_enabled() is True
