import time
from typing import Iterable
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import (
    LiveAuctionBook, DimItem, AuctionEventLog,
    OHLCVSession, ScanLog, ScanSnapshot
)

def _now_epoch() -> int:
    return int(time.time())

def _already_ingested(session: Session, faction: str, scan_ts: int) -> bool:
    return session.get(ScanLog, (faction, scan_ts)) is not None

def _chunked_insert(session: Session, table, rows: list[dict], chunk_size: int = 1000):
    """Safely inserts large lists in batches to avoid Postgres parameter limits."""
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        session.execute(pg_insert(table).values(chunk))

def _chunked_upsert(session: Session, table, rows: list[dict], index_elements: list[str], chunk_size: int = 1000):
    """Safely upserts large lists in batches."""
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        stmt = pg_insert(table).values(chunk)
        update_cols = {col: getattr(stmt.excluded, col) for col in chunk[0].keys() if col not in index_elements}
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_=update_cols
        )
        session.execute(stmt)

def _upsert_dim_items(session: Session, listings: Iterable[dict]) -> None:
    seen: dict[int, str] = {}
    for l in listings:
        item_id = l.get("item_id")
        item_name = l.get("item_name")
        if item_id and item_name:
            seen[item_id] = item_name

    if not seen:
        return

    rows = [{"item_id": k, "item_name": v} for k, v in seen.items()]
    _chunked_upsert(session, DimItem, rows, ['item_id'])

def _load_current_live(session: Session, faction: str) -> list[LiveAuctionBook]:
    return list(session.scalars(
        select(LiveAuctionBook).where(LiveAuctionBook.faction == faction)
    ))

def _detect_vanished(previous_rows, current_listings, current_scan_ts) -> list[dict]:
    def key_of(item_id, seller, stack, price):
        return f"{item_id}|{seller}|{stack}|{price}"

    current_keys = {
        key_of(l["item_id"], l.get("seller", ""), l["stack_size"], l["unit_buyout_price"])
        for l in current_listings
    }

    vanished = []
    for row in previous_rows:
        k = key_of(row.item_id, row.seller, row.stack_size, row.unit_buyout_price)
        if k not in current_keys:
            vanished.append({
                "item_id": row.item_id,
                "faction": row.faction,
                "seller": row.seller,
                "unit_price": row.unit_buyout_price,
                "quantity": row.stack_size,
                "duration_hours": row.duration_hours,
                "first_seen": None,
                "last_seen": row.scan_timestamp,
                "detected_at": current_scan_ts,
                "detection_resolution_seconds": current_scan_ts - row.scan_timestamp,
                "disappearance_type": "VANISHED",
                "confidence": 1.0,
            })
    return vanished

from sqlalchemy import text

from sqlalchemy import text

