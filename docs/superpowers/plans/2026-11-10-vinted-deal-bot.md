# Vinted Deal Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python bot that polls Vinted for underpriced listings of specific tracked
models (e.g. "carhartt detroit jacket") and alerts the owner on Telegram, managed entirely
through Telegram commands, deployable as a single Docker container on a homelab.

**Architecture:** One asyncio process running two concurrent loops sharing a SQLite file: a
scheduler that polls Vinted's unofficial catalog API every N seconds and evaluates deals by
comparing each new listing's price to the median of all active listings for that search
query, and a Telegram bot (long polling) that lets the owner manage the tracked-model list
and discount threshold.

**Tech Stack:** Python 3.12, `httpx` (async HTTP), `aiosqlite` (async SQLite), 
`python-telegram-bot` 21.x (async Telegram), `pytest` + `pytest-asyncio` + `respx` for testing.

## Global Constraints

- Vinted domain: default `vinted.de` (from spec).
- Check interval: default `900` seconds / 15 minutes (from spec), configurable via
  `CHECK_INTERVAL_SECONDS` env var.
- Discount threshold: default `30%`, user-configurable at runtime via `/threshold` Telegram
  command, persisted in the `settings` table (from spec).
- Minimum active listings required to trust a median: `5`, hardcoded, not user-configurable
  (from spec).
- `seen_items` retention: purge entries older than `30` days (from spec).
- Telegram command access restricted to the single `TELEGRAM_OWNER_ID`; all other users are
  silently ignored (from spec).
- Price comparison uses item price only — shipping cost is excluded, and size is not used
  when computing the median (from spec).
- Storage is a single SQLite file on a Docker volume; the container restarts with
  `restart: unless-stopped` (from spec).
- After `3` consecutive fully-failed check cycles (every tracked model failed), send one
  warning message to the owner and don't repeat it until a cycle succeeds again (this
  specific number is a plan-level decision — the spec only said "repeated failures").

---

### Task 1: Project scaffolding and config loading

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `vinted_bot/__init__.py`
- Create: `vinted_bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass with fields `telegram_bot_token: str`,
  `telegram_owner_id: int`, `vinted_domain: str`, `check_interval_seconds: int`,
  `db_path: str`. `load_config() -> Config` reads from `os.environ`, raises `ValueError` if
  `TELEGRAM_BOT_TOKEN` or `TELEGRAM_OWNER_ID` is missing.

- [ ] **Step 1: Create scaffolding files**

`requirements.txt`:
```
httpx==0.27.2
aiosqlite==0.20.0
python-telegram-bot==21.6
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
*.db
.venv/
```

`vinted_bot/__init__.py`: empty file.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
import pytest

from vinted_bot.config import load_config


def test_load_config_reads_required_and_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")
    monkeypatch.delenv("VINTED_DOMAIN", raising=False)
    monkeypatch.delenv("CHECK_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    config = load_config()

    assert config.telegram_bot_token == "test-token"
    assert config.telegram_owner_id == 12345
    assert config.vinted_domain == "vinted.de"
    assert config.check_interval_seconds == 900
    assert config.db_path == "/data/bot.db"


def test_load_config_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        load_config()


def test_load_config_missing_owner_id_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_OWNER_ID"):
        load_config()


def test_load_config_respects_overrides(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "12345")
    monkeypatch.setenv("VINTED_DOMAIN", "vinted.pl")
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")

    config = load_config()

    assert config.vinted_domain == "vinted.pl"
    assert config.check_interval_seconds == 60
    assert config.db_path == "/tmp/custom.db"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pip install -r requirements-dev.txt && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.config'`

- [ ] **Step 4: Write minimal implementation**

