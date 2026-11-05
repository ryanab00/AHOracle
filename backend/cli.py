#!/usr/bin/env python3
"""AHOracle ETL — ingest SavedVariables into a database.

Commands:
    ingest    Parse SV file and write to DB   (default)
    inspect   Show what's currently in the DB
    volume    ASCII histogram of units vanished at each price point

Examples:
    python etl.py ingest
    python etl.py --sv-file /path/to/AHOracle.lua ingest
    python etl.py --db postgresql+psycopg://... ingest
    python etl.py inspect
    python etl.py volume --item 13463 --days 30
"""
import argparse
import os
import sys
import time
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ahoracle import parse, pipeline
from ahoracle.db import make_engine, ensure_views, default_db_url
from ahoracle.models import (
    AuctionEventLog, Base, DimItem, LiveAuctionBook, OHLCVSession, ScanLog,
)


# ─── Path detection ──────────────────────────────────────────────────────

def default_sv_path() -> Path | None:
    """Best-effort lookup of AHOracle.lua under common WoW installs."""
    env_path = os.environ.get("AHORACLE_SV_FILE")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    roots = [
        Path.home() / "Documents" / "World of Warcraft" / "_classic_era_" / "WTF" / "Account",
        Path("C:/Program Files (x86)/World of Warcraft/_classic_era_/WTF/Account"),
        Path("C:/Program Files/World of Warcraft/_classic_era_/WTF/Account"),
        Path.home() / ".wine" / "drive_c" / "Program Files (x86)" /
            "World of Warcraft" / "_classic_era_" / "WTF" / "Account",
        Path("/Applications/World of Warcraft/_classic_era_/WTF/Account"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for account in root.iterdir():
            sv = account / "SavedVariables" / "AHOracle.lua"
            if sv.exists():
                return sv
    return None


# ─── Commands ────────────────────────────────────────────────────────────

def cmd_ingest(args) -> int:
    sv_path = Path(args.sv_file) if args.sv_file else default_sv_path()
    if not sv_path or not sv_path.exists():
        print("error: could not find AHOracle.lua.  Use --sv-file to specify.",
              file=sys.stderr)
        return 1

    print(f"Reading  {sv_path}")
    db = parse.parse_saved_variables(sv_path)

    engine = make_engine(args.db)
    Base.metadata.create_all(engine)
    ensure_views(engine)

    results = []
    with Session(engine) as session:
        for faction, scan in parse.extract_scans(db):
            r = pipeline.ingest_scan(session, scan)
            results.append(r)
        session.commit()

    print(f"Writing  {args.db or default_db_url()}")
    if not results:
        print("  (no populated faction slots in SavedVariables)")
        return 0

    for r in results:
        if r.get("skipped"):
            print(f"  {r['faction']:9s} skipped ({r['skipped']})")
        else:
            print(f"  {r['faction']:9s} {r['listing_count']:>6d} listings"
                  f"  |  {r['vanished']:>4d} vanished"
                  f"  |  {r['zone']}")
    return 0


def cmd_inspect(args) -> int:
    engine = make_engine(args.db)
    with Session(engine) as session:
        print("── scan_log ────────────────────────────────────────────────")
        rows = list(session.scalars(select(ScanLog).order_by(ScanLog.scan_timestamp)))
        if not rows:
            print("  (empty — has the ETL been run?)")
        for row in rows:
            print(f"  {row.faction:9s}  ts={row.scan_timestamp}  "
                  f"zone={row.zone!r:30s}  {row.listing_count:>6d} listings")

        print("\n── live_auction_book (by faction) ──────────────────────────")
        for faction, count in session.execute(
            select(LiveAuctionBook.faction, func.count()).group_by(LiveAuctionBook.faction)
        ):
            print(f"  {faction:9s}  {count:>6d}")

        print("\n── auction_event_log (by faction) ──────────────────────────")
        for faction, count in session.execute(
            select(AuctionEventLog.faction, func.count()).group_by(AuctionEventLog.faction)
        ):
            print(f"  {faction:9s}  {count:>6d}")

        print("\n── ohlcv_session (by faction) ──────────────────────────────")
        for faction, count in session.execute(
            select(OHLCVSession.faction, func.count()).group_by(OHLCVSession.faction)
        ):
            print(f"  {faction:9s}  {count:>6d} bars")

        print("\n── dim_items ───────────────────────────────────────────────")
        n = session.scalar(select(func.count()).select_from(DimItem))
        print(f"  {n} items")
    return 0


def cmd_volume(args) -> int:
    """ASCII histogram: units vanished at each price point."""
    if not args.item:
        print("error: --item <id> is required for the 'volume' command",
              file=sys.stderr)
        return 1

    engine = make_engine(args.db)
    cutoff = int(time.time()) - args.days * 86400

    sql = text("""
        SELECT faction, unit_price, units_vanished, events
        FROM v_volume_at_price
        WHERE item_id = :item_id
          AND last_vanished_ts >= :cutoff
        ORDER BY faction, unit_price
    """)

    with Session(engine) as session:
        rows = list(session.execute(sql, {"item_id": args.item, "cutoff": cutoff}))

    if not rows:
        print(f"No vanished events for item {args.item} in the last {args.days} days.")
        return 0

    by_faction: dict[str, list] = {}
    for f, price, units, events in rows:
        by_faction.setdefault(f, []).append((price, units, events))

    for faction, pts in by_faction.items():
        print(f"\n══ {faction} — item {args.item} — last {args.days} days ══")
        max_units = max(u for _, u, _ in pts) or 1
        for price, units, events in pts:
            gold    = price / 10000.0
            bar_len = max(1, int(40 * units / max_units))
            bar     = "█" * bar_len
            print(f"  {gold:>10.2f}g  {units:>7d}u  {events:>4d}e  {bar}")
    return 0


# ─── Entry point ─────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="AHOracle ETL")
    ap.add_argument("--db", default=None,
                    help="SQLAlchemy DB URL (default: $AHORACLE_DB_URL or sqlite:///ahoracle.db)")
    ap.add_argument("--sv-file", type=Path,
                    help="Path to AHOracle.lua SavedVariables file")

    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("ingest",  help="Parse SV file and write to DB (default)")
    sub.add_parser("inspect", help="Show current DB contents")
    p_vol = sub.add_parser("volume", help="Histogram: units vanished at each price")
    p_vol.add_argument("--item", type=int, required=True, help="Item ID")
    p_vol.add_argument("--days", type=int, default=30, help="Lookback window (default 30)")

    args = ap.parse_args()
    cmd = args.cmd or "ingest"

    if cmd == "ingest":  return cmd_ingest(args)
    if cmd == "inspect": return cmd_inspect(args)
    if cmd == "volume":  return cmd_volume(args)

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())