def _rebuild_ohlcv_and_compress(session: Session, faction: str, scan_ts: int):
    
    # 1. Build DAILY OHLCV for ALL days currently in scan_snapshots
    session.execute(text("""
        INSERT INTO ohlcv_session (
            bucket_start, item_id, faction, open_price, high_price, 
            low_price, close_price, median_price, avg_price, volume
        )
        SELECT
            (scan_timestamp / 86400) * 86400 AS bucket_start,
            item_id,
            faction,
            (array_agg(unit_buyout_price ORDER BY scan_timestamp ASC))[1] AS open_price,
            MAX(unit_buyout_price) AS high_price,
            MIN(unit_buyout_price) AS low_price,
            (array_agg(unit_buyout_price ORDER BY scan_timestamp DESC))[1] AS close_price,
            CAST(percentile_cont(0.5) WITHIN GROUP (ORDER BY unit_buyout_price) AS INTEGER) AS median_price,
            CAST(AVG(unit_buyout_price) AS INTEGER) AS avg_price,
            SUM(stack_size) AS volume
        FROM scan_snapshots
        WHERE faction = :faction
        GROUP BY (scan_timestamp / 86400) * 86400, item_id, faction
        ON CONFLICT (bucket_start, item_id, faction) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            median_price = EXCLUDED.median_price,
            avg_price = EXCLUDED.avg_price,
            volume = EXCLUDED.volume
    """), {"faction": faction})

    # 2. Roll up ALL Vanish Events into Daily Volume Summary
    session.execute(text("""
        INSERT INTO volume_summary_daily (
            day_start, item_id, faction, price, units_vanished, events
        )
        SELECT
            (detected_at / 86400) * 86400 AS day_start,
            item_id,
            faction,
            unit_price AS price,
            SUM(quantity) AS units_vanished,
            COUNT(*) AS events
        FROM auction_event_log
        WHERE faction = :faction
        GROUP BY (detected_at / 86400) * 86400, item_id, faction, unit_price
        ON CONFLICT (day_start, item_id, faction, price) DO UPDATE SET
            units_vanished = EXCLUDED.units_vanished,
            events = EXCLUDED.events
    """), {"faction": faction})

    # 3. Compress Daily to Weekly (ONLY after 3 YEARS / 1095 days)
    bucket_start = (scan_ts // 86400) * 86400
    cutoff_3_years = bucket_start - (1095 * 86400)
    
    session.execute(text("""
        WITH weekly AS (
            SELECT
                (bucket_start / 604800) * 604800 AS week_start,
                item_id,
                faction,
                (array_agg(open_price ORDER BY bucket_start ASC))[1] AS open_price,
                MAX(high_price) AS high_price,
                MIN(low_price) AS low_price,
                (array_agg(close_price ORDER BY bucket_start DESC))[1] AS close_price,
                CAST(AVG(median_price) AS INTEGER) AS median_price,
                CAST(AVG(avg_price) AS INTEGER) AS avg_price,
                SUM(volume) AS volume
            FROM ohlcv_session
            WHERE faction = :faction AND bucket_start < :cutoff
            GROUP BY (bucket_start / 604800) * 604800, item_id, faction
        )
        INSERT INTO ohlcv_session (
            bucket_start, item_id, faction, open_price, high_price, 
            low_price, close_price, median_price, avg_price, volume
        )
        SELECT * FROM weekly
        ON CONFLICT (bucket_start, item_id, faction) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            median_price = EXCLUDED.median_price,
            avg_price = EXCLUDED.avg_price,
            volume = EXCLUDED.volume
    """), {"cutoff": cutoff_3_years, "faction": faction})

    # 4. Delete old daily data that was just rolled into weekly
    session.execute(text("""
        DELETE FROM ohlcv_session
        WHERE faction = :faction 
          AND bucket_start < :cutoff 
          AND bucket_start % 604800 != 0
    """), {"cutoff": cutoff_3_years, "faction": faction})

def ingest_scan(session: Session, scan: dict) -> dict:
    faction  = scan["faction"]
    scan_ts  = scan["scan_timestamp"]
    zone     = scan["zone"]
    listings = scan["listings"]

    if _already_ingested(session, faction, scan_ts):
        return {"skipped": True, "faction": faction, "scan_timestamp": scan_ts}

    previous_rows = _load_current_live(session, faction)
    vanished = _detect_vanished(previous_rows, listings, scan_ts)

    # 1. Log vanished items safely
    if vanished:
        _chunked_insert(session, AuctionEventLog, vanished)

    # 2. Delete old live book
    session.execute(delete(LiveAuctionBook).where(LiveAuctionBook.faction == faction))

    # 3. Bulk insert new live book safely
    if listings:
        live_rows = [{"scan_timestamp": scan_ts, "faction": faction, **l} for l in listings]
        _chunked_insert(session, LiveAuctionBook, live_rows)

    # 4. Append to scan_snapshots safely
    if listings:
        snapshots = [
            {
                "scan_timestamp": scan_ts,
                "faction": faction,
                "item_id": l["item_id"],
                "item_name": l.get("item_name"),
                "seller": l.get("seller"),
                "stack_size": l["stack_size"],
                "unit_buyout_price": l["unit_buyout_price"],
                "duration_hours": l.get("duration_hours")
            } for l in listings
        ]
        _chunked_insert(session, ScanSnapshot, snapshots)

        # 5. Upsert dim_items & rebuild OHLCV
    _upsert_dim_items(session, listings)
    _rebuild_ohlcv_and_compress(session, faction, scan_ts)

    # 6. CLEANUP: Delete raw scan_snapshots older than today's midnight
    bucket_start = (scan_ts // 86400) * 86400
    session.execute(
        delete(ScanSnapshot).where(ScanSnapshot.scan_timestamp < bucket_start)
    )

    # 7. CLEANUP: Delete raw events older than 90 days
    cutoff_events = bucket_start - (90 * 86400)
    session.execute(
        delete(AuctionEventLog).where(AuctionEventLog.detected_at < cutoff_events)
    )

    # 8. Log the scan
    log = ScanLog(
        faction=faction,
        scan_timestamp=scan_ts,
        zone=zone,
        listing_count=len(listings),
        ingested_at=_now_epoch()
    )
    session.merge(log)
    session.commit()

    return {
        "skipped": False,
        "faction": faction,
        "listings": len(listings),
        "vanished": len(vanished)
    }