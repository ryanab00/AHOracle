import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from sqlalchemy import text
from ahoracle_etl.db import make_engine

def downsample():
    engine = make_engine()
    # 7 days ago, rounded to the start of the day (UTC)
    cutoff = int((time.time() - 7 * 86400) // 86400) * 86400
    
    print(f"📉 Downsampling OHLCV data older than {time.strftime('%Y-%m-%d', time.gmtime(cutoff))}...")
    
    with engine.begin() as conn:
        # 1. Aggregate hourly into daily buckets
        # We use DISTINCT ON to get the true open/close prices for the day
        conn.execute(text("""
            WITH aggregated AS (
                SELECT
                    (bucket_start / 86400) * 86400 AS day_start,
                    item_id,
                    faction,
                    (array_agg(open_price ORDER BY bucket_start ASC))[1] AS open_price,
                    MAX(high_price) AS high_price,
                    MIN(low_price) AS low_price,
                    (array_agg(close_price ORDER BY bucket_start DESC))[1] AS close_price,
                    SUM(volume) AS volume
                FROM ohlcv_session
                WHERE bucket_start < :cutoff
                GROUP BY (bucket_start / 86400) * 86400, item_id, faction
            )
            INSERT INTO ohlcv_session (
                bucket_start, item_id, faction, open_price, high_price, low_price, close_price, volume
            )
            SELECT * FROM aggregated
            ON CONFLICT (bucket_start, item_id, faction) DO UPDATE SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume;
        """), {"cutoff": cutoff})

        # 2. Delete the old hourly rows
        deleted = conn.execute(text("""
            DELETE FROM ohlcv_session
            WHERE bucket_start < :cutoff
              AND bucket_start % 86400 != 0
        """), {"cutoff": cutoff}).rowcount
        
    print(f"✅ Downsampled and removed {deleted:,} hourly rows.")

if __name__ == "__main__":
    downsample()