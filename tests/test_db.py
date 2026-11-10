from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from vinted_bot import db


@pytest.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await db.init_db(path)
    return path


async def test_add_and_list_tracked_models(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")

    models = await db.list_tracked_models(db_path)

    assert len(models) == 1
    assert models[0].id == model_id
    assert models[0].search_text == "carhartt detroit jacket"


async def test_remove_tracked_model(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")

    removed = await db.remove_tracked_model(db_path, model_id)
    models = await db.list_tracked_models(db_path)

    assert removed is True
    assert models == []


async def test_remove_tracked_model_returns_false_when_missing(db_path):
    removed = await db.remove_tracked_model(db_path, 999)

    assert removed is False


async def test_threshold_defaults_to_30(db_path):
    threshold = await db.get_threshold_percent(db_path)

    assert threshold == 30


async def test_set_and_get_threshold(db_path):
    await db.set_threshold_percent(db_path, 25)

    threshold = await db.get_threshold_percent(db_path)

    assert threshold == 25


async def test_set_threshold_overwrites_previous_value(db_path):
    await db.set_threshold_percent(db_path, 25)
    await db.set_threshold_percent(db_path, 40)

    threshold = await db.get_threshold_percent(db_path)

    assert threshold == 40


async def test_filter_unseen_item_ids(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")
    await db.mark_items_seen(db_path, model_id, ["item-1"])

    unseen = await db.filter_unseen_item_ids(db_path, ["item-1", "item-2"])

    assert unseen == ["item-2"]


async def test_filter_unseen_item_ids_handles_empty_list(db_path):
    unseen = await db.filter_unseen_item_ids(db_path, [])

    assert unseen == []


async def test_purge_old_seen_items(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO seen_items (item_id, model_id, first_seen_at) VALUES (?, ?, ?)",
            ("old-item", model_id, old_time),
        )
        await conn.commit()

    deleted_count = await db.purge_old_seen_items(db_path, older_than_days=30)
    unseen = await db.filter_unseen_item_ids(db_path, ["old-item"])

    assert deleted_count == 1
    assert unseen == ["old-item"]
