import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from ahoracle.db import make_engine
from ahoracle.models import (
    Base, DimItem, ScanLog, LiveAuctionBook,
    ScanSnapshot, AuctionEventLog, OHLCVSession
)

# Map each model to the auto-incrementing column that must be omitted
DROP_COLUMNS = {
    LiveAuctionBook: "id",
    ScanSnapshot: "id",
    AuctionEventLog: "event_id",
}

def migrate():
    print("🚀 Starting migration from local SQLite to Neon...")
    
    local_engine = create_engine("sqlite:///ahoracle.db")
    if not local_engine.dialect.has_table(local_engine.connect(), "live_auction_book"):
        print("❌ Error: ahoracle.db not found or missing tables in this folder.")
        return

    neon_engine = make_engine()
    
    tables = [
        (DimItem, ['item_id']),
        (ScanLog, ['faction', 'scan_timestamp']),
        (LiveAuctionBook, None),
        (ScanSnapshot, None),
        (AuctionEventLog, None),
        (OHLCVSession, ['bucket_start', 'item_id', 'faction'])
    ]

    Base.metadata.create_all(neon_engine)
    CHUNK_SIZE = 2000

    with Session(local_engine) as local_session, Session(neon_engine) as neon_session:
        for model, unique_cols in tables:
            print(f"\n📦 Migrating {model.__tablename__}...")
            
            rows = local_session.scalars(select(model)).all()
            if not rows:
                print("   (Empty, skipping)")
                continue

            drop_col = DROP_COLUMNS.get(model)
            data = []
            for row in rows:
                d = {c.name: getattr(row, c.name) for c in model.__table__.columns}
                if drop_col and drop_col in d:
                    del d[drop_col]   # Let Postgres generate the ID
                data.append(d)

            print(f"   Found {len(data)} rows. Uploading...")
            for i in range(0, len(data), CHUNK_SIZE):
                chunk = data[i:i+CHUNK_SIZE]
                stmt = pg_insert(model).values(chunk)
                
                if unique_cols:
                    stmt = stmt.on_conflict_do_nothing(index_elements=unique_cols)
                
                neon_session.execute(stmt)
                neon_session.commit()
                print(f"   ...uploaded {i + len(chunk)} / {len(data)}")

            print(f"✅ Finished {model.__tablename__}")

    print("\n🎉 Migration complete! Your old local data is now in Neon.")

if __name__ == "__main__":
    migrate()