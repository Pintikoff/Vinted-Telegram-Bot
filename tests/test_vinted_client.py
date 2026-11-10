from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from vinted_bot.vinted_client import USER_AGENT, VintedClient, VintedClientError


@pytest.fixture
async def http_client():
    async with httpx.AsyncClient() as client:
        yield client


@respx.mock
async def test_search_returns_parsed_items(http_client):
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 123,
                        "title": "Carhartt Detroit Jacket",
                        "price": {"amount": "18.0"},
                        "size_title": "M",
                        "photo": {"url": "https://img.example/1.jpg"},
                        "url": "https://www.vinted.de/items/123",
                    }
                ]
            },
        )
    )

    client = VintedClient("vinted.de", http_client)
    items = await client.search("carhartt detroit jacket")

    assert len(items) == 1
    assert items[0].item_id == "123"
    assert items[0].price == 18.0
    assert items[0].size_title == "M"
    assert items[0].photo_url == "https://img.example/1.jpg"
    assert items[0].url == "https://www.vinted.de/items/123"


@respx.mock
async def test_search_handles_missing_photo(http_client):
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 456,
                        "title": "Dickies Polo",
                        "price": {"amount": "10.0"},
                        "size_title": "L",
                        "photo": None,
                        "url": "https://www.vinted.de/items/456",
                    }
                ]
            },
        )
    )

    client = VintedClient("vinted.de", http_client)
    items = await client.search("dickies polo")

    assert items[0].photo_url is None


@respx.mock
async def test_search_raises_after_repeated_failures(http_client):
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(500)
    )

    client = VintedClient("vinted.de", http_client)

    with pytest.raises(VintedClientError):
        await client.search("carhartt detroit jacket")


@respx.mock
async def test_search_reauthenticates_on_403(http_client):
    bootstrap_route = respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    search_route = respx.get("https://www.vinted.de/api/v2/catalog/items")
    search_route.side_effect = [
        httpx.Response(403),
        httpx.Response(200, json={"items": []}),
    ]

    client = VintedClient("vinted.de", http_client)
    items = await client.search("carhartt detroit jacket")

    assert items == []
    assert bootstrap_route.call_count == 2


@respx.mock
async def test_search_wraps_initial_bootstrap_failure(http_client):
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(500))
    catalog_route = respx.get("https://www.vinted.de/api/v2/catalog/items")

    client = VintedClient("vinted.de", http_client)

    with pytest.raises(VintedClientError) as exc_info:
        await client.search("carhartt detroit jacket")

    assert isinstance(exc_info.value.__cause__, httpx.HTTPError)
    assert not catalog_route.called


@respx.mock
async def test_search_raises_with_cause_after_repeated_403(http_client):
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(403)
    )

    client = VintedClient("vinted.de", http_client)

    with pytest.raises(VintedClientError) as exc_info:
        await client.search("carhartt detroit jacket")

    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)
    assert exc_info.value.__cause__.response.status_code == 403


@respx.mock
async def test_search_wraps_malformed_payload_instead_of_crashing(http_client):
    # Finding 2: a payload-shape change (e.g. a missing "id" field) must
    # surface as VintedClientError, not an uncaught KeyError, so that
    # scheduler.py's per-model `except VintedClientError` can isolate it.
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        # "id" key missing entirely -> KeyError inside _parse_items
                        "title": "Carhartt Detroit Jacket",
                        "price": {"amount": "18.0"},
                        "size_title": "M",
                        "photo": None,
                        "url": "https://www.vinted.de/items/123",
                    }
                ]
            },
        )
    )

    client = VintedClient("vinted.de", http_client)

    with patch("vinted_bot.vinted_client.asyncio.sleep", AsyncMock()):
        with pytest.raises(VintedClientError) as exc_info:
            await client.search("carhartt detroit jacket")

    assert isinstance(exc_info.value.__cause__, KeyError)


@respx.mock
async def test_search_sends_user_agent_header(http_client):
    # Finding 4: outgoing requests must carry a realistic browser
    # User-Agent, or Cloudflare-fronted endpoints may 403 the default
    # python-httpx UA.
    bootstrap_route = respx.get("https://www.vinted.de/").mock(
        return_value=httpx.Response(200)
    )
    catalog_route = respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    client = VintedClient("vinted.de", http_client)
    await client.search("carhartt detroit jacket")

    assert bootstrap_route.calls.last.request.headers["user-agent"] == USER_AGENT
    assert catalog_route.calls.last.request.headers["user-agent"] == USER_AGENT


@respx.mock
async def test_search_sleeps_between_retry_attempts_but_not_after_last(http_client):
    # Finding 5: retries must have a delay between attempts (but not delay
    # the happy path, and not delay after the final failed attempt).
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(500)
    )

    client = VintedClient("vinted.de", http_client)

    with patch(
        "vinted_bot.vinted_client.asyncio.sleep", AsyncMock()
    ) as mock_sleep:
        with pytest.raises(VintedClientError):
            await client.search("carhartt detroit jacket")

    # 3 attempts total -> sleep between attempt 1->2 and 2->3, but not after
    # the final (3rd) failed attempt.
    assert mock_sleep.await_count == 2
    for call in mock_sleep.await_args_list:
        assert call.args[0] > 0


@respx.mock
async def test_search_does_not_sleep_on_success(http_client):
    # The happy path must not be delayed by the retry-delay logic.
    respx.get("https://www.vinted.de/").mock(return_value=httpx.Response(200))
    respx.get("https://www.vinted.de/api/v2/catalog/items").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    client = VintedClient("vinted.de", http_client)

    with patch(
        "vinted_bot.vinted_client.asyncio.sleep", AsyncMock()
    ) as mock_sleep:
        await client.search("carhartt detroit jacket")

    mock_sleep.assert_not_awaited()
