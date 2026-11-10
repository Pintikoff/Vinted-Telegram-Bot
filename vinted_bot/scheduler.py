# vinted_bot/scheduler.py
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from vinted_bot import db
from vinted_bot.notifier import format_deal_message, send_deal_alert
from vinted_bot.pricing import evaluate_deal
from vinted_bot.vinted_client import VintedClient, VintedClientError

logger = logging.getLogger(__name__)

FAILURE_WARNING_THRESHOLD = 3


@dataclass
class SchedulerState:
    last_success_at: str | None = None
    consecutive_failure_cycles: int = 0
    warned_about_failures: bool = False


async def run_check_cycle(
    db_path: str,
    vinted_client: VintedClient,
    bot,
    owner_chat_id: int,
    state: SchedulerState,
) -> None:
    await db.purge_old_seen_items(db_path)

    models = await db.list_tracked_models(db_path)
    threshold_percent = await db.get_threshold_percent(db_path)

    any_model_succeeded = False

    for model in models:
        try:
            items = await vinted_client.search(model.search_text)
        except VintedClientError:
            logger.warning("Vinted search failed for model %s", model.search_text)
            continue

        any_model_succeeded = True
        prices = [item.price for item in items]
        all_ids = [item.item_id for item in items]

        unseen_ids = set(await db.filter_unseen_item_ids(db_path, all_ids))
        for item in items:
            if item.item_id not in unseen_ids:
                continue
            result = evaluate_deal(prices, item.price, threshold_percent)
            if result.is_deal:
                text = format_deal_message(
                    model.search_text, item, result.median_price, result.sample_size
                )
                await send_deal_alert(bot, owner_chat_id, text, item.photo_url)

        await db.mark_items_seen(db_path, model.id, all_ids)

    if any_model_succeeded or not models:
        state.last_success_at = datetime.now(timezone.utc).isoformat()
        state.consecutive_failure_cycles = 0
        state.warned_about_failures = False
    else:
        state.consecutive_failure_cycles += 1
        if (
            state.consecutive_failure_cycles >= FAILURE_WARNING_THRESHOLD
            and not state.warned_about_failures
        ):
            await bot.send_message(
                chat_id=owner_chat_id,
                text=f"⚠️ Vinted недоступен уже {state.consecutive_failure_cycles} циклов подряд",
            )
            state.warned_about_failures = True


async def run_forever(
    db_path: str,
    vinted_client: VintedClient,
    bot,
    owner_chat_id: int,
    interval_seconds: int,
    state: SchedulerState,
) -> None:
    while True:
        await run_check_cycle(db_path, vinted_client, bot, owner_chat_id, state)
        await asyncio.sleep(interval_seconds)
