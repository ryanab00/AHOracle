"""Ingest pipeline: SavedVariables table -> SQLAlchemy models."""
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from .models import (
    AuctionEventLog, DimItem, LiveAuctionBook, OHLCVSession,
    ScanLog, ScanSnapshot,
)


# ─── Helpers ─────────────────────────────────────────────────────────────

def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _already_ingested(session: Session, faction: str, scan_ts: int) -> bool:
    return session.scalar(
        select(ScanLog).where(
            ScanLog.faction == faction,
            ScanLog.scan_timestamp == scan_ts,
        )
    ) is not None


def _upsert_dim_items(session: Session, listings: Iterable[dict]) -> None:
    seen: dict[int, str] = {}
    for l in listings:
        seen[l["item_id"]] = l.get("item_name") or ""

    for item_id, name in seen.items():
        row = session.get(DimItem, item_id)
        if row is None:
            session.add(DimItem(item_id=item_id, item_name=name or None))
        elif name and not row.item_name:
            row.item_name = name


def _load_current_live(session: Session, faction: str) -> list[LiveAuctionBook]:
    return list(session.scalars(
        select(LiveAuctionBook).where(LiveAuctionBook.faction == faction)
    ))


# ─── Vanished-listing detection ──────────────────────────────────────────

def _detect_vanished(previous_rows, current_listings, current_scan_ts):
    """Return vanished listings.

    We do NOT try to distinguish SOLD from EXPIRED — with daily scan cadence
    the signal is too weak.  Every vanish is logged as VANISHED and downstream
    views aggregate volume at each price point.  A trained classifier can be
    added later once we have months of history.
    """
    def key_of(item_id, seller, stack, price):
        return (item_id, seller or "Unknown", stack, price)

    current_keys = {
        key_of(l["item_id"], l.get("seller"), l["stack_size"], l["unit_buyout_price"])
        for l in current_listings
    }

    vanished = []
    for row in previous_rows:
        k = key_of(row.item_id, row.seller, row.stack_size, row.unit_buyout_price)
        if k in current_keys:
            continue

        vanished.append({
            "item_id":                      row.item_id,
            "faction":                      row.faction,
            "seller":                       row.seller,
            "unit_price":                   row.unit_buyout_price,
            "quantity":                     row.stack_size,
            "duration_hours":               getattr(row, "duration_hours", 0) or 0,
            "first_seen":                   row.scan_timestamp,
            "last_seen":                    row.scan_timestamp,
            "detected_at":                  current_scan_ts,
            "detection_resolution_seconds": max(current_scan_ts - row.scan_timestamp, 0),
            "disappearance_type":           "VANISHED",
            "confidence":                   1.0,
        })
    return vanished


# ─── OHLCV rebuild ───────────────────────────────────────────────────────

def _rebuild_ohlcv(session: Session, faction, scan_ts, listings, bucket_seconds=3600):
    """Compute median price per item at the scan's bucket and upsert."""
    bucket_start = (scan_ts // bucket_seconds) * bucket_seconds

    by_item: dict[int, list[dict]] = {}
    for l in listings:
        by_item.setdefault(l["item_id"], []).append(l)

    for item_id, items in by_item.items():
        prices = sorted(l["unit_buyout_price"] for l in items)
        n = len(prices)
        if n == 0:
            continue
        median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) // 2
        volume = sum(l["stack_size"] for l in items)

        row = session.get(OHLCVSession, (bucket_start, item_id, faction))
        if row is None:
            session.add(OHLCVSession(
                bucket_start=bucket_start,
                item_id=item_id,
                faction=faction,
                open_price=median,
                high_price=median,
                low_price=median,
                close_price=median,
                volume=volume,
            ))
        else:
            row.high_price  = max(row.high_price, median)
            row.low_price   = min(row.low_price,  median)
            row.close_price = median
            row.volume      = (row.volume or 0) + volume


# ─── Main entry ──────────────────────────────────────────────────────────

def ingest_scan(session: Session, scan: dict) -> dict:
    """Ingest one faction scan.  Returns a summary dict.

    Assumes caller has already opened a transaction.
    """
    faction  = scan["faction"]
    scan_ts  = scan["scan_timestamp"]
    zone     = scan["zone"]
    listings = scan["listings"]

    if _already_ingested(session, faction, scan_ts):
        return {"faction": faction, "skipped": "duplicate"}

    # 1. Grab the current live book for this faction BEFORE we overwrite it.
    previous_rows = _load_current_live(session, faction)

    # 2. Compute vanished listings.
    vanished = _detect_vanished(previous_rows, listings, scan_ts)
    for v in vanished:
        session.add(AuctionEventLog(**v))

    # 3. Replace live_auction_book for this faction — clean upload.
    session.execute(delete(LiveAuctionBook).where(LiveAuctionBook.faction == faction))
    for l in listings:
        session.add(LiveAuctionBook(
            scan_timestamp=scan_ts,
            faction=faction,
            item_id=l["item_id"],
            item_name=l.get("item_name") or None,
            seller=l.get("seller") or None,
            stack_size=l["stack_size"],
            unit_buyout_price=l["unit_buyout_price"],
            duration_hours=l.get("duration_hours") or 0,
        ))

    # 4. Archive the snapshot (append-only history).
    for l in listings:
        session.add(ScanSnapshot(
            scan_timestamp=scan_ts,
            faction=faction,
            zone=zone,
            item_id=l["item_id"],
            item_name=l.get("item_name") or None,
            seller=l.get("seller") or None,
            stack_size=l["stack_size"],
            unit_buyout_price=l["unit_buyout_price"],
            duration_hours=l.get("duration_hours") or 0,
        ))

    # 5. Dimension table.
    _upsert_dim_items(session, listings)

    # 6. OHLCV bar.
    _rebuild_ohlcv(session, faction, scan_ts, listings)

    # 7. Book-keeping.
    session.add(ScanLog(
        faction=faction,
        scan_timestamp=scan_ts,
        zone=zone,
        listing_count=len(listings),
        ingested_at=_now_epoch(),
    ))

    return {
        "faction":       faction,
        "listing_count": len(listings),
        "vanished":      len(vanished),
        "zone":          zone,
    }