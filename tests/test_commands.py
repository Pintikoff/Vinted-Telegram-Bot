import pytest

from vinted_bot import commands, db


@pytest.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await db.init_db(path)
    return path


async def test_add_model_command_adds_and_confirms(db_path):
    reply = await commands.add_model_command(db_path, ["carhartt", "detroit", "jacket"])

    assert "Добавлено" in reply
    models = await db.list_tracked_models(db_path)
    assert models[0].search_text == "carhartt detroit jacket"


async def test_add_model_command_requires_args(db_path):
    reply = await commands.add_model_command(db_path, [])

    assert "Укажи текст запроса" in reply


async def test_add_model_command_duplicate_returns_friendly_message(db_path):
    first_reply = await commands.add_model_command(db_path, ["carhartt", "detroit", "jacket"])
    assert "Добавлено" in first_reply

    second_reply = await commands.add_model_command(db_path, ["carhartt", "detroit", "jacket"])

    assert "Уже отслеживается" in second_reply
    assert "carhartt detroit jacket" in second_reply
    models = await db.list_tracked_models(db_path)
    assert len(models) == 1


async def test_remove_model_command_by_id(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")

    reply = await commands.remove_model_command(db_path, [str(model_id)])

    assert "Удалено" in reply
    assert await db.list_tracked_models(db_path) == []


async def test_remove_model_command_by_text(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")

    reply = await commands.remove_model_command(db_path, ["carhartt", "detroit", "jacket"])

    assert "Удалено" in reply


async def test_remove_model_command_not_found(db_path):
    reply = await commands.remove_model_command(db_path, ["999"])

    assert "не найдена" in reply


async def test_list_models_command_empty(db_path):
    reply = await commands.list_models_command(db_path)

    assert "пуст" in reply


async def test_list_models_command_shows_entries(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")

    reply = await commands.list_models_command(db_path)

    assert "carhartt detroit jacket" in reply


async def test_threshold_command_shows_current(db_path):
    reply = await commands.threshold_command(db_path, [])

    assert "30%" in reply


async def test_threshold_command_sets_new_value(db_path):
    reply = await commands.threshold_command(db_path, ["25"])

    assert "25%" in reply
    assert await db.get_threshold_percent(db_path) == 25


async def test_threshold_command_rejects_non_numeric_value(db_path):
    reply = await commands.threshold_command(db_path, ["abc"])

    assert "числом" in reply


async def test_threshold_command_rejects_out_of_range_value(db_path):
    reply = await commands.threshold_command(db_path, ["150"])

    assert "между 1 и 99" in reply


async def test_status_command_reports_counts(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")

    reply = await commands.status_command(db_path, "2026-11-10T12:00:00+00:00", 0)

    assert "1" in reply
    assert "2026-11-10T12:00:00+00:00" in reply
