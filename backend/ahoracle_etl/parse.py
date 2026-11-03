"""Parse AHOracle or AHDB SavedVariables into Python data structures."""
from pathlib import Path
import re
import slpp
import math

FACTIONS = ("Alliance", "Horde", "Neutral")


def _slpp_parse(text: str):
    # Support both slpp versions
    for name in ("decode", "parse"):
        fn = getattr(slpp, name, None)
        if callable(fn):
            return fn(text)
    cls = getattr(slpp, "SLPP", None)
    if cls is not None:
        parser = cls()
        for name in ("decode", "parse"):
            fn = getattr(parser, name, None)
            if callable(fn):
                return fn(text)
    raise RuntimeError("The installed 'slpp' package has no usable parser.")


def parse_saved_variables(path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    
    # 1. Locate the table assignment (AHOracleDB or AuctionDBSaved)
    match = re.search(r'(AHOracleDB|AuctionDBSaved)\s*=\s*(\{)', text)
    if not match:
        raise ValueError(f"No known database table found in {path}")
        
    brace = match.start(2)
    return _slpp_parse(text[brace:])


def extract_scans(db: dict):
    """Yields (faction, scan_dict) depending on which addon format was parsed."""
    if "ah" in db:
        yield from extract_ahdb_scans(db)
    else:
        yield from extract_ahoracle_scans(db)


# ─── AHDB Parser ─────────────────────────────────────────────────────────

def extract_ahdb_scans(db):
    ah_list = db.get("ah", [])
    item_db = db.get("itemDB_2", {})
    
    # 1. Build a mapping of item_key (e.g. "i9830?153") to item_id and item_name
    items = {}
    for key, val in item_db.items():
        # Skip non-string values like _count_ or _infoCount_
        if not isinstance(val, str):
            continue
            
        # AHDB stores item data in a pipe-delimited string. 
        # We extract the ID and Name directly from the full string.
        id_match = re.search(r'item:(\d+)', val)
        item_id = int(id_match.group(1)) if id_match else 0
        
        name_match = re.search(r'\[(.*?)\]', val)
        name = name_match.group(1) if name_match else "Unknown"
        
        if item_id:
            items[key] = {
                "item_id": item_id,
                "item_name": name,
            }
            
    # 2. Parse the compressed auction data
    for scan_entry in ah_list:
        faction = scan_entry.get("faction", "Unknown")
        ts = int(scan_entry.get("ts", 0))
        data_str = scan_entry.get("data", "")
        
        listings = []
        
        # Regex to find item blocks: matches "i123" or "i123?456" followed by "!"
        pattern = r'(i\d+(?:\?\d+)?)!(.*?)(?=(?:i\d+(?:\?\d+)?!)|$)'
        
        for match in re.finditer(pattern, data_str):
            item_key = match.group(1)
            block = match.group(2).strip()
            
            item_info = items.get(item_key, {})
            item_id = item_info.get("item_id", 0)
            item_name = item_info.get("item_name", "Unknown")
            
            if not item_id:
                continue

            # Block format: "seller1/a1&a2!seller2/a1..."
            seller_blocks = block.split('!')
            for sb in seller_blocks:
                if not sb: continue
                parts = sb.split('/')
                if len(parts) >= 2:
                    seller = parts[0].strip()
                    if not seller:
                        seller = "Unknown"
                    auctions_str = parts[1]
                    auctions = auctions_str.split('&')
                    for auc in auctions:
                        fields = auc.split(',')
                        if len(fields) >= 4:
                            # format: timeleft,itemCount,minBid,buyoutPrice,curBid
                            timeleft = int(fields[0]) if fields[0] else 0
                            itemCount = int(fields[1]) if fields[1] else 0
                            minBid = int(fields[2]) if fields[2] else 0
                            buyoutPrice = int(fields[3]) if fields[3] else 0
                            
                            if itemCount > 0 and buyoutPrice > 0:
                                listings.append({
                                    "item_id": item_id,
                                    "item_name": item_name,
                                    "seller": seller,
                                    "stack_size": itemCount,
                                    "unit_buyout_price": math.floor(buyoutPrice / itemCount),
                                    "duration_hours": 0,
                                })
                                
        yield faction, {
            "faction": faction,
            "scan_timestamp": ts,
            "zone": scan_entry.get("realm", "Unknown"),
            "listings": listings
        }


# ─── AHOracle Parser (Legacy) ────────────────────────────────────────────

def extract_ahoracle_scans(db: dict):
    scans = db.get("scans") or {}
    for faction in FACTIONS:
        scan = scans.get(faction)
        if not scan:
            continue

        ts = int(scan.get("scan_timestamp") or 0)
        if ts <= 0:
            continue

        listings = scan.get("listings") or []
        clean = []
        for l in listings:
            try:
                clean.append({
                    "item_id":           int(l["item_id"]),
                    "item_name":         l.get("item_name") or "",
                    "seller":            l.get("seller") or "Unknown",
                    "stack_size":        int(l["stack_size"]),
                    "unit_buyout_price": int(l["unit_buyout_price"]),
                    "duration_hours":    int(l.get("duration_hours") or 0),
                })
            except (KeyError, TypeError, ValueError):
                continue

        yield faction, {
            "faction":        faction,
            "scan_timestamp": ts,
            "zone":           scan.get("zone") or "Unknown",
            "listings":       clean,
        }