```python
# vinted_bot/config.py
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_owner_id: int
    vinted_domain: str
    check_interval_seconds: int
    db_path: str


def load_config() -> Config:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    owner_id = os.environ.get("TELEGRAM_OWNER_ID")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not owner_id:
        raise ValueError("TELEGRAM_OWNER_ID environment variable is required")

    return Config(
        telegram_bot_token=token,
        telegram_owner_id=int(owner_id),
        vinted_domain=os.environ.get("VINTED_DOMAIN", "vinted.de"),
        check_interval_seconds=int(os.environ.get("CHECK_INTERVAL_SECONDS", "900")),
        db_path=os.environ.get("DB_PATH", "/data/bot.db"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt pyproject.toml .gitignore vinted_bot/__init__.py vinted_bot/config.py tests/test_config.py
git commit -m "feat: add project scaffolding and config loading"
```

---

### Task 2: SQLite data layer

**Files:**
- Create: `vinted_bot/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `TrackedModel` dataclass: `id: int`, `search_text: str`, `added_at: str`.
  - `DEFAULT_THRESHOLD_PERCENT: int = 30`.
  - `async def init_db(db_path: str) -> None`
  - `async def add_tracked_model(db_path: str, search_text: str) -> int`
  - `async def remove_tracked_model(db_path: str, model_id: int) -> bool`
  - `async def list_tracked_models(db_path: str) -> list[TrackedModel]`
  - `async def get_threshold_percent(db_path: str) -> int`
  - `async def set_threshold_percent(db_path: str, value: int) -> None`
  - `async def filter_unseen_item_ids(db_path: str, item_ids: list[str]) -> list[str]`
  - `async def mark_items_seen(db_path: str, model_id: int, item_ids: list[str]) -> None`
  - `async def purge_old_seen_items(db_path: str, older_than_days: int = 30) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.db'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/db.py
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

DEFAULT_THRESHOLD_PERCENT = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_text TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_items (
    item_id TEXT PRIMARY KEY,
    model_id INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class TrackedModel:
    id: int
    search_text: str
    added_at: str


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()


async def add_tracked_model(db_path: str, search_text: str) -> int:
    added_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO tracked_models (search_text, added_at) VALUES (?, ?)",
            (search_text, added_at),
        )
        await conn.commit()
        return cursor.lastrowid


async def remove_tracked_model(db_path: str, model_id: int) -> bool:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("DELETE FROM tracked_models WHERE id = ?", (model_id,))
        await conn.commit()
        return cursor.rowcount > 0


async def list_tracked_models(db_path: str) -> list[TrackedModel]:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT id, search_text, added_at FROM tracked_models ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [TrackedModel(row[0], row[1], row[2]) for row in rows]


async def get_threshold_percent(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT value FROM settings WHERE key = 'threshold_percent'"
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else DEFAULT_THRESHOLD_PERCENT


async def set_threshold_percent(db_path: str, value: int) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ('threshold_percent', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(value),),
        )
        await conn.commit()


async def filter_unseen_item_ids(db_path: str, item_ids: list[str]) -> list[str]:
    if not item_ids:
        return []
    async with aiosqlite.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in item_ids)
        cursor = await conn.execute(
            f"SELECT item_id FROM seen_items WHERE item_id IN ({placeholders})",
            item_ids,
        )
        rows = await cursor.fetchall()
        seen = {row[0] for row in rows}
        return [item_id for item_id in item_ids if item_id not in seen]


async def mark_items_seen(db_path: str, model_id: int, item_ids: list[str]) -> None:
    if not item_ids:
        return
    first_seen_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            "INSERT OR IGNORE INTO seen_items (item_id, model_id, first_seen_at) "
            "VALUES (?, ?, ?)",
            [(item_id, model_id, first_seen_at) for item_id in item_ids],
        )
        await conn.commit()


