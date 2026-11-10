# tests/test_scheduler.py
from unittest.mock import AsyncMock

import pytest

from vinted_bot import db
from vinted_bot.scheduler import SchedulerState, run_check_cycle
from vinted_bot.vinted_client import VintedClientError, VintedItem


@pytest.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await db.init_db(path)
    return path


def make_item(item_id: str, price: float) -> VintedItem:
    return VintedItem(
        item_id=item_id,
        title="Carhartt Detroit Jacket",
        price=price,
        size_title="M",
        photo_url=None,
        url=f"https://www.vinted.de/items/{item_id}",
    )


async def test_run_check_cycle_sends_alert_for_underpriced_item(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item(str(i), price) for i, price in enumerate([20, 25, 28, 30, 32, 35, 18])]
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_awaited()
    assert state.consecutive_failure_cycles == 0
    assert state.last_success_at is not None


async def test_run_check_cycle_does_not_resend_already_seen_item(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item(str(i), price) for i, price in enumerate([20, 25, 28, 30, 32, 35, 18])]
    await db.mark_items_seen(db_path, model_id, [item.item_id for item in items])
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_not_awaited()


async def test_run_check_cycle_skips_model_below_min_sample_size(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item("1", 5.0)]
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_not_awaited()


async def test_run_check_cycle_tracks_consecutive_failures_and_warns(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    vinted_client = AsyncMock()
    vinted_client.search.side_effect = VintedClientError("boom")
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    assert state.consecutive_failure_cycles == 3
    bot.send_message.assert_awaited_once()
    assert "недоступен" in bot.send_message.call_args.kwargs["text"]


async def test_run_check_cycle_resets_failure_count_after_success(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    vinted_client = AsyncMock()
    vinted_client.search.side_effect = VintedClientError("boom")
    bot = AsyncMock()
    state = SchedulerState()
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    vinted_client.search.side_effect = None
    vinted_client.search.return_value = []
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    assert state.consecutive_failure_cycles == 0
