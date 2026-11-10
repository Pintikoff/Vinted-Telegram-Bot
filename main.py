import asyncio
import logging

import httpx

from vinted_bot.config import load_config
from vinted_bot.db import init_db
from vinted_bot.scheduler import SchedulerState, run_forever
from vinted_bot.telegram_bot import build_application
from vinted_bot.vinted_client import VintedClient

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    config = load_config()
    await init_db(config.db_path)

    application = build_application(
        config.telegram_bot_token, config.telegram_owner_id, config.db_path
    )
    state = SchedulerState()
    application.bot_data["scheduler_state"] = state

    async with httpx.AsyncClient() as http_client:
        vinted_client = VintedClient(config.vinted_domain, http_client)

        async with application:
            await application.start()
            await application.updater.start_polling()
            try:
                await run_forever(
                    config.db_path,
                    vinted_client,
                    application.bot,
                    config.telegram_owner_id,
                    config.check_interval_seconds,
                    state,
                )
            finally:
                await application.updater.stop()
                await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