async def purge_old_seen_items(db_path: str, older_than_days: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("DELETE FROM seen_items WHERE first_seen_at < ?", (cutoff,))
        await conn.commit()
        return cursor.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/db.py tests/test_db.py
git commit -m "feat: add SQLite data layer for tracked models, settings, seen items"
```

---

### Task 3: Deal-evaluation logic

**Files:**
- Create: `vinted_bot/pricing.py`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `MIN_SAMPLE_SIZE: int = 5`
  - `DealResult` dataclass: `is_deal: bool`, `median_price: float`, `sample_size: int`.
  - `def evaluate_deal(prices: list[float], item_price: float, threshold_percent: int) -> DealResult`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pricing.py
from vinted_bot.pricing import evaluate_deal


def test_not_a_deal_when_sample_too_small():
    result = evaluate_deal(prices=[10, 12, 15], item_price=5, threshold_percent=30)

    assert result.is_deal is False
    assert result.sample_size == 3


def test_is_deal_when_price_below_threshold():
    prices = [20, 25, 28, 30, 32, 35, 40]
    result = evaluate_deal(prices=prices, item_price=18, threshold_percent=30)

    assert result.sample_size == 7
    assert result.median_price == 30
    assert result.is_deal is True


def test_not_a_deal_when_price_above_threshold():
    prices = [20, 25, 28, 30, 32, 35, 40]
    result = evaluate_deal(prices=prices, item_price=25, threshold_percent=30)

    assert result.is_deal is False
    assert result.median_price == 30


def test_boundary_price_exactly_at_threshold_counts_as_deal():
    prices = [20, 25, 30, 35, 40]
    result = evaluate_deal(prices=prices, item_price=21, threshold_percent=30)

    assert result.median_price == 30
    assert result.is_deal is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pricing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.pricing'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/pricing.py
from dataclasses import dataclass
from statistics import median

MIN_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class DealResult:
    is_deal: bool
    median_price: float
    sample_size: int


def evaluate_deal(prices: list[float], item_price: float, threshold_percent: int) -> DealResult:
    sample_size = len(prices)
    if sample_size < MIN_SAMPLE_SIZE:
        return DealResult(is_deal=False, median_price=0.0, sample_size=sample_size)

    median_price = median(prices)
    cutoff = median_price * (1 - threshold_percent / 100)
    return DealResult(
        is_deal=item_price <= cutoff,
        median_price=median_price,
        sample_size=sample_size,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pricing.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/pricing.py tests/test_pricing.py
git commit -m "feat: add median-based deal evaluation logic"
```

---

### Task 4: Vinted API client

**Files:**
- Create: `vinted_bot/vinted_client.py`
- Test: `tests/test_vinted_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (uses `httpx.AsyncClient` directly).
- Produces:
  - `VintedItem` dataclass: `item_id: str`, `title: str`, `price: float`,
    `size_title: str`, `photo_url: str | None`, `url: str`.
  - `VintedClientError(Exception)`.
  - `class VintedClient`: `__init__(self, domain: str, http_client: httpx.AsyncClient)`,
    `async def search(self, search_text: str, per_page: int = 96) -> list[VintedItem]`
    (raises `VintedClientError` after 3 failed attempts).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vinted_client.py
import httpx
import pytest
import respx

from vinted_bot.vinted_client import VintedClient, VintedClientError


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_vinted_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.vinted_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/vinted_client.py
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
        await self._ensure_session()

        last_error: Exception | None = None
        for _ in range(3):
            try:
                response = await self._http_client.get(
                    f"https://www.{self._domain}/api/v2/catalog/items",
                    params={
                        "search_text": search_text,
                        "order": "newest_first",
                        "per_page": per_page,
                    },
                )
                if response.status_code in (401, 403):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_vinted_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/vinted_client.py tests/test_vinted_client.py
git commit -m "feat: add Vinted catalog API client with session bootstrap and retries"
```

---

### Task 5: Notification formatting and sending

**Files:**
- Create: `vinted_bot/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: `VintedItem` from Task 4 (`vinted_bot.vinted_client`).
- Produces:
  - `def format_deal_message(model_search_text: str, item: VintedItem, median_price: float, sample_size: int) -> str`
  - `async def send_deal_alert(bot, chat_id: int, text: str, photo_url: str | None) -> None`
    (calls `bot.send_photo(chat_id=..., photo=..., caption=...)` when `photo_url` is set,
    else `bot.send_message(chat_id=..., text=...)`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_notifier.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.notifier'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/notifier.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/notifier.py tests/test_notifier.py
git commit -m "feat: add deal notification formatting and sending"
```

---

### Task 6: Telegram command logic

**Files:**
- Create: `vinted_bot/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: `db` module functions from Task 2 (`vinted_bot.db`).
- Produces:
  - `async def add_model_command(db_path: str, args: list[str]) -> str`
  - `async def remove_model_command(db_path: str, args: list[str]) -> str`
  - `async def list_models_command(db_path: str) -> str`
  - `async def threshold_command(db_path: str, args: list[str]) -> str`
  - `async def status_command(db_path: str, last_success_at: str | None, consecutive_failure_cycles: int) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_commands.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.commands'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/commands.py
from vinted_bot import db


async def add_model_command(db_path: str, args: list[str]) -> str:
    search_text = " ".join(args).strip()
    if not search_text:
        return "Укажи текст запроса: /add carhartt detroit jacket"

    model_id = await db.add_tracked_model(db_path, search_text)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_commands.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/commands.py tests/test_commands.py
git commit -m "feat: add Telegram command business logic"
```

---

### Task 7: Telegram bot wiring with owner-only access

**Files:**
- Create: `vinted_bot/telegram_bot.py`
- Test: `tests/test_telegram_bot.py`

**Interfaces:**
- Consumes: `commands` module from Task 6 (`vinted_bot.commands`).
- Produces:
  - `def owner_only(owner_id: int)` — decorator factory; wraps an
    `async def handler(update, context)` so it only runs when
    `update.effective_user.id == owner_id`.
  - `def build_application(token: str, owner_id: int, db_path: str) -> telegram.ext.Application`
    — registers `/add`, `/remove`, `/list`, `/threshold`, `/status` command handlers. The
    `/status` handler reads a `SchedulerState` (Task 8) from
    `application.bot_data["scheduler_state"]` if present, otherwise treats it as never having
    run.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_telegram_bot.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.telegram_bot'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/telegram_bot.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: wire Telegram command handlers with owner-only access"
```

---

### Task 8: Scheduler loop

**Files:**
- Create: `vinted_bot/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `db` (Task 2), `evaluate_deal`/`DealResult` (Task 3, `vinted_bot.pricing`),
  `VintedClient`/`VintedClientError`/`VintedItem` (Task 4), `format_deal_message`/
  `send_deal_alert` (Task 5).
- Produces:
  - `FAILURE_WARNING_THRESHOLD: int = 3`
  - `SchedulerState` dataclass: `last_success_at: str | None = None`,
    `consecutive_failure_cycles: int = 0`, `warned_about_failures: bool = False`. Consumed
    by Task 7's `/status` handler via these exact field names.
  - `async def run_check_cycle(db_path: str, vinted_client: VintedClient, bot, owner_chat_id: int, state: SchedulerState) -> None`
  - `async def run_forever(db_path: str, vinted_client: VintedClient, bot, owner_chat_id: int, interval_seconds: int, state: SchedulerState) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scheduler.py
from unittest.mock import AsyncMock

import pytest

from vinted_bot import db
from vinted_bot.scheduler import SchedulerState, run_check_cycle
from vinted_bot.vinted_client import VintedClientError, VintedItem


@pytest.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await db.init_db(path)
    return path


def make_item(item_id: str, price: float) -> VintedItem:
    return VintedItem(
        item_id=item_id,
        title="Carhartt Detroit Jacket",
        price=price,
        size_title="M",
        photo_url=None,
        url=f"https://www.vinted.de/items/{item_id}",
    )


async def test_run_check_cycle_sends_alert_for_underpriced_item(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item(str(i), price) for i, price in enumerate([20, 25, 28, 30, 32, 35, 18])]
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_awaited()
    assert state.consecutive_failure_cycles == 0
    assert state.last_success_at is not None


async def test_run_check_cycle_does_not_resend_already_seen_item(db_path):
    model_id = await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item(str(i), price) for i, price in enumerate([20, 25, 28, 30, 32, 35, 18])]
    await db.mark_items_seen(db_path, model_id, [item.item_id for item in items])
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_not_awaited()


