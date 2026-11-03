"""Read-only REST API for AH Oracle."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from pathlib import Path
import json
import time

from ahoracle_etl.db import make_engine
from ahoracle_etl.models import (
    LiveAuctionBook, DimItem, OHLCVSession, ScanLog,
)

router = APIRouter()
engine = make_engine()


def get_db():
    with Session(engine) as s:
        yield s


# ─── Static data loaded at import time ───────────────────────────────────
_API_DIR      = Path(__file__).parent
RECIPES_FILE  = _API_DIR / "recipes.json"
ITEMS_FILE    = _API_DIR / "items.json"

if not RECIPES_FILE.exists():
    print(f"WARNING: {RECIPES_FILE.name} not found — /consumables will be empty")
    RECIPES: list[dict] = []
else:
    RECIPES = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))

if not ITEMS_FILE.exists():
    print(f"WARNING: {ITEMS_FILE.name} not found — item names unavailable")
    ITEMS_FALLBACK: dict[int, str] = {}
else:
    ITEMS_FALLBACK = {
        int(k): v for k, v in
        json.loads(ITEMS_FILE.read_text(encoding="utf-8")).items()
    }

PRICEABLE_RECIPES = [r for r in RECIPES if r.get("reagents")]
RECIPE_BY_OUTPUT = {r["output_item_id"]: r for r in PRICEABLE_RECIPES}

VENDOR_ITEMS: dict[int, int] = {
    3371: 5,     # Crystal Vial
    8925: 5,     # Crystal Vial
}

IMPOSSIBLE = 99999999999


# ─── Health & meta ───────────────────────────────────────────────────────
@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    scans = db.scalar(select(func.count()).select_from(ScanLog)) or 0
    items = db.scalar(select(func.count()).select_from(DimItem)) or 0
    live  = db.scalar(select(func.count()).select_from(LiveAuctionBook)) or 0
    return {
        "status":          "ok",
        "scan_rows":       scans,
        "items":           items,
        "live_listings":   live,
        "recipes_loaded":  len(RECIPES),
        "recipes_priceable": len(PRICEABLE_RECIPES),
    }


@router.get("/last_scan")
def get_last_scan(db: Session = Depends(get_db)):
    stmt = (
        select(ScanLog.faction, func.max(ScanLog.scan_timestamp))
        .group_by(ScanLog.faction)
    )
    rows = db.execute(stmt).all()
    return {faction: ts for faction, ts in rows}


# ─── Auction browser ─────────────────────────────────────────────────────
@router.get("/auctions")
def list_auctions(
    page:     int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    faction:  str = Query("Horde"),
    db: Session = Depends(get_db),
):
    stmt = text("""
        SELECT item_id, item_name,
               COUNT(*)                  AS num_listings,
               SUM(stack_size)           AS total_quantity,
               MIN(unit_buyout_price)    AS min_price,
               MAX(unit_buyout_price)    AS max_price
        FROM live_auction_book
        WHERE faction = :faction
        GROUP BY item_id, item_name
        ORDER BY item_name
        LIMIT :limit OFFSET :offset
    """)
    count_stmt = text(
        "SELECT COUNT(DISTINCT item_id) FROM live_auction_book WHERE faction = :faction"
    )
    total = db.execute(count_stmt, {"faction": faction}).scalar() or 0
    rows = db.execute(stmt, {
        "faction": faction,
        "limit":   per_page,
        "offset":  (page - 1) * per_page,
    }).all()

    items = [
        {
            "item_id":        r[0],
            "item_name":      r[1],
            "num_listings":   r[2],
            "total_quantity": r[3],
            "min_price":      r[4],
            "max_price":      r[5],
        }
        for r in rows
    ]
    return {
        "items":    items,
        "page":     page,
        "per_page": per_page,
        "total":    total,
    }


@router.get("/auctions/{item_id}")
def auction_listings(
    item_id: int,
    faction: str = Query("Horde"),
    db: Session = Depends(get_db),
):
    stmt = (
        select(LiveAuctionBook)
        .where(
            LiveAuctionBook.item_id == item_id,
            LiveAuctionBook.faction == faction,
        )
        .order_by(LiveAuctionBook.unit_buyout_price.asc())
        .limit(200)
    )
    return list(db.scalars(stmt))


# ─── Item detail ─────────────────────────────────────────────────────────
@router.get("/items/{item_id}/stats")
def item_stats(
    item_id: int,
    faction: str = Query("Horde"),
    db: Session = Depends(get_db),
):
    item = db.get(DimItem, item_id)

    # UPDATED: Query the new summary table instead of the old view
    vol_stmt = text("""
        SELECT price, SUM(units_vanished) as units_vanished, SUM(events) as events
        FROM volume_summary_daily
        WHERE item_id = :item_id AND faction = :faction
        GROUP BY price
        ORDER BY price
    """)
    vol_rows = db.execute(vol_stmt, {
        "item_id": item_id, "faction": faction,
    }).all()

    volume_at_price = [
        {"price": r[0], "units_vanished": r[1], "events": r[2]}
        for r in vol_rows
    ]
    return {
        "item": {
            "item_id":   item_id,
            "item_name": item.item_name if item else None,
        },
        "volume_at_price": volume_at_price,
    }


@router.get("/items/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(OHLCVSession)
        .where(OHLCVSession.item_id == item_id)
        .order_by(OHLCVSession.bucket_start.asc())
    )
    history = list(db.scalars(stmt))

    time_map: dict[int, dict] = {}
    for h in history:
        t = h.bucket_start * 1000
        bucket = time_map.setdefault(t, {"time": t})
        key = (
            "Horde"    if h.faction == "Horde"    else
            "Alliance" if h.faction == "Alliance" else
            "Neutral"
        )
        bucket[f"{key}Price"]   = h.close_price
        bucket[f"{key}Median"]  = h.median_price
        bucket[f"{key}Average"] = h.avg_price
        bucket[f"{key}Volume"]  = h.volume

    return sorted(time_map.values(), key=lambda x: x["time"])


@router.get("/items/{item_id}/current_depth")
def item_current_depth(
    item_id: int,
    faction: str = Query("Horde"),
    db: Session = Depends(get_db),
):
    stmt = text("""
        SELECT unit_buyout_price, stack_size
        FROM live_auction_book
        WHERE item_id = :item_id AND faction = :faction
        ORDER BY unit_buyout_price ASC
    """)
    rows = db.execute(stmt, {
        "item_id": item_id, "faction": faction,
    }).all()

    cumulative_units = 0
    depth_data = []
    for price, stack in rows:
        cumulative_units += stack
        depth_data.append({
            "price":            price,
            "cumulative_units": cumulative_units,
        })
    return depth_data


# ─── Crafting profitability ──────────────────────────────────────────────
def cheapest_cost(
    item_id: int,
    qty: int,
    item_listings: dict[int, list[tuple[int, int]]],
    recipe_dict: dict[int, dict],
    vendor_items: dict[int, int],
    depth: int = 0,
) -> int:
    if qty <= 0: return 0
    if depth > 12: return IMPOSSIBLE

    # 1. AH
    ah_cost, acquired = 0, 0
    for price, stack in item_listings.get(item_id, []):
        if acquired >= qty: break
        buy = min(stack, qty - acquired)
        ah_cost   += price * buy
        acquired  += buy
    ah_complete = acquired >= qty

    # 2. Vendor
    vendor_price = vendor_items.get(item_id)
    vendor_cost  = vendor_price * qty if vendor_price is not None else IMPOSSIBLE

    # 3. Crafting
    craft_cost = IMPOSSIBLE
    if item_id in recipe_dict:
        r = recipe_dict[item_id]
        total = 0
        ok = True
        for sub_id_str, sub_qty in r["reagents"].items():
            sub_id = int(sub_id_str)
            sub = cheapest_cost(
                sub_id, sub_qty * qty,
                item_listings, recipe_dict, vendor_items, depth + 1,
            )
            if sub >= IMPOSSIBLE:
                ok = False
                break
            total += sub
        if ok:
            craft_cost = total

    if ah_complete and ah_cost < vendor_cost and ah_cost < craft_cost:
        return ah_cost
    if vendor_cost < craft_cost:
        return vendor_cost if vendor_cost < IMPOSSIBLE else IMPOSSIBLE
    return craft_cost


def price_recipe(
    recipe: dict,
    quantity: int,
    faction: str,
    item_listings: dict[int, list[tuple[int, int]]],
    hist_avg: dict[int, int],
    item_lookup: dict[int, str],
) -> dict:
    output_id = recipe["output_item_id"]
    output_rows = item_listings.get(output_id, [])

    if output_rows:
        total_qty = sum(s for _, s in output_rows)
        total_val = sum(p * s for p, s in output_rows)
        avg_out = int(total_val / total_qty) if total_qty else 0
    else:
        avg_out = 0
    revenue = avg_out * quantity
    hist_out = hist_avg.get(output_id, avg_out)

    total_cost = 0
    reagent_details = []
    insufficient = False
    missing = None

    for reagent_id_str, base_qty in recipe["reagents"].items():
        reagent_id = int(reagent_id_str)
        req = base_qty * quantity

        ah_only = cheapest_cost(reagent_id, req, item_listings, {}, {})
        vendor_only = (
            VENDOR_ITEMS[reagent_id] * req
            if reagent_id in VENDOR_ITEMS else IMPOSSIBLE
        )
        all_in = cheapest_cost(
            reagent_id, req, item_listings, RECIPE_BY_OUTPUT, VENDOR_ITEMS,
        )

        if all_in >= IMPOSSIBLE:
            insufficient = True
            missing = f"{req}x {item_lookup.get(reagent_id, f'Item #{reagent_id}')}"
            break

        if all_in < min(ah_only, vendor_only):
            method = "Craft"
        elif vendor_only < ah_only:
            method = "Vendor"
        else:
            method = "AH"

        unit_cost = all_in // req if req else all_in
        available = sum(s for _, s in item_listings.get(reagent_id, []))
        reagent_details.append({
            "name":          item_lookup.get(reagent_id, f"Item #{reagent_id}"),
            "item_id":       reagent_id,
            "req":           req,
            "current_price": unit_cost,
            "avg_price":     hist_avg.get(reagent_id, unit_cost),
            "available":     available,
            "method":        method,
        })
        total_cost += all_in

    profit = None
    roi    = 0.0
    if not insufficient:
        profit = revenue - total_cost
        roi    = (profit / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "faction":            faction,
        "quantity":           quantity,
        "total_craft_cost":   total_cost,
        "total_revenue":      revenue,
        "total_profit":       profit,
        "roi":                roi,
        "insufficient_supply": insufficient,
        "missing_reagent":    missing,
        "reagent_details":    reagent_details,
        "hist_output_price":  hist_out,
    }


@router.get("/consumables")
def consumables(
    quantity: int = Query(1, ge=1, le=1000),
    faction:  str = Query("Horde"),
    include_unpriceable: bool = Query(False),
    db: Session = Depends(get_db),
):
    item_lookup: dict[int, str] = dict(ITEMS_FALLBACK)
    for row in db.execute(text(
        "SELECT item_id, item_name FROM dim_items"
    )).all():
        if row[1]:
            item_lookup[row[0]] = row[1]

    faction_cache = {}
    for side in ("Horde", "Alliance"):
        faction_cache[side] = _load_faction(side, db)

    results = []
    for recipe in RECIPES:
        output_id = recipe["output_item_id"]
        output_name = item_lookup.get(output_id, f"Item #{output_id}")

        recipe_name = recipe["name"]
        if recipe_name.startswith("Item #"):
            recipe_name = output_name

        if not recipe.get("reagents"):
            if include_unpriceable:
                results.append({
                    "name":             recipe_name,
                    "category":         recipe.get("category", "Other"),
                    "output_item_name": output_name,
                    "output_item_id":   output_id,
                    "unpriceable":      True,
                    "horde":            None,
                    "alliance":         None,
                })
            continue

        result_for_side = {}
        for side in ("Horde", "Alliance"):
            listings, avg = faction_cache[side]
            result_for_side[side] = price_recipe(
                recipe, quantity, side, listings, avg, item_lookup,
            )

        results.append({
            "name":             recipe_name,
            "category":         recipe.get("category", "Other"),
            "output_item_name": output_name,
            "output_item_id":   output_id,
            "unpriceable":      False,
            "quantity":         quantity,
            "horde":            result_for_side["Horde"],
            "alliance":         result_for_side["Alliance"],
        })

    return results # <--- THIS WAS MISSING


# ─── Helper: on-demand per-faction listing load ──────────────────────────
def _load_faction(faction: str, db: Session):
    listings: dict[int, list[tuple[int, int]]] = {}
    for item_id, price, stack in db.execute(text("""
        SELECT item_id, unit_buyout_price, stack_size
        FROM live_auction_book
        WHERE faction = :faction
        ORDER BY item_id, unit_buyout_price
    """), {"faction": faction}).all():
        listings.setdefault(item_id, []).append((price, stack))

    cutoff = int(time.time()) - (7 * 86400)
    rows = db.execute(text("""
        SELECT item_id,
               SUM(close_price * volume),
               SUM(volume)
        FROM ohlcv_session
        WHERE bucket_start > :cutoff AND faction = :faction
        GROUP BY item_id
    """), {"cutoff": cutoff, "faction": faction}).all()
    avg = {r[0]: int(r[1] / r[2]) for r in rows if r[2] and r[2] > 0}
    return listings, avg


# ─── Arbitrage ───────────────────────────────────────────────────────────
@router.get("/arbitrage")
def get_arbitrage(
    direction: str = Query("ally_to_horde"),
    db: Session = Depends(get_db),
):
    hist_stmt = text("""
        SELECT item_id, faction, median_price 
        FROM ohlcv_session 
        WHERE bucket_start >= (EXTRACT(EPOCH FROM NOW()) - 604800)::bigint
    """)
    medians = {(r[0], r[1]): r[2] for r in db.execute(hist_stmt).all() if r[2]}

    live_stmt = text("""
        SELECT item_id, item_name, faction, unit_buyout_price, stack_size
        FROM live_auction_book
        ORDER BY item_id, faction, unit_buyout_price ASC
    """)
    rows = db.execute(live_stmt).all()

    book = {}
    for r in rows:
        key = (r.item_id, r.faction)
        if key not in book: book[key] = {"name": r.item_name, "listings": []}
        book[key]["listings"].append({"price": r.unit_buyout_price, "qty": r.stack_size})

    def get_craft_cost(reagents, faction):
        total_cost = 0
        breakdown = []
        for rid_str, req_qty in reagents.items():
            rid = int(rid_str)
            listings = book.get((rid, faction), [])
            cost, acquired = 0, 0
            for listing in listings:
                if acquired >= req_qty: break
                buy = min(listing["qty"], req_qty - acquired)
                cost += buy * listing["price"]
                acquired += buy
            if acquired < req_qty: return None, [] 
            total_cost += cost
            breakdown.append({"item_id": rid, "qty": req_qty, "cost": cost})
        return total_cost, breakdown

    opportunities = []
    all_items = set(k[0] for k in book.keys())

    for item_id in all_items:
        horde_listings = book.get((item_id, "Horde"), {}).get("listings", [])
        ally_listings = book.get((item_id, "Alliance"), {}).get("listings", [])
        
        if not horde_listings or not ally_listings: continue

        item_name = book.get((item_id, "Horde"), book.get((item_id, "Alliance"))).get("name")

        if direction == "ally_to_horde":
            source, dest, dest_faction = ally_listings, horde_listings, "Horde"
        else:
            source, dest, dest_faction = horde_listings, ally_listings, "Alliance"

        buy_price = source[0]["price"]
        total_available = sum(l["qty"] for l in source)

        current_cheapest_dest = dest[0]["price"]
        median_dest = medians.get((item_id, dest_faction), current_cheapest_dest)
        
        if current_cheapest_dest > (median_dest * 5):
            realistic_sell_price = median_dest
        else:
            realistic_sell_price = min(current_cheapest_dest, median_dest)

        if (item_id, dest_faction) not in medians:
            realistic_sell_price = min(realistic_sell_price, int(buy_price * 3))

        profit_per_unit = int((realistic_sell_price * 0.95) - buy_price)

        if profit_per_unit > 0:
            craft_data = None
            if item_id in RECIPE_BY_OUTPUT:
                recipe = RECIPE_BY_OUTPUT[item_id]
                ally_cost, ally_mats = get_craft_cost(recipe["reagents"], "Alliance")
                horde_cost, horde_mats = get_craft_cost(recipe["reagents"], "Horde")
                
                craft_data = {
                    "ally_cost": ally_cost or 0,
                    "horde_cost": horde_cost or 0,
                    "reagents": [
                        {
                            "name": next((n for i, n in ITEMS_FALLBACK.items() if i == int(rid)), f"Item #{rid}"),
                            "qty": req_qty,
                            "ally_cost": next((m["cost"] for m in ally_mats if m["item_id"] == int(rid)), 0),
                            "horde_cost": next((m["cost"] for m in horde_mats if m["item_id"] == int(rid)), 0)
                        } for rid, req_qty in recipe["reagents"].items()
                    ]
                }

            opportunities.append({
                "item_id": item_id,
                "item_name": item_name,
                "buy_price": buy_price,
                "sell_price": realistic_sell_price,
                "profit_per_unit": profit_per_unit,
                "total_profit": profit_per_unit * total_available,
                "qty_available": total_available,
                "roi": (profit_per_unit / buy_price) * 100,
                "craft_data": craft_data
            })

    opportunities.sort(key=lambda x: x["roi"], reverse=True)
    return opportunities[:100]