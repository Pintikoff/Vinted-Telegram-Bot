import pytest

from vinted_bot.config import load_config


def test_load_config_reads_required_and_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")
    monkeypatch.delenv("VINTED_DOMAIN", raising=False)
    monkeypatch.delenv("CHECK_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    config = load_config()

    assert config.telegram_bot_token == "test-token"
    assert config.telegram_owner_id == 12345
    assert config.vinted_domain == "vinted.de"
    assert config.check_interval_seconds == 900
    assert config.db_path == "/data/bot.db"


def test_load_config_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        load_config()


def test_load_config_missing_owner_id_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_OWNER_ID"):
        load_config()


def test_load_config_respects_overrides(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")
    monkeypatch.setenv("VINTED_DOMAIN", "vinted.pl")
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")

    config = load_config()

    assert config.vinted_domain == "vinted.pl"
    assert config.check_interval_seconds == 60
    assert config.db_path == "/tmp/custom.db"
