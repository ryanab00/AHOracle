"""API routes for AH Oracle.

Reads the hand-maintained recipes.json / items.json from ahoracle/api/
and serves the endpoints consumed by the Nuxt frontend.
"""
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import cast, func, or_, select, text, String
from sqlalchemy.orm import Session

from ahoracle.db import make_engine
from ahoracle.models import (
    DimItem,
    LiveAuctionBook,
    OHLCVSession,
    ScanLog,
)

router = APIRouter()
engine = make_engine()


def get_db():
    with Session(engine) as session:
        yield session


# ─────────────────────────────────────────────────────────────────────────────
# Data files
# ─────────────────────────────────────────────────────────────────────────────
_API_DIR = Path(__file__).parent
RECIPES_FILE = _API_DIR / "recipes.json"
ITEMS_FILE = _API_DIR / "items.json"

RECIPES: list[dict] = []
if RECIPES_FILE.exists():
    RECIPES = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))

ITEMS_FALLBACK: dict[int, str] = {}
if ITEMS_FILE.exists():
    raw = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    ITEMS_FALLBACK = {int(k): v for k, v in raw.items()}

# Only recipes with at least one reagent can be priced.
PRICEABLE_RECIPES = [r for r in RECIPES if r.get("reagents")]

# Map output_item_id -> recipe. If multiple recipes produce the same item,
# keep the first (they're sorted by category/name from the extractor).
RECIPE_BY_OUTPUT: dict[int, dict] = {}
for _r in PRICEABLE_RECIPES:
    RECIPE_BY_OUTPUT.setdefault(_r["output_item_id"], _r)

# Vendor prices in copper. Anything vendorable that appears as a reagent
# MUST be listed here, or the cost calculator will treat it as unavailable.
VENDOR_ITEMS: dict[int, int] = {
    3371: 5,      # Crystal Vial (low)
    3372: 40,     # Leaded Vial
    8925: 50,     # Crystal Vial (mid)
    16583: 250,   # Crystal Vial (high)
}

# The specific raid consumables you want on the /consumables page.
# This prevents Transmutes, cheap oils, and other junk from cluttering the view.
RAID_CONSUMES_IDS = {
    13506, 13510, 13511, 13512, 13513,  # Flasks
    13457, 13456, 13458, 13459, 13461,  # Greater Prot Pots
    6049, 6050, 6051, 6052, 7255, 7256, 7257, 7258, 7259, # Regular Prot Pots
    9172, 13455, 6624,                  # LIP, Gtr Stoneshield, Free Action
    13447, 13445, 13452, 13454, 21546, 20007, 9187, # Elixirs
    24801, 22480, 15906,                # Food
    10646, 18641, 17552, 11451,         # Damage
    22757, 25129, 25130                 # Weapon Imbues
}

IMPOSSIBLE = 999_999_999_99


# ─────────────────────────────────────────────────────────────────────────────
# Market data helpers
# ─────────────────────────────────────────────────────────────────────────────
def _item_listings_from_db(
    db: Session, faction: str
) -> dict[int, list[tuple[int, int]]]:
    """Returns {item_id: [(unit_price, stack_size), ...] sorted ascending}."""
    stmt = (
        select(
            LiveAuctionBook.item_id,
            LiveAuctionBook.unit_buyout_price,
            LiveAuctionBook.stack_size,
        )
        .where(LiveAuctionBook.faction == faction)
        .order_by(LiveAuctionBook.item_id, LiveAuctionBook.unit_buyout_price)
    )
    out: dict[int, list[tuple[int, int]]] = {}
    for item_id, price, size in db.execute(stmt):
        out.setdefault(item_id, []).append((int(price), int(size)))
    return out


