# Vinted Deal Bot

A homelab Telegram bot that watches specific Vinted search queries (e.g. `carhartt detroit jacket`, `carhartt active jacket`, `dickies polo`) and alerts you when a new listing is priced well below the current market median — for resale sourcing.

## How it works

Every `CHECK_INTERVAL_SECONDS` (default 15 min), the bot:

1. Reads your list of tracked search queries.
2. Searches Vinted for each one and computes the median price across all active listings returned.
3. Flags any **new** listing priced at least `threshold%` below that median (default 30%, adjustable at runtime).
4. Sends you a Telegram message with the listing's price, size, photo, and link.

Each tracked query is a narrow, specific search (not a broad category) so the median stays meaningful — "Detroit jacket" and "Active jacket" are tracked and priced separately. Listings are deduplicated so you're never alerted twice about the same item.

## Setup

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and note the token.
2. Get your own numeric Telegram user ID (e.g. via [@userinfobot](https://t.me/userinfobot)) — only this ID can control the bot.
3. Copy `.env.example` to `.env` and fill in the two required values:

   ```
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_OWNER_ID=your-numeric-user-id
   ```

   Optional overrides (defaults shown):

   ```
   VINTED_DOMAIN=vinted.de
   CHECK_INTERVAL_SECONDS=900
   DB_PATH=/data/bot.db
   ```

## Running with Docker (recommended for a homelab)

```bash
docker compose build
docker compose up -d
```

The tracked-model list, threshold, and seen-items history persist in a SQLite file on a named Docker volume, so they survive container restarts and rebuilds.

## Telegram commands

| Command | Description |
|---|---|
| `/add <search text>` | Start tracking a search query, e.g. `/add carhartt detroit jacket` |
| `/remove <id or text>` | Stop tracking a model |
| `/list` | Show all tracked models with their IDs |
| `/threshold [value]` | Show or set the discount threshold (%) |
| `/status` | Show tracked-model count and last successful check |

Only the Telegram account matching `TELEGRAM_OWNER_ID` can use these commands; everyone else is silently ignored.

## Running without Docker

```bash
pip install -r requirements.txt
python main.py
```

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Design notes

- Median price is computed live from currently active listings each cycle — no historical price database is maintained.
- Only the listing price is compared; shipping cost and size are not factored in.
- A query needs at least 5 active listings before its median is trusted; otherwise it's skipped that cycle.
- The Vinted catalog endpoint is unofficial — see `vinted_bot/vinted_client.py` for the session/retry handling if it ever needs adjusting.

Full design rationale and implementation plan: [`docs/superpowers/specs/`](docs/superpowers/specs/) and [`docs/superpowers/plans/`](docs/superpowers/plans/).
