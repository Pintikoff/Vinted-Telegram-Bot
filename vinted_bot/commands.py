import sqlite3

from vinted_bot import db


async def add_model_command(db_path: str, args: list[str]) -> str:
    search_text = " ".join(args).strip()
    if not search_text:
        return "Укажи текст запроса: /add carhartt detroit jacket"

    try:
        model_id = await db.add_tracked_model(db_path, search_text)
    except sqlite3.IntegrityError:
        return f'Уже отслеживается: "{search_text}"'
    return f'Добавлено: "{search_text}" (id {model_id})'


async def remove_model_command(db_path: str, args: list[str]) -> str:
    if not args:
        return "Укажи id модели: /remove 3"

    identifier = " ".join(args).strip()

    if identifier.isdigit():
        model_id = int(identifier)
    else:
        model_id = None
        for model in await db.list_tracked_models(db_path):
            if model.search_text == identifier:
                model_id = model.id
                break

    if model_id is None:
        return f"Модель не найдена: {identifier}"

    removed = await db.remove_tracked_model(db_path, model_id)
    if removed:
        return f"Удалено (id {model_id})"
    return f"Модель не найдена: {identifier}"


async def list_models_command(db_path: str) -> str:
    models = await db.list_tracked_models(db_path)
    if not models:
        return "Список пуст. Добавь модель: /add carhartt detroit jacket"

    return "\n".join(f"{model.id}. {model.search_text}" for model in models)


async def threshold_command(db_path: str, args: list[str]) -> str:
    if not args:
        current = await db.get_threshold_percent(db_path)
        return f"Текущий порог: {current}%"

    try:
        value = int(args[0])
    except ValueError:
        return "Порог должен быть числом: /threshold 25"

    if not (0 < value < 100):
        return "Порог должен быть между 1 и 99"

    await db.set_threshold_percent(db_path, value)
    return f"Новый порог: {value}%"


async def status_command(
    db_path: str, last_success_at: str | None, consecutive_failure_cycles: int
) -> str:
    models = await db.list_tracked_models(db_path)
    last_check_text = last_success_at if last_success_at else "ещё не было"
    return (
        f"Отслеживается моделей: {len(models)}\n"
        f"Последняя успешная проверка: {last_check_text}\n"
        f"Циклов подряд с ошибками: {consecutive_failure_cycles}"
    )
