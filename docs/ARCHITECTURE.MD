# Architecture

## What this project is

AH Oracle is a market-intelligence tool for **WoW Classic Era** Auction Houses.
It ingests raw auction data, computes profitability for a **curated set of
high-value recipes**, and serves that to a Nuxt dashboard.

It is *not* a general-purpose auction database. Data coverage is deliberately
narrow (see [Data Scope](#data-scope)) so the signal-to-noise ratio stays high
and the free-tier Postgres budget lasts.

---

## High-level data flow

    ┌────────────────────┐
    │  WoW Classic Era   │
    │  ─────────────────  │
    │  AHDB addon         │  /ahdb scan  →  writes AuctionDB.lua
    └──────────┬─────────┘
               │  SavedVariables file on disk
               ▼
    ┌────────────────────┐
    │  Watcher           │  watcher.py or watcher_gui.py
    │  ─────────────────  │  Polls mtime → ingests on stable write
    └──────────┬─────────┘
               │  parse.parse_saved_variables → pipeline.ingest_scan
               ▼
    ┌────────────────────┐
    │  Postgres (Neon)   │  or SQLite for local dev
    │  ─────────────────  │  live_auction_book, ohlcv_session, ...
    └──────────┬─────────┘
               │  SELECTs via SQLAlchemy
               ▼
    ┌────────────────────┐
    │  FastAPI (api/)    │  /items/{id}/history, /consumables, /arbitrage
    └──────────┬─────────┘
               │  HTTP on :8000
               ▼
    ┌────────────────────┐
    │  Nuxt frontend     │  :3000
    └────────────────────┘

---

## Component map

| Path | Role |
|---|---|
| `backend/ahoracle_etl/parse.py`    | Parses `AHOracleDB` **or** `AuctionDBSaved` Lua blobs into a normalised dict |
| `backend/ahoracle_etl/pipeline.py` | Diff-and-ingest: writes `live_auction_book`, detects vanished listings, rebuilds OHLCV |
| `backend/ahoracle_etl/models.py`   | SQLAlchemy schema (see `backend/SCHEMA.md`) |
| `backend/ahoracle_etl/db.py`       | Engine factory + view creation |
| `backend/etl.py`                   | CLI: `ingest`, `inspect`, `volume` |
| `backend/watcher.py`               | Headless watcher: polls SavedVariables mtime, ingests when stable |
| `backend/watcher_gui.py`           | Tkinter wrapper around the same watcher logic |
| `backend/api/main.py`              | FastAPI app factory |
| `backend/api/routes.py`            | All HTTP endpoints |
| `backend/api/recipes.json`         | Canonical recipe list (built by `scripts/build_recipes.py`) |
| `backend/api/items.json`           | Item ID → display name map (built by `scripts/build_recipes.py`) |
| `backend/profession_data/core/`    | Raw recipe data from `LibProfessionDB` (source of truth) |
| `backend/profession_data/name/`    | English names for the same recipes |
| `backend/scripts/build_recipes.py` | Merges `core/` + `name/` → `recipes.json` + `items.json` |
| `frontend/pages/`                  | Nuxt routes: `/`, `/professions`, `/consumables`, `/arbitrage`, `/item/[id]` |
| `frontend/stores/`                 | Pinia stores (faction, auction, item, tool) |
| `start_dev.py`                     | Launches watcher + uvicorn + Nuxt concurrently |

---

## Current data source: AHDB

The live pipeline reads **AHDB** (`AuctionDB.lua`, `AuctionDBSaved` global).
`parse.py` supports this format natively — see `extract_ahdb_scans()`.

Scan workflow today:

1. In game: `/ahdb scan` (takes ~1s for a full AH sweep).
2. `/reload` or log out — WoW writes `AuctionDB.lua` to disk.
3. `watcher.py` sees the mtime change, waits ~3s for stability, ingests.

### The `AHOracle` addon is **not in use**

`Addon/AHOracle/` exists and is functional, but it is **postponed**. Reasons
it has not shipped:

- Live infrastructure still depends on AHDB's data format.
- AHDB is actively maintained and enforces category-scoped scanning (see
  the `scan.categories = { GetAuctionItemClasses() }` logic in
  `AHOracle.lua`) which the current pipeline does not require.
- Migrating users is a support burden we're not ready for.

When the addon *does* ship, `parse.py` already handles its output — the
format-detection branch in `parse_saved_variables()` accepts either
`AHOracleDB` or `AuctionDBSaved`. No pipeline changes will be required to
accept both sources simultaneously.

---

## Data Scope

The dashboard deliberately tracks a **curated subset** of recipes:

- **All Alchemy transmutes** — the `Transmute: *` line.
- **Protection potions** — Greater / regular Fire, Frost, Nature, Shadow,
  Arcane, Holy protection.
- **Damage consumables** — wizard / mana oils, spell-power elixirs,
  flasks (Supreme Power, Titans, Distilled Wisdom, Chromatic Resistance),
  and the Fiery / Demonic weapon elixirs.

**Why so narrow?**

- Profitability on the long tail of recipes is dominated by illiquid markets
  where a single troll listing breaks every calculation.
- The `items.json` map is *incomplete by design* — anything not in the curated
  list falls back to `"Item #<id>"`. That's a bug-reporter trap, not a
  feature: if a user sees `Item #12345` on the dashboard, that item is out
  of scope and should either be added explicitly to `recipes.json` or
  filtered out entirely.

**If you need to expand the list**, edit `backend/scripts/build_recipes.py`
and regenerate — do **not** hand-edit `items.json` or `recipes.json`.
See [CONTRIBUTING.md](./CONTRIBUTING.md#adding-a-recipe).

---

## Storage model (retention)

The Postgres instance is sized for a free tier. Full details in
[`backend/SCHEMA.md`](../backend/SCHEMA.md), but the key retention rules:

| Table | Retention |
|---|---|
| `live_auction_book` | Overwritten per faction per scan |
| `scan_snapshots` | Pruned daily → aggregated into OHLCV |
| `ohlcv_session` | Daily for 3 years, then weekly indefinitely |
| `auction_event_log` | 90 days → rolled into `volume_summary_daily` |
| `dim_items` | Indefinite |
| `scan_log` | Indefinite (dedup ledger) |

---

## Known limitations

- **`dim_items` metadata is sparse** — `max_stack_size` and `quality` are
  NULL because the scanning addon doesn't capture them. Downstream code
  must not assume they're populated.
- **Single realm.** No `realm` column exists; multi-realm would require a
  schema migration on every table.
- **Vanished ≠ sold.** Every disappearance is logged as `VANISHED` because
  at 1–2 scans per day we cannot reliably distinguish a sale from an expiry.
  `volume_summary_daily` surfaces the aggregate signal; a classifier can be
  added later once months of history exist.