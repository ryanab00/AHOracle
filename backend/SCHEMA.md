# AH Oracle Database Schema

This document describes the Postgres database schema used by AH Oracle. 
It is designed to be highly compressed for the free tier while retaining enough 
granularity to power historical market trend analysis and LLM-driven trading logic.

## 📊 Architecture Overview
The ETL pipeline operates on a rolling retention model:
1. **Live State:** Current auctions are kept in `live_auction_book`.
2. **Raw History:** Every scan is appended to `scan_snapshots` (deleted at midnight UTC).
3. **Aggregated History:** Raw scans are compressed into `ohlcv_session` (daily/weekly) and `volume_summary_daily`.
4. **Vanish Events:** Items that disappear are logged in `auction_event_log` (retained for 90 days) and summarized daily.

---

## 🗄️ Tables

### `live_auction_book`
The current snapshot of the Auction House. This table is completely wiped and 
rewritten for a faction every time a new scan is ingested.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `BIGSERIAL` | Primary Key |
| `scan_timestamp` | `BIGINT` | Unix epoch of the scan |
| `faction` | `VARCHAR(10)` | `Horde`, `Alliance`, or `Neutral` |
| `item_id` | `INTEGER` | Blizzard Item ID |
| `item_name` | `VARCHAR(100)` | Localized name of the item |
| `seller` | `VARCHAR(50)` | Name of the player selling (if available) |
| `stack_size` | `INTEGER` | Number of items in the stack |
| `unit_buyout_price` | `INTEGER` | Price per single item in copper |
| `duration_hours` | `INTEGER` | Auction duration (24, 8, 2, etc.) |

### `scan_snapshots`
An append-only log of every scan. **Retention: Current Day Only.**
At midnight UTC, all rows older than 24 hours are aggregated and deleted to save space.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `BIGSERIAL` | Primary Key |
| `scan_timestamp` | `BIGINT` | Unix epoch of the scan |
| `faction` | `VARCHAR(10)` | `Horde`, `Alliance`, or `Neutral` |
| `item_id` | `INTEGER` | Blizzard Item ID |
| `item_name` | `VARCHAR(100)` | Localized name of the item |
| `seller` | `VARCHAR(50)` | Player name |
| `stack_size` | `INTEGER` | Number of items in the stack |
| `unit_buyout_price` | `INTEGER` | Price per single item in copper |
| `duration_hours` | `INTEGER` | Auction duration |

### `ohlcv_session`
Historical price data aggregated into OHLCV (Open, High, Low, Close, Volume) bars.
**Retention: Daily for 3 years, then Weekly indefinitely.**

| Column | Type | Description |
| :--- | :--- | :--- |
| `bucket_start` | `BIGINT` | Unix epoch of the start of the day/week |
| `item_id` | `INTEGER` | Blizzard Item ID |
| `faction` | `VARCHAR(10)` | `Horde`, `Alliance`, or `Neutral` |
| `open_price` | `INTEGER` | First price seen in the bucket |
| `high_price` | `INTEGER` | Highest price seen in the bucket |
| `low_price` | `INTEGER` | Lowest price seen in the bucket |
| `close_price` | `INTEGER` | Last price seen in the bucket |
| `median_price` | `INTEGER` | The exact middle price (protects against troll listings) |
| `avg_price` | `INTEGER` | Simple mathematical average |
| `volume` | `INTEGER` | Total stack sizes seen in the bucket |

*(Primary Key: `bucket_start`, `item_id`, `faction`)*

### `volume_summary_daily`
Summarizes how many items vanished (presumably sold) at specific price points.
This allows us to see demand elasticity without storing millions of raw events.
**Retention: 3 Years**

| Column | Type | Description |
| :--- | :--- | :--- |
| `day_start` | `BIGINT` | Unix epoch of the start of the day |
| `item_id` | `INTEGER` | Blizzard Item ID |
| `faction` | `VARCHAR(10)` | `Horde`, `Alliance`, or `Neutral` |
| `price` | `INTEGER` | The unit price they vanished at |
| `units_vanished` | `INTEGER` | Total quantity that disappeared |
| `events` | `INTEGER` | Number of individual listings that disappeared |

*(Primary Key: `day_start`, `item_id`, `faction`, `price`)*

### `auction_event_log`
Raw log of individual auctions that vanished between scans.
**Retention: 90 Days** (Aggregated into `volume_summary_daily` before deletion).

| Column | Type | Description |
| :--- | :--- | :--- |
| `event_id` | `BIGSERIAL` | Primary Key |
| `item_id` | `INTEGER` | Blizzard Item ID |
| `faction` | `VARCHAR(10)` | Faction |
| `seller` | `VARCHAR(50)` | Player who listed it |
| `unit_price` | `INTEGER` | The price it vanished at |
| `quantity` | `INTEGER` | The stack size |
| `detected_at` | `BIGINT` | Unix epoch of when we noticed it was gone |
| `disappearance_type` | `VARCHAR(20)` | Defaults to `VANISHED` (could be `SOLD` or `EXPIRED`) |

### `dim_items`
Static metadata for items. Used as a fallback if localized names are missing.
**Retention: Indefinite**

| Column | Type | Description |
| :--- | :--- | :--- |
| `item_id` | `INTEGER` | Primary Key |
| `item_name` | `VARCHAR(100)` | Localized name |
| `max_stack_size` | `INTEGER` | Maximum stack size (currently null) |
| `quality` | `VARCHAR(20)` | Item quality (currently null) |

### `scan_log`
A deduplication ledger to ensure the same scan isn't ingested twice.
**Retention: Indefinite**

| Column | Type | Description |
| :--- | :--- | :--- |
| `faction` | `VARCHAR(10)` | Primary Key |
| `scan_timestamp` | `BIGINT` | Primary Key |
| `zone` | `VARCHAR(50)` | Where the scan was taken |
| `listing_count` | `INTEGER` | Number of items in the scan |
| `ingested_at` | `BIGINT` | When the ETL processed it |