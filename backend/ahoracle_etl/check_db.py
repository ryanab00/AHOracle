from backend.db import make_engine
from sqlalchemy import text

engine = make_engine()
print("dialect:", engine.dialect.name)

with engine.connect() as c:
    tables = c.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )).all()
    print("tables:", [r[0] for r in tables])

    views = c.execute(text(
        "SELECT viewname FROM pg_views WHERE schemaname='public' ORDER BY viewname"
    )).all()
    print("views:", [r[0] for r in views])

    for t in ("live_auction_book", "scan_snapshots", "dim_items",
              "ohlcv_session", "scan_log", "auction_event_log"):
        try:
            n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:22} {n:>10,}")
        except Exception as e:
            print(f"  {t:22} (missing: {e.__class__.__name__})")