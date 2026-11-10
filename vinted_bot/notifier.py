from vinted_bot.vinted_client import VintedItem


def format_deal_message(
    model_search_text: str,
    item: VintedItem,
    median_price: float,
    sample_size: int,
) -> str:
    discount_percent = round((1 - item.price / median_price) * 100)
    title = model_search_text.title()
    return (
        f"🔥 {title} — -{discount_percent}% от медианы\n\n"
        f"Цена: {item.price:.0f} €  (медиана: {median_price:.0f} €, по {sample_size} лотам)\n"
        f"Размер: {item.size_title}\n"
        f"{item.url}"
    )


async def send_deal_alert(bot, chat_id: int, text: str, photo_url: str | None) -> None:
    if photo_url:
        await bot.send_photo(chat_id=chat_id, photo=photo_url, caption=text)
    else:
        await bot.send_message(chat_id=chat_id, text=text)
