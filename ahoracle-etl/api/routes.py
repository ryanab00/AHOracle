import json
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from ahoracle_etl.db import make_engine
from ahoracle_etl.models import LiveAuctionBook, DimItem, ScanLog, OHLCVSession

router = APIRouter()
engine = make_engine()

def get_db():
    with Session(engine) as session:
        yield session

# ─── Health & Status ─────────────────────────────────────────────────────

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    scans = db.scalar(select(func.count()).select_from(ScanLog)) or 0
    items = db.scalar(select(func.count()).select_from(DimItem)) or 0
    live = db.scalar(select(func.count()).select_from(LiveAuctionBook)) or 0
    return {"scans": scans, "items": items, "live_listings": live}

@router.get("/last_scan")
def get_last_scan(db: Session = Depends(get_db)):
    # Get the latest scan timestamp for each faction
    stmt = select(ScanLog.faction, func.max(ScanLog.scan_timestamp)).group_by(ScanLog.faction)
    rows = db.execute(stmt).all()
    
    result = {faction: ts for faction, ts in rows}
    
    # Ensure all expected factions have an entry (default to 0 if never scanned)
    for faction in ["Horde", "Alliance", "Neutral"]:
        if faction not in result:
            result[faction] = 0
            
    return result

# ─── Auctions ────────────────────────────────────────────────────────────

