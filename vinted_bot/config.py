from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_owner_id: int
    vinted_domain: str
    check_interval_seconds: int
    db_path: str


def load_config() -> Config:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    owner_id = os.environ.get("TELEGRAM_OWNER_ID")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not owner_id:
        raise ValueError("TELEGRAM_OWNER_ID environment variable is required")

    return Config(
        telegram_bot_token=token,
        telegram_owner_id=int(owner_id),
        vinted_domain=os.environ.get("VINTED_DOMAIN", "vinted.de"),
        check_interval_seconds=int(os.environ.get("CHECK_INTERVAL_SECONDS", "900")),
        db_path=os.environ.get("DB_PATH", "/data/bot.db"),
    )
