from backend.db import make_engine
from sqlalchemy import text

engine = make_engine()
with engine.connect() as c:
    # Latest two snapshots per faction
    for faction in ("Alliance", "Horde", "Neutral"):
        rows = list(c.execute(text("""
            SELECT scan_timestamp FROM scan_log
            WHERE faction = :f
            ORDER BY scan_timestamp DESC LIMIT 2
        """), {"f": faction}))
        if len(rows) < 2:
            continue
        t_new, t_old = rows[0][0], rows[1][0]

        # Distinct item_ids in each snapshot
        old_ids = {r[0] for r in c.execute(text("""
            SELECT DISTINCT item_id FROM scan_snapshots
            WHERE faction=:f AND scan_timestamp=:t
        """), {"f": faction, "t": t_old})}

        new_ids = {r[0] for r in c.execute(text("""
            SELECT DISTINCT item_id FROM scan_snapshots
            WHERE faction=:f AND scan_timestamp=:t
        """), {"f": faction, "t": t_new})}

        only_old = old_ids - new_ids
        only_new = new_ids - old_ids
        both     = old_ids & new_ids

        print(f"\n══ {faction} ══")
        print(f"  items in BOTH   {len(both):>6d}")
        print(f"  items only OLD  {len(only_old):>6d}")
        print(f"  items only NEW  {len(only_new):>6d}")

        # Listing-level overlap (full key)
        def listing_keys(ts):
            return {(r[0], r[1], r[2], r[3]) for r in c.execute(text("""
                SELECT item_id, seller, stack_size, unit_buyout_price
                FROM scan_snapshots
                WHERE faction=:f AND scan_timestamp=:t
            """), {"f": faction, "t": ts})}

        old_k = listing_keys(t_old)
        new_k = listing_keys(t_new)
        print(f"  listings in BOTH  {len(old_k & new_k):>6d}")
        print(f"  listings only OLD {len(old_k - new_k):>6d}")
        print(f"  listings only NEW {len(new_k - old_k):>6d}")