import functools

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from vinted_bot import commands


def owner_only(owner_id: int):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user is None or update.effective_user.id != owner_id:
                return
            await func(update, context)

        return wrapper

    return decorator


def build_application(token: str, owner_id: int, db_path: str) -> Application:
    application = Application.builder().token(token).build()

    @owner_only(owner_id)
    async def handle_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await commands.add_model_command(db_path, context.args)
        await update.message.reply_text(reply)

    @owner_only(owner_id)
    async def handle_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await commands.remove_model_command(db_path, context.args)
        await update.message.reply_text(reply)

    @owner_only(owner_id)
    async def handle_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await commands.list_models_command(db_path)
        await update.message.reply_text(reply)

    @owner_only(owner_id)
    async def handle_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await commands.threshold_command(db_path, context.args)
        await update.message.reply_text(reply)

    @owner_only(owner_id)
    async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = context.bot_data.get("scheduler_state")
        last_success_at = state.last_success_at if state else None
        consecutive_failures = state.consecutive_failure_cycles if state else 0
        reply = await commands.status_command(db_path, last_success_at, consecutive_failures)
        await update.message.reply_text(reply)

    application.add_handler(CommandHandler("add", handle_add))
    application.add_handler(CommandHandler("remove", handle_remove))
    application.add_handler(CommandHandler("list", handle_list))
    application.add_handler(CommandHandler("threshold", handle_threshold))
    application.add_handler(CommandHandler("status", handle_status))

    return application
