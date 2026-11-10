from types import SimpleNamespace
from unittest.mock import AsyncMock

from vinted_bot import db
from vinted_bot.telegram_bot import build_application, owner_only


def _get_handler(application, command_name):
    for handler in application.handlers[0]:
        if command_name in handler.commands:
            return handler.callback
    raise AssertionError(f"no handler registered for /{command_name}")


async def test_owner_only_calls_wrapped_function_for_owner():
    called = AsyncMock()
    wrapped = owner_only(owner_id=42)(called)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=42))
    context = SimpleNamespace()

    await wrapped(update, context)

    called.assert_awaited_once_with(update, context)


async def test_owner_only_ignores_other_users():
    called = AsyncMock()
    wrapped = owner_only(owner_id=42)(called)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=999))
    context = SimpleNamespace()

    await wrapped(update, context)

    called.assert_not_awaited()


async def test_owner_only_ignores_missing_user():
    called = AsyncMock()
    wrapped = owner_only(owner_id=42)(called)
    update = SimpleNamespace(effective_user=None)
    context = SimpleNamespace()

    await wrapped(update, context)

    called.assert_not_awaited()


def test_build_application_registers_all_commands():
    application = build_application("fake-token", owner_id=42, db_path="/tmp/test.db")

    command_names = set()
    for handler in application.handlers[0]:
        command_names.update(handler.commands)

    assert command_names == {"add", "remove", "list", "threshold", "status"}


async def test_handle_add_replies_when_update_message_is_none(tmp_path):
    db_path = str(tmp_path / "test.db")
    await db.init_db(db_path)
    application = build_application("fake-token", owner_id=42, db_path=db_path)
    handle_add = _get_handler(application, "add")

    effective_message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=None,
        effective_message=effective_message,
    )
    context = SimpleNamespace(args=["carhartt", "detroit", "jacket"])

    await handle_add(update, context)

    effective_message.reply_text.assert_awaited_once()


async def test_handle_status_replies_when_update_message_is_none(tmp_path):
    db_path = str(tmp_path / "test.db")
    await db.init_db(db_path)
    application = build_application("fake-token", owner_id=42, db_path=db_path)
    handle_status = _get_handler(application, "status")

    effective_message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=None,
        effective_message=effective_message,
    )
    context = SimpleNamespace(args=[], bot_data={})

    await handle_status(update, context)

    effective_message.reply_text.assert_awaited_once()
