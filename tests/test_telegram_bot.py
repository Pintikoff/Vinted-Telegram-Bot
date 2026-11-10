from types import SimpleNamespace
from unittest.mock import AsyncMock

from vinted_bot.telegram_bot import build_application, owner_only


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