async def test_run_check_cycle_skips_model_below_min_sample_size(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    items = [make_item("1", 5.0)]
    vinted_client = AsyncMock()
    vinted_client.search.return_value = items
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    bot.send_message.assert_not_awaited()


async def test_run_check_cycle_tracks_consecutive_failures_and_warns(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    vinted_client = AsyncMock()
    vinted_client.search.side_effect = VintedClientError("boom")
    bot = AsyncMock()
    state = SchedulerState()

    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    assert state.consecutive_failure_cycles == 3
    bot.send_message.assert_awaited_once()
    assert "недоступен" in bot.send_message.call_args.kwargs["text"]


async def test_run_check_cycle_resets_failure_count_after_success(db_path):
    await db.add_tracked_model(db_path, "carhartt detroit jacket")
    vinted_client = AsyncMock()
    vinted_client.search.side_effect = VintedClientError("boom")
    bot = AsyncMock()
    state = SchedulerState()
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    vinted_client.search.side_effect = None
    vinted_client.search.return_value = []
    await run_check_cycle(db_path, vinted_client, bot, owner_chat_id=999, state=state)

    assert state.consecutive_failure_cycles == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vinted_bot.scheduler'`

- [ ] **Step 3: Write minimal implementation**

```python
# vinted_bot/scheduler.py
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from vinted_bot import db
from vinted_bot.notifier import format_deal_message, send_deal_alert
from vinted_bot.pricing import evaluate_deal
from vinted_bot.vinted_client import VintedClient, VintedClientError

logger = logging.getLogger(__name__)

FAILURE_WARNING_THRESHOLD = 3


@dataclass
class SchedulerState:
    last_success_at: str | None = None
    consecutive_failure_cycles: int = 0
    warned_about_failures: bool = False


async def run_check_cycle(
    db_path: str,
    vinted_client: VintedClient,
    bot,
    owner_chat_id: int,
    state: SchedulerState,
) -> None:
    await db.purge_old_seen_items(db_path)

    models = await db.list_tracked_models(db_path)
    threshold_percent = await db.get_threshold_percent(db_path)

    any_model_succeeded = False

    for model in models:
        try:
            items = await vinted_client.search(model.search_text)
        except VintedClientError:
            logger.warning("Vinted search failed for model %s", model.search_text)
            continue

        any_model_succeeded = True
        prices = [item.price for item in items]
        all_ids = [item.item_id for item in items]

        unseen_ids = set(await db.filter_unseen_item_ids(db_path, all_ids))
        for item in items:
            if item.item_id not in unseen_ids:
                continue
            result = evaluate_deal(prices, item.price, threshold_percent)
            if result.is_deal:
                text = format_deal_message(
                    model.search_text, item, result.median_price, result.sample_size
                )
                await send_deal_alert(bot, owner_chat_id, text, item.photo_url)

        await db.mark_items_seen(db_path, model.id, all_ids)

    if any_model_succeeded or not models:
        state.last_success_at = datetime.now(timezone.utc).isoformat()
        state.consecutive_failure_cycles = 0
        state.warned_about_failures = False
    else:
        state.consecutive_failure_cycles += 1
        if (
            state.consecutive_failure_cycles >= FAILURE_WARNING_THRESHOLD
            and not state.warned_about_failures
        ):
            await bot.send_message(
                chat_id=owner_chat_id,
                text=f"⚠️ Vinted недоступен уже {state.consecutive_failure_cycles} циклов подряд",
            )
            state.warned_about_failures = True


async def run_forever(
    db_path: str,
    vinted_client: VintedClient,
    bot,
    owner_chat_id: int,
    interval_seconds: int,
    state: SchedulerState,
) -> None:
    while True:
        await run_check_cycle(db_path, vinted_client, bot, owner_chat_id, state)
        await asyncio.sleep(interval_seconds)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add vinted_bot/scheduler.py tests/test_scheduler.py
git commit -m "feat: add scheduler loop with deal alerts and failure tracking"
```

---

### Task 9: Entrypoint wiring

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `init_db` (Task 2), `build_application` (Task 7),
  `SchedulerState`/`run_forever` (Task 8), `VintedClient` (Task 4).
- Produces: `async def main() -> None` — the process entrypoint.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
import inspect

import main


def test_main_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(main.main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write minimal implementation**

```python
# main.py
import asyncio
import logging

import httpx

from vinted_bot.config import load_config
from vinted_bot.db import init_db
from vinted_bot.scheduler import SchedulerState, run_forever
from vinted_bot.telegram_bot import build_application
from vinted_bot.vinted_client import VintedClient

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    config = load_config()
    await init_db(config.db_path)

    application = build_application(
        config.telegram_bot_token, config.telegram_owner_id, config.db_path
    )
    state = SchedulerState()
    application.bot_data["scheduler_state"] = state

    async with httpx.AsyncClient() as http_client:
        vinted_client = VintedClient(config.vinted_domain, http_client)

        async with application:
            await application.start()
            await application.updater.start_polling()
            try:
                await run_forever(
                    config.db_path,
                    vinted_client,
                    application.bot,
                    config.telegram_owner_id,
                    config.check_interval_seconds,
                    state,
                )
            finally:
                await application.updater.stop()
                await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Manual smoke test**

1. Create a disposable Telegram bot via `@BotFather`, grab the token and your own numeric
   `user_id` (e.g. via `@userinfobot`).
2. Run locally: `TELEGRAM_BOT_TOKEN=... TELEGRAM_OWNER_ID=... DB_PATH=/tmp/bot.db python main.py`
3. In Telegram, send `/list` (expect "Список пуст..."), then `/add carhartt detroit jacket`,
   then `/list` again (expect the model to show up), then `/threshold 25` (expect
   confirmation), then `/status` (expect counts).
4. Stop the process with Ctrl+C once confirmed.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: wire scheduler and Telegram bot into process entrypoint"
```

---

### Task 10: Docker deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Interfaces:**
- Consumes: `main.py` (Task 9) as the container's entrypoint.
- Produces: a buildable Docker image and a `docker-compose.yml` service definition.

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vinted_bot/ vinted_bot/
COPY main.py .

CMD ["python", "main.py"]
```

- [ ] **Step 2: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  vinted-bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - vinted-bot-data:/data

volumes:
  vinted-bot-data:
```

- [ ] **Step 3: Write .env.example**

```
# .env.example
TELEGRAM_BOT_TOKEN=
TELEGRAM_OWNER_ID=
VINTED_DOMAIN=vinted.de
CHECK_INTERVAL_SECONDS=900
DB_PATH=/data/bot.db
```

- [ ] **Step 4: Build the image**

Run: `docker compose build`
Expected: image builds successfully with no errors.

- [ ] **Step 5: Manual smoke test in container**

1. Copy `.env.example` to `.env` and fill in real `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID`.
2. Run: `docker compose up`
3. Repeat the Telegram command checks from Task 9 Step 5 against the containerized bot.
4. Stop with `docker compose down` — confirm `docker compose up` again afterwards still
   remembers the tracked model added earlier (volume persistence).

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .env.example
git commit -m "feat: add Docker deployment for homelab"
```

---

## Self-Review Notes

- **Spec coverage:** median-based deal criterion (Task 3), narrow per-model search queries
  with no size segmentation (Task 2 schema + Task 8 usage), fixed user-configurable threshold
  (Task 2 settings + Task 6 `/threshold`), live-snapshot median with 5-listing minimum
  (Task 3/8), own Vinted API client (Task 4), Telegram command management of tracked models
  (Task 6/7), 15-minute default interval (Task 1 config), price-only comparison with no
  shipping/size (Task 3), error handling and failure warning (Task 8), Docker deployment with
  persistent volume (Task 10) — all covered.
- **Placeholder scan:** no TBD/TODO markers; every step has runnable code.
- **Type consistency:** `VintedItem` fields match across Tasks 4/5/8; `TrackedModel` fields
  match across Tasks 2/6; `SchedulerState` field names match between Task 8's producer and
  Task 7's `/status` consumer.
