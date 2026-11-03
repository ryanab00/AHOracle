# AHOracle ETL

Parses the `AHOracle.lua` SavedVariables file from the WoW addon and lands
it in a relational database.

## Install

    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate

    pip install -r requirements.txt

## Configure (optional)

Copy `.env.example` to `.env` and edit:

    cp .env.example .env

Set `AHORACLE_DB_URL` to your Postgres connection string, or leave it blank
to use the local SQLite file `ahoracle.db`.

## Run

    # Ingest (auto-detects the SavedVariables file)
    python etl.py ingest

    # Explicit file
    python etl.py --sv-file /path/to/AHOracle.lua ingest

    # Explicit database
    python etl.py --db postgresql+psycopg://user:pass@host/db ingest

    # Inspect what's in the DB
    python etl.py inspect

    # Volume-at-price histogram for an item
    python etl.py volume --item 13463 --days 30

## What `ingest` does

For each faction slot (`Alliance`, `Horde`, `Neutral`) in the SavedVariables:

1. Skips if `(faction, scan_timestamp)` is already in `scan_log`.
2. Loads the current `live_auction_book` rows for that faction.
3. Diffs against the new snapshot → writes to `auction_event_log` with
   `disappearance_type = "VANISHED"`.
4. Deletes the old `live_auction_book` rows and inserts the new ones
   (clean per-faction overwrite).
5. Appends to `scan_snapshots` (append-only history).
6. Upserts `dim_items`.
7. Rebuilds the hour's OHLCV bar in `ohlcv_session`.
8. Records the ingestion in `scan_log`.

## Schema

- `live_auction_book`  — current listings (per faction, replaced each scan)
- `scan_snapshots`     — append-only history
- `dim_items`          — item metadata
- `auction_event_log`  — vanished listings
- `ohlcv_session`      — OHLCV per hour
- `scan_log`           — dedup ledger

Views:

- `v_volume_at_price`         — aggregate units vanished at each price
- `v_volume_at_price_daily`   — same, bucketed by day

## Philosophy on SOLD vs EXPIRED

With 1–2 scans/day the signal is too weak to reliably distinguish a sale
from an expired listing. Rather than guess wrong, every vanish is logged
as `VANISHED`. The `v_volume_at_price` view surfaces the aggregate
distribution — how much supply cleared at each price point — which is the
honest signal at this cadence. A trained classifier can be added later
once months of history exist.

## Known limitations

- `disappearance_type` is always `"VANISHED"` (see above).
- `max_stack_size` and `quality` are NULL in `dim_items` — the addon does
  not capture them. Source these from Wowhead or TSM.
- Single realm only. Multi-realm needs a `realm` column added to all tables.