from ahoracle_etl.db import make_engine
from ahoracle_etl.models import OHLCVSession, ScanLog
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime

engine = make_engine()

with Session(engine) as session:
    print("=== Ingested Scans ===")
    scans = session.scalars(select(ScanLog).order_by(ScanLog.scan_timestamp.desc()).limit(15)).all()
    for s in scans:
        dt = datetime.fromtimestamp(s.scan_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{s.faction:8s} | {dt} | {s.listing_count} listings")

    print("\n=== OHLCV History for Item 8067 (Crafted Light Shot) ===")
    history = session.scalars(
        select(OHLCVSession).where(OHLCVSession.item_id == 8067).order_by(OHLCVSession.bucket_start.asc())
    ).all()
    
    if not history:
        print("No OHLCV data found for this item.")
    
    for h in history:
        dt = datetime.fromtimestamp(h.bucket_start).strftime('%Y-%m-%d %H:%M')
        print(f"{dt} | {h.faction:8s} | Price: {h.close_price:>5}c | Volume: {h.volume:>5}")