def _seven_day_avg(db: Session, faction: str) -> dict[int, int]:
    """Average OHLCV avg_price over the last 7 days per item."""
    cutoff = int(time.time()) - 7 * 86400
    sql = text(
        """
        SELECT item_id, AVG(avg_price) AS avg
        FROM ohlcv_session
        WHERE faction = :faction
          AND bucket_start >= :cutoff
          AND avg_price IS NOT NULL
        GROUP BY item_id
        """
    )
    out: dict[int, int] = {}
    for row in db.execute(sql, {"faction": faction, "cutoff": cutoff}):
        out[int(row.item_id)] = int(row.avg or 0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Recursive cheapest-source pricing (used for reagents, and by /arbitrage)
# ─────────────────────────────────────────────────────────────────────────────
def build_craft_cost(
    item_id: int,
    qty: int,
    item_listings: dict[int, list[tuple[int, int]]],
    recipe_dict: dict[int, dict],
    max_depth: int = 12,
) -> dict:
    """Cheapest way to obtain `qty` of `item_id` via Vendor / AH / Craft.

    Returns {cost, source, complete, unit_cost, breakdown}.
    """
    if qty <= 0:
        return {"cost": 0, "source": "None", "complete": True,
                "unit_cost": 0, "breakdown": []}

    cache: dict[tuple[int, int], dict] = {}

    def resolve(iid: int, need: int, path: frozenset[int], depth: int) -> dict:
        key = (iid, need)
        if key in cache:
            return cache[key]
        if depth > max_depth:
            return {"cost": IMPOSSIBLE, "source": None, "complete": False,
                    "unit_cost": 0, "breakdown": []}

        options: list[tuple[str, int, bool, list]] = []

        # ── Vendor ──────────────────────────────────────────────
        vp = VENDOR_ITEMS.get(iid)
        if vp is not None:
            options.append(("Vendor", vp * need, True, []))

        # ── AH order book (walk cheapest listings first) ────────
        rows = item_listings.get(iid, [])
        if rows:
            total, taken = 0, 0
            for price, size in rows:
                if taken >= need:
                    break
                take = min(size, need - taken)
                total += price * take
                taken += take
            if taken >= need:
                options.append(("AH", total, True, []))

        # ── Craft (recursively price the reagent tree) ──────────
        recipe = recipe_dict.get(iid)
        if recipe and iid not in path:
            out_q = max(1, int(recipe.get("output_quantity", 1)))
            crafts_needed = -(-need // out_q)  # ceil(need / out_q)
            total = 0
            complete = True
            breakdown: list[dict] = []
            new_path = path | {iid}
            for sub_id_str, base_qty in recipe["reagents"].items():
                sub_id = int(sub_id_str)
                sub_need = int(base_qty) * crafts_needed
                sub = resolve(sub_id, sub_need, new_path, depth + 1)
                total += sub["cost"]
                complete = complete and sub["complete"]
                breakdown.append({
                    "item_id": sub_id,
                    "name": ITEMS_FALLBACK.get(sub_id, f"Item #{sub_id}"),
                    "qty": sub_need,
                    "cost": sub["cost"],
                    "source": sub["source"],
                    "complete": sub["complete"],
                })
                if not complete:
                    break
            if complete:
                options.append(("Craft", total, True, breakdown))

        if not options:
            result = {"cost": IMPOSSIBLE, "source": None, "complete": False,
                      "unit_cost": 0, "breakdown": []}
        else:
            source, cost, complete, breakdown = min(options, key=lambda o: o[1])
            result = {
                "cost": cost,
                "source": source,
                "complete": complete,
                "unit_cost": cost // need if need else 0,
                "breakdown": breakdown,
            }
        cache[key] = result
        return result

    return resolve(item_id, qty, frozenset(), 0)


def _price_recipe(recipe: dict, qty: int, item_listings: dict, hist_avg: dict) -> dict:
    """Helper to price a recipe and shape the response for the frontend."""
    out_id = int(recipe["output_item_id"])
    
    reagent_details = []
    craft_total = 0
    craft_complete = True
    max_crafts = 9999  # Start high, we'll find the bottleneck
    
    for sub_id_str, base_qty in recipe["reagents"].items():
        sub_id = int(sub_id_str)
        sub_need = int(base_qty) * qty
        sub = build_craft_cost(sub_id, sub_need, item_listings, RECIPE_BY_OUTPUT)
        
        if sub["complete"]:
            craft_total += sub["cost"]
        else:
            craft_complete = False
            
        available = sum(s for _, s in item_listings.get(sub_id, []))
        
        # Calculate max crafts based on this specific reagent
        if sub["source"] == "Vendor":
            possible_crafts = 9999 # Vendor is infinite
        else:
            possible_crafts = available // int(base_qty)
            
        max_crafts = min(max_crafts, possible_crafts)

        reagent_details.append({
            "name": ITEMS_FALLBACK.get(sub_id, f"Item #{sub_id}"),
            "req": sub_need,
            "current_price": (sub["cost"] // sub_need) if (sub_need and sub["complete"]) else 0,
            "avg_price": hist_avg.get(sub_id, 0),
            "available": available,
            "method": sub["source"] or "?",
            "complete": sub["complete"],
        })

    # If a vendor ingredient is the only thing required, cap the max crafts artificially
    if max_crafts == 9999:
        max_crafts = 999 

    craft_cost = craft_total if craft_complete else None
    
    out_rows = item_listings.get(out_id, [])
    if out_rows:
        total_qty = sum(s for _, s in out_rows)
        total_val = sum(p * s for p, s in out_rows)
        avg_out = int(total_val / total_qty) if total_qty else 0
    else:
        avg_out = 0
        
    revenue = avg_out * qty
    profit = (revenue - (craft_cost or 0)) if craft_complete else 0
    roi = (profit / craft_cost * 100) if (craft_cost and craft_cost > 0) else 0

    return {
        "name": recipe["name"],
        "category": recipe.get("profession", "Other"),
        "output_item_id": out_id,
        "quantity": qty,
        "max_crafts": max_crafts,
        "total_craft_cost": craft_cost or 0,
        "total_revenue": revenue,
        "total_profit": profit,
        "roi": roi,
        "insufficient_supply": not craft_complete,
        "avg_output_price": avg_out,
        "hist_output_price": hist_avg.get(out_id, avg_out),
        "reagent_details": reagent_details,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    scans = db.scalar(select(func.count()).select_from(ScanLog)) or 0
    items = db.scalar(select(func.count()).select_from(DimItem)) or 0
    live = db.scalar(select(func.count()).select_from(LiveAuctionBook)) or 0
    return {
        "scans": scans,
        "items": items,
        "live": live,
        "recipes": len(RECIPES),
        "priceable_recipes": len(PRICEABLE_RECIPES),
    }


@router.get("/last_scan")
def get_last_scan(db: Session = Depends(get_db)):
    stmt = (
        select(ScanLog.faction, func.max(ScanLog.scan_timestamp))
        .group_by(ScanLog.faction)
    )
    out = {"Horde": 0, "Alliance": 0, "Neutral": 0}
    for faction, ts in db.execute(stmt):
        if faction in out:
            out[faction] = int(ts or 0)
    return out


@router.get("/auctions")
def get_auctions(
    faction: str = "Horde",
    page: int = 1,
    per_page: int = 200,
    q: str = "",
    db: Session = Depends(get_db),
):
    base = select(
        LiveAuctionBook.item_id,
        func.min(LiveAuctionBook.item_name).label("item_name"),
        func.count().label("num_listings"),
        func.sum(LiveAuctionBook.stack_size).label("total_quantity"),
        func.min(LiveAuctionBook.unit_buyout_price).label("min_price"),
        func.max(LiveAuctionBook.unit_buyout_price).label("max_price"),
    ).where(LiveAuctionBook.faction == faction)

    if q:
        q_like = f"%{q}%"
        base = base.where(
            or_(
                LiveAuctionBook.item_name.ilike(q_like),
                cast(LiveAuctionBook.item_id, String).like(q_like),
            )
        )

    base = base.group_by(LiveAuctionBook.item_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(func.count().desc())
        .limit(per_page)
        .offset(max(0, page - 1) * per_page)
    ).all()

    items = []
    for r in rows:
        items.append({
            "item_id": int(r.item_id),
            "item_name": r.item_name
                        or ITEMS_FALLBACK.get(int(r.item_id), f"Item #{r.item_id}"),
            "num_listings": int(r.num_listings),
            "total_quantity": int(r.total_quantity or 0),
            "min_price": int(r.min_price or 0),
            "max_price": int(r.max_price or 0),
        })
    return {"page": page, "per_page": per_page, "total": total, "items": items}


@router.get("/items/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(OHLCVSession)
        .where(OHLCVSession.item_id == item_id)
        .order_by(OHLCVSession.bucket_start)
    )
    history = list(db.scalars(stmt))

    time_map: dict[int, dict] = {}
    for h in history:
        t = h.bucket_start * 1000
        bucket = time_map.setdefault(t, {"time": t})
        bucket[f"{h.faction}Price"] = h.avg_price
        bucket[f"{h.faction}Volume"] = h.volume

    listing_stmt = (
        select(LiveAuctionBook)
        .where(LiveAuctionBook.item_id == item_id)
        .order_by(LiveAuctionBook.unit_buyout_price, LiveAuctionBook.stack_size)
    )
    listings = list(db.scalars(listing_stmt))

    depth_by_faction: dict[str, list[dict]] = {}
    for row in listings:
        bucket = depth_by_faction.setdefault(row.faction, [])
        bucket.append({"price": row.unit_buyout_price,
                       "stack_size": row.stack_size})
    for bucket in depth_by_faction.values():
        cumulative = 0
        for entry in bucket:
            cumulative += entry["stack_size"]
            entry["cumulative_units"] = cumulative

    item = db.get(DimItem, item_id)
    return {
        "item": {
            "item_id": item_id,
            "item_name": (item.item_name if item and item.item_name else None)
                         or ITEMS_FALLBACK.get(item_id, f"Item #{item_id}"),
        },
        "history": list(time_map.values()),
        "depth": depth_by_faction,
        "listings": [
            {
                "faction": l.faction,
                "seller": l.seller,
                "stack_size": l.stack_size,
                "unit_buyout_price": l.unit_buyout_price,
                "duration_hours": l.duration_hours,
            }
            for l in listings
        ],
    }


@router.get("/consumables")
def get_consumables(
    quantity: int = 1,
    faction: str = "Horde",
    db: Session = Depends(get_db),
):
    item_listings = _item_listings_from_db(db, faction)
    hist_avg = _seven_day_avg(db, faction)
    qty = max(1, quantity)

    out = []
    for recipe in RECIPES:
        out_id = int(recipe["output_item_id"])
        if out_id not in RAID_CONSUMES_IDS:
            continue
        out.append(_price_recipe(recipe, qty, item_listings, hist_avg))

    return out


@router.get("/professions")
def get_professions(
    quantity: int = 1,
    faction: str = "Horde",
    db: Session = Depends(get_db),
):
    item_listings = _item_listings_from_db(db, faction)
    hist_avg = _seven_day_avg(db, faction)
    qty = max(1, quantity)

    out = []
    for recipe in RECIPES:
        out.append(_price_recipe(recipe, qty, item_listings, hist_avg))

    return out


@router.get("/arbitrage")
def get_arbitrage(
    direction: str = "ally_to_horde",
    db: Session = Depends(get_db),
):
    src_faction = "Alliance" if direction == "ally_to_horde" else "Horde"
    dst_faction = "Horde" if direction == "ally_to_horde" else "Alliance"

    src_listings = _item_listings_from_db(db, src_faction)
    dst_listings = _item_listings_from_db(db, dst_faction)

    out = []
    for recipe in RECIPES:
        out_id = int(recipe["output_item_id"])

        src_rows = src_listings.get(out_id, [])
        dst_rows = dst_listings.get(out_id, [])
        if not src_rows or not dst_rows:
            continue

        # Direct flip: cheapest buy on source, undercut cheapest on dest.
        buy_price = src_rows[0][0]
        sell_price = max(1, dst_rows[0][0] - 1)
        qty_available = sum(s for _, s in src_rows)

        profit_per = sell_price - buy_price
        if profit_per <= 0:
            continue

        total_profit = profit_per * qty_available
        roi = (profit_per / buy_price * 100) if buy_price else 0

        # Crafting comparison (informational)
        src_craft = build_craft_cost(out_id, 1, src_listings, RECIPE_BY_OUTPUT)
        dst_craft = build_craft_cost(out_id, 1, dst_listings, RECIPE_BY_OUTPUT)

        craft_data = None
        if src_craft["complete"] or dst_craft["complete"]:
            reagents = []
            for entry in src_craft.get("breakdown", []):
                sub_id = entry["item_id"]
                sub_qty = entry["qty"]
                s_src = build_craft_cost(sub_id, sub_qty, src_listings, RECIPE_BY_OUTPUT)
                s_dst = build_craft_cost(sub_id, sub_qty, dst_listings, RECIPE_BY_OUTPUT)
                reagents.append({
                    "name": entry["name"],
                    "qty": sub_qty,
                    "ally_cost": (s_src["cost"] if direction == "ally_to_horde" else s_dst["cost"]) if (s_src["complete"] or s_dst["complete"]) else 0,
                    "horde_cost": (s_dst["cost"] if direction == "ally_to_horde" else s_src["cost"]) if (s_src["complete"] or s_dst["complete"]) else 0,
                })
            craft_data = {
                "ally_cost": (src_craft["cost"] if direction == "ally_to_horde" else dst_craft["cost"]) if (src_craft["complete"] or dst_craft["complete"]) else 0,
                "horde_cost": (dst_craft["cost"] if direction == "ally_to_horde" else src_craft["cost"]) if (src_craft["complete"] or dst_craft["complete"]) else 0,
                "reagents": reagents,
            }

        out.append({
            "item_id": out_id,
            "item_name": ITEMS_FALLBACK.get(out_id, f"Item #{out_id}"),
            "buy_price": buy_price,
            "sell_price": sell_price,
            "qty_available": qty_available,
            "roi": roi,
            "total_profit": total_profit,
            "craft_data": craft_data,
        })

    out.sort(key=lambda x: x["total_profit"], reverse=True)
    return out