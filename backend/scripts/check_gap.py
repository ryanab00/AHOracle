# save as check_gap.py
from ahoracle_etl.db import make_engine
from sqlalchemy import text

engine = make_engine()
with engine.connect() as c:
    print("=== Last scan per faction ===")
    for row in c.execute(text("""
        SELECT faction, scan_timestamp, datetime(scan_timestamp, 'unixepoch', 'localtime') as when_, listing_count
        FROM scan_log
        ORDER BY scan_timestamp DESC
        LIMIT 12
    """)):
        print(f"  {row[0]:9s}  {row[2]}  {row[3]:>6d} listings")