@router.get("/auctions")
def auction_summary(
    faction: str = Query("Horde"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    stmt = text("""
        SELECT item_id, item_name, COUNT(*) as num_listings, 
               SUM(stack_size) as total_quantity, MIN(unit_buyout_price) as min_price,
               MAX(unit_buyout_price) as max_price
        FROM live_auction_book WHERE faction = :faction
        GROUP BY item_id, item_name ORDER BY min_price ASC LIMIT :limit OFFSET :offset
    """)
    count_stmt = text("SELECT COUNT(DISTINCT item_id) FROM live_auction_book WHERE faction = :faction")
    
    total = db.execute(count_stmt, {"faction": faction}).scalar()
    rows = db.execute(stmt, {"faction": faction, "limit": per_page, "offset": (page - 1) * per_page}).all()
    
    results = [{"item_id": r[0], "item_name": r[1], "num_listings": r[2], "total_quantity": r[3], "min_price": r[4], "max_price": r[5]} for r in rows]
    return {"total": total, "page": page, "per_page": per_page, "results": results}

@router.get("/auctions/{item_id}")
def auction_listings(item_id: int, faction: str = Query("Horde"), db: Session = Depends(get_db)):
    stmt = (select(LiveAuctionBook).where(LiveAuctionBook.item_id == item_id, LiveAuctionBook.faction == faction).order_by(LiveAuctionBook.unit_buyout_price.asc()).limit(200))
    return list(db.scalars(stmt))

# ─── Items ───────────────────────────────────────────────────────────────

@router.get("/items/{item_id}/stats")
def item_stats(item_id: int, faction: str = Query("Horde"), db: Session = Depends(get_db)):
    item = db.get(DimItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    vol_stmt = text("SELECT faction, unit_price, units_vanished, events FROM v_volume_at_price WHERE item_id = :item_id AND faction = :faction ORDER BY unit_price")
    vol_rows = db.execute(vol_stmt, {"item_id": item_id, "faction": faction}).all()
    
    return {
        "item": {"item_id": item.item_id, "item_name": item.item_name},
        "volume_at_price": [{"unit_price": r[1], "units_vanished": r[2], "events": r[3]} for r in vol_rows]
    }

@router.get("/items/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    stmt = select(OHLCVSession).where(OHLCVSession.item_id == item_id).order_by(OHLCVSession.bucket_start.asc())
    history = list(db.scalars(stmt))
    time_map = {}
    for h in history:
        t = h.bucket_start * 1000
        if t not in time_map:
            time_map[t] = {"time": t, "HordePrice": None, "AlliancePrice": None, "HordeVolume": 0, "AllianceVolume": 0}
        if h.faction == "Horde":
            time_map[t]["HordePrice"] = h.close_price
            time_map[t]["HordeVolume"] = h.volume
        elif h.faction == "Alliance":
            time_map[t]["AlliancePrice"] = h.close_price
            time_map[t]["AllianceVolume"] = h.volume
    return list(time_map.values())

@router.get("/items/{item_id}/current_depth")
def item_current_depth(item_id: int, faction: str = Query("Horde"), db: Session = Depends(get_db)):
    stmt = text("""
        SELECT unit_buyout_price, SUM(stack_size) as units_at_price
        FROM live_auction_book WHERE item_id = :item_id AND faction = :faction
        GROUP BY unit_buyout_price ORDER BY unit_buyout_price ASC LIMIT 50
    """)
    rows = db.execute(stmt, {"item_id": item_id, "faction": faction}).all()
    cumulative_units = 0
    depth_data = []
    for r in rows:
        cumulative_units += r[1]
        depth_data.append({"price": r[0], "units_at_price": r[1], "cumulative_units": cumulative_units})
    return depth_data

# ─── Consumables Calculator ──────────────────────────────────────────────

# Helper for recursive crafting cost evaluation
def get_cheapest_cost_for_qty(item_name, qty, item_listings, recipe_dict, vendor_items, depth=0):
    if depth > 3: return 99999999999 # Prevent infinite loops
    
    if item_name in vendor_items:
        return vendor_items[item_name] * qty

    # 1. AH Cost (Order Book depth matching)
    ah_cost = 0
    acquired = 0
    for price, stack in item_listings.get(item_name, []):
        if acquired >= qty: break
        buy = min(stack, qty - acquired)
        ah_cost += buy * price
        acquired += buy
        
    if acquired < qty:
        ah_cost = 99999999999 # Not enough on AH
        
    # 2. Craft Cost
    craft_cost = 99999999999
    if item_name in recipe_dict:
        r = recipe_dict[item_name]
        c_cost = 0
        possible = True
        for sub_name, sub_qty in r["reagents"].items():
            sub_c = get_cheapest_cost_for_qty(sub_name, sub_qty * qty, item_listings, recipe_dict, vendor_items, depth + 1)
            if sub_c >= 99999999999:
                possible = False
                break
            c_cost += sub_c
        if possible:
            craft_cost = c_cost
            
    return min(ah_cost, craft_cost)

@router.get("/consumables")
def get_consumables(
    faction: str = Query("Horde"), 
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db)
):
    json_path = Path(__file__).parent / "recipes.json"
    if not json_path.exists():
        raise HTTPException(status_code=500, detail="recipes.json not found.")
        
    recipes = json.loads(json_path.read_text())
    recipe_dict = {r["output_item_name"]: r for r in recipes}
    
    VENDOR_ITEMS = {
        "Crystal Vial": 500, "Leaded Vial": 100, "Soothing Spices": 40, 
        "Mild Spices": 40, "Simple Flour": 20, "Refreshing Spring Water": 25
    }
    
    # Pre-fetch ALL live AH data into memory for rapid recursive checking
    all_listings = db.execute(text("""
        SELECT item_name, unit_buyout_price, stack_size 
        FROM live_auction_book 
        WHERE faction = :faction
        ORDER BY unit_buyout_price ASC
    """), {"faction": faction}).all()
    
    item_listings = {}
    for name, price, stack in all_listings:
        if name not in item_listings: item_listings[name] = []
        item_listings[name].append((price, stack))
        
    # Pre-fetch 7-day averages
    cutoff = int(time.time()) - (7 * 86400)
    hist_rows = db.execute(text("""
        SELECT o.item_id, SUM(o.close_price * o.volume), SUM(o.volume)
        FROM ohlcv_session o WHERE o.bucket_start >= :cutoff
        GROUP BY o.item_id
    """), {"cutoff": cutoff}).all()
    hist_avg = {r[0]: int(r[1]/r[2]) for r in hist_rows if r[2] > 0}
    
    item_lookup = {r[0]: r[1] for r in db.execute(text("SELECT item_name, item_id FROM dim_items")).all()}

    results = []
    
    for recipe in recipes:
        output_name = recipe["output_item_name"]
        output_id = item_lookup.get(output_name)
        
        # Output Revenue
        output_rows = item_listings.get(output_name, [])
        if not output_rows:
            continue
            
        total_output_qty = sum(r[1] for r in output_rows)
        total_output_val = sum(r[0] * r[1] for r in output_rows)
        avg_output_price = int(total_output_val / total_output_qty)
        
        total_revenue = avg_output_price * quantity
        avg_hist_output = hist_avg.get(output_id, avg_output_price)
        
        # Craft Cost
        total_craft_cost = 0
        insufficient_supply = False
        missing_reagent = None
        reagent_details = []

        for reagent_name, base_qty in recipe["reagents"].items():
            req_qty = base_qty * quantity
            
            # Recursive best cost
            best_cost = get_cheapest_cost_for_qty(reagent_name, req_qty, item_listings, recipe_dict, VENDOR_ITEMS)
            # AH only cost (to determine if we crafted it)
            ah_only_cost = get_cheapest_cost_for_qty(reagent_name, req_qty, item_listings, {}, VENDOR_ITEMS)
            
            method = "AH"
            if reagent_name in VENDOR_ITEMS:
                method = "Vendor"
            elif best_cost < ah_only_cost:
                method = "Craft"
                
            if best_cost >= 99999999999:
                insufficient_supply = True
                missing_reagent = f"{req_qty}x {reagent_name}"
                break
                
            total_craft_cost += best_cost
            
            # Unit cost for display
            unit_cost = int(best_cost / req_qty)
            reagent_id = item_lookup.get(reagent_name)
            r_hist = hist_avg.get(reagent_id, unit_cost)
            
            # Raw available on AH
            available = sum(s for p, s in item_listings.get(reagent_name, []))
            
            reagent_details.append({
                "name": reagent_name, "req": req_qty, 
                "current_price": unit_cost, "avg_price": r_hist, 
                "available": available, "method": method
            })

        profit = None
        roi = 0.0
        if not insufficient_supply and total_craft_cost > 0:
            profit = total_revenue - total_craft_cost
            roi = (profit / total_craft_cost) * 100

        results.append({
            "category": recipe["category"],
            "name": recipe["name"],
            "quantity": quantity,
            "output_price": output_rows[0][0],
            "avg_output_price": avg_output_price,
            "hist_output_price": avg_hist_output,
            "total_revenue": total_revenue,
            "total_craft_cost": total_craft_cost if not insufficient_supply else None,
            "avg_craft_cost": (total_craft_cost / quantity) if not insufficient_supply else None,
            "total_profit": profit,
            "roi": roi,
            "insufficient_supply": insufficient_supply,
            "missing_reagent": missing_reagent,
            "reagents": recipe["reagents"],
            "reagent_details": reagent_details
        })
        
    return results