from dataclasses import dataclass

import httpx


class VintedClientError(Exception):
    pass


@dataclass(frozen=True)
class VintedItem:
    item_id: str
    title: str
    price: float
    size_title: str
    photo_url: str | None
    url: str


class VintedClient:
    def __init__(self, domain: str, http_client: httpx.AsyncClient):
        self._domain = domain
        self._http_client = http_client
        self._session_ready = False

    async def search(self, search_text: str, per_page: int = 96) -> list[VintedItem]:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                await self._ensure_session()
                response = await self._http_client.get(
                    f"https://www.{self._domain}/api/v2/catalog/items",
                    params={
                        "search_text": search_text,
                        "order": "newest_first",
                        "per_page": per_page,
                    },
                )
                if response.status_code in (401, 403):
                    last_error = httpx.HTTPStatusError(
                        f"Vinted returned {response.status_code} for catalog request",
                        request=response.request,
                        response=response,
                    )
                    self._session_ready = False
                    await self._ensure_session()
                    continue
                response.raise_for_status()
                return self._parse_items(response.json())
            except httpx.HTTPError as exc:
                last_error = exc

        raise VintedClientError(
            f"Failed to search Vinted for '{search_text}' after 3 attempts"
        ) from last_error

    async def _ensure_session(self) -> None:
        if self._session_ready:
            return
        response = await self._http_client.get(f"https://www.{self._domain}/")
        response.raise_for_status()
        self._session_ready = True

    @staticmethod
    def _parse_items(payload: dict) -> list[VintedItem]:
        items = []
        for raw in payload.get("items", []):
            photo = raw.get("photo") or {}
            items.append(
                VintedItem(
                    item_id=str(raw["id"]),
                    title=raw["title"],
                    price=float(raw["price"]["amount"]),
                    size_title=raw.get("size_title", ""),
                    photo_url=photo.get("url"),
                    url=raw["url"],
                )
            )
        return items
