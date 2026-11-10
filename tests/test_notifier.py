from unittest.mock import AsyncMock

from vinted_bot.notifier import format_deal_message, send_deal_alert
from vinted_bot.vinted_client import VintedItem


def test_format_deal_message_includes_key_fields():
    item = VintedItem(
        item_id="123",
        title="Carhartt Detroit Jacket size M",
        price=18.0,
        size_title="M",
        photo_url="https://img.example/1.jpg",
        url="https://www.vinted.de/items/123",
    )

    text = format_deal_message(
        "carhartt detroit jacket", item, median_price=31.0, sample_size=23
    )

    assert "-42%" in text
    assert "18 €" in text
    assert "31 €" in text
    assert "23 лотам" in text
    assert "Размер: M" in text
    assert "https://www.vinted.de/items/123" in text


async def test_send_deal_alert_sends_photo_when_url_present():
    bot = AsyncMock()

    await send_deal_alert(bot, chat_id=999, text="hello", photo_url="https://img.example/1.jpg")

    bot.send_photo.assert_awaited_once_with(
        chat_id=999, photo="https://img.example/1.jpg", caption="hello"
    )
    bot.send_message.assert_not_awaited()


async def test_send_deal_alert_falls_back_to_text_when_no_photo():
    bot = AsyncMock()

    await send_deal_alert(bot, chat_id=999, text="hello", photo_url=None)

    bot.send_message.assert_awaited_once_with(chat_id=999, text="hello")
    bot.send_photo.assert_not_awaited()
