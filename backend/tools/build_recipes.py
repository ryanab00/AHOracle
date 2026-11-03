"""build_recipes.py — offline, ID-normalized recipes."""
import json
import re
from pathlib import Path
from collections import Counter

HERE         = Path(__file__).resolve().parent
DATA_DIR     = HERE.parent / "profession_data"
CORE_DIR     = DATA_DIR / "core"
NAMES_DIR    = DATA_DIR / "names"
RECIPES_FILE = HERE.parent / "api" / "recipes.json"
ITEMS_FILE   = HERE.parent / "api" / "items.json"

PROFESSIONS = {
    "Alchemy.lua":        ("Alchemy",        171),
    "Blacksmithing.lua":  ("Blacksmithing",  164),
    "Cooking.lua":        ("Cooking",        185),
    "Enchanting.lua":     ("Enchanting",     333),
    "Engineering.lua":    ("Engineering",    202),
    "Firstaid.lua":       ("First Aid",      129),
    "Fishing.lua":        ("Fishing",        356),
    "Leatherworking.lua": ("Leatherworking", 165),
    "Mining.lua":         ("Mining",         186),
    "Tailoring.lua":      ("Tailoring",      197),
}

SPELL_NAME_OVERRIDES = {
    2657: "Smelt Copper",   2658: "Smelt Silver",   2659: "Smelt Bronze",
    3304: "Smelt Tin",      3307: "Smelt Iron",     3308: "Smelt Gold",
    3569: "Smelt Steel",    10097: "Smelt Mithril", 10098: "Smelt Truesilver",
    14891: "Smelt Dark Iron", 16153: "Smelt Thorium", 22967: "Smelt Elementium",
    1213638: "Smelt Obsidian-Infused Thorium Bar",
}

NAME_PREFIX_CATEGORY = {
    "Mining": [("Smelt ", "Smelting")],
}

# Hand-coded reagent names for local fallback
ITEM_NAMES = {
    3371: "Crystal Vial", 3372: "Leaded Vial", 8925: "Crystal Vial", 16583: "Crystal Vial",
    765: "Silverleaf", 785: "Mageroyal", 2447: "Peacebloom", 2449: "Earthroot",
    2450: "Briarthorn", 2452: "Swiftthistle", 2453: "Bruiseweed", 3355: "Wild Steelbloom",
    3356: "Kingsblood", 3357: "Liferoot", 3358: "Khadgar's Whisker", 3369: "Grave Moss",
    3818: "Fadeleaf", 3819: "Dragon's Teeth", 3820: "Stranglekelp", 3821: "Goldthorn",
    4625: "Firebloom", 8831: "Purple Lotus", 8836: "Arthas' Tears", 8838: "Sungrass",
    8839: "Blindweed", 8845: "Ghost Mushroom", 8846: "Gromsblood", 13463: "Dreamfoil",
    13464: "Golden Sansam", 13465: "Mountain Silversage", 13466: "Plaguebloom",
    13467: "Icecap", 13468: "Black Lotus", 13422: "Stonescale Eel",
    2770: "Copper Ore", 2771: "Tin Ore", 2772: "Iron Ore", 2775: "Silver Ore",
    2776: "Gold Ore", 3858: "Mithril Ore", 7911: "Truesilver Ore", 10620: "Thorium Ore",
    11370: "Dark Iron Ore", 2589: "Linen Cloth", 2592: "Wool Cloth", 4306: "Silk Cloth",
    4338: "Mageweave Cloth", 14047: "Runecloth", 14341: "Rune Thread",
    2318: "Light Leather", 2319: "Medium Leather", 4234: "Heavy Leather", 4304: "Thick Leather",
    8170: "Rugged Leather", 15407: "Cured Rugged Hide", 15408: "Heavy Scorpid Scale",
    15412: "Green Dragonscale", 15414: "Red Dragonscale", 15415: "Blue Dragonscale",
    15416: "Black Dragonscale", 15417: "Devilsaur Leather", 15419: "Warbear Leather",
    15420: "Ironfeather", 15422: "Frostsaber Leather", 15423: "Chimera Leather",
    10938: "Lesser Magic Essence", 10939: "Greater Magic Essence", 10940: "Strange Dust",
    10978: "Small Glimmering Shard", 10998: "Lesser Astral Essence", 11082: "Greater Astral Essence",
    11083: "Soul Dust", 11084: "Large Glimmering Shard", 11134: "Lesser Mystic Essence",
    11135: "Greater Mystic Essence", 11137: "Vision Dust", 11138: "Small Glowing Shard",
    11139: "Large Glowing Shard", 11174: "Lesser Nether Essence", 11175: "Greater Nether Essence",
    11176: "Dream Dust", 11177: "Small Radiant Shard", 11178: "Large Radiant Shard",
    14343: "Small Brilliant Shard", 14344: "Large Brilliant Shard", 16202: "Lesser Eternal Essence",
    16203: "Greater Eternal Essence", 16204: "Illusion Dust", 20725: "Nexus Crystal",
    7067: "Elemental Earth", 7068: "Elemental Fire", 7069: "Elemental Air", 7070: "Elemental Water",
    7075: "Core of Earth", 7076: "Essence of Earth", 7077: "Heart of Fire", 7078: "Essence of Fire",
    7079: "Globe of Water", 7080: "Essence of Water", 7081: "Breath of Wind", 7082: "Essence of Air",
    7072: "Elemental Air", 12803: "Living Essence", 12804: "Powerful Mojo", 12808: "Essence of Undeath",
    12809: "Guardian Stone", 12811: "Righteous Orb", 12363: "Arcane Crystal", 12364: "Huge Emerald",
    12799: "Large Opal", 12800: "Azerothian Diamond", 14342: "Mooncloth", 17010: "Fiery Core",
    17011: "Lava Core", 17012: "Core Leather", 17202: "Snowball", 18512: "Larvae of the Plague",
    20381: "Dreamscale", 20520: "Dark Rune", 7972: "Ichor of Undeath", 10285: "Shadow Silk",
    10286: "Heart of the Wild", 12607: "Brilliant Chromatic Scale", 12938: "Blood of Heroes",
    18562: "Elementium Ore",
}

def _extract_block(text: str, opener_re: str) -> str | None:
    """Finds the opening brace and correctly balances nested tables."""
    m = re.search(opener_re, text)
    if not m:
        return None
    
    start = text.find('{', m.start())
    if start == -1:
        return None
        
    depth = 1
    i = start + 1
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start+1:i]
        i += 1
    return None

def parse_lua_names(text: str, skill_line: int) -> dict[int, str]:
    block = _extract_block(text, rf'lib:LoadNames\(\s*{skill_line}\s*,\s*\{{')
    if not block: return {}
    out = {}
    # Robust regex to grab the name
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{[^\}]*?\["name"\]\s*=\s*"([^"]+)"', block, re.DOTALL):
        sid = int(m.group(1))
        out[sid] = m.group(2)
    return out

def parse_lua_core(text: str, skill_line: int) -> dict[int, dict]:
    block = _extract_block(text, rf'lib:LoadCore\(\s*{skill_line}\s*,\s*\{{')
    if not block: return {}
    out, i, n = {}, 0, len(block)
    
    while i < n:
        m = re.compile(r'\[(\d+)\]\s*=\s*\{').search(block, i)
        if not m: break
        
        sid = int(m.group(1))
        start = m.end() - 1
        depth = 1
        j = start + 1
        
        # Balance nested tables (difficulty, reagents)
        while j < n:
            if block[j] == '{': depth += 1
            elif block[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        
        entry = block[start+1:j]
        i = j + 1

        mc = re.search(r'\["craftedItemId"\]\s*=\s*(\d+)', entry)
        crafted = int(mc.group(1)) if mc else None

        reagents = {}
        mr = re.search(r'\["reagents"\]\s*=\s*\{([^}]*)\}', entry)
        if mr:
            for rr in re.finditer(r'\[(\d+)\]\s*=\s*(\d+)', mr.group(1)):
                iid, qty = int(rr.group(1)), int(rr.group(2))
                if qty > 0: reagents[iid] = qty

        out[sid] = {"crafted_item_id": crafted, "reagents": reagents or None}
    return out

def categorize(profession: str, name: str) -> str:
    for prefix, cat in NAME_PREFIX_CATEGORY.get(profession, []):
        if name.startswith(prefix): return cat
    return profession

def main() -> None:
    items: dict[int, str] = dict(ITEM_NAMES)
    recipes: list[dict] = []
    missing: set[int] = set()

    print("Parsing profession files (offline):")
    
    if not CORE_DIR.exists():
        print(f"ERROR: Core directory not found at {CORE_DIR}")
        return

    for filename, (profession, skill_line) in PROFESSIONS.items():
        core_path  = CORE_DIR  / filename
        names_path = NAMES_DIR / filename

        if not core_path.exists():
            print(f"  {filename:24} MISSING core file — skip")
            continue

        core_text = core_path.read_text(encoding="utf-8")
        core  = parse_lua_core(core_text, skill_line)
        
        names = {}
        if names_path.exists():
            names = parse_lua_names(names_path.read_text(encoding="utf-8"), skill_line)

        # First pass: fill in crafted item names
        for sid, data in core.items():
            cid = data.get("crafted_item_id")
            if not cid or cid in items: continue
            if sid in SPELL_NAME_OVERRIDES: items[cid] = SPELL_NAME_OVERRIDES[sid]
            elif sid in names: items[cid] = names[sid]

        # Second pass: emit recipes
        with_r, no_r, no_out = 0, 0, 0
        for sid, data in core.items():
            cid = data.get("crafted_item_id")
            if not cid:
                no_out += 1
                continue

            recipe_name = (
                names.get(sid)
                or SPELL_NAME_OVERRIDES.get(sid)
                or items.get(cid, f"Item #{cid}")
            )

            entry = {
                "category":       categorize(profession, recipe_name),
                "name":           recipe_name,
                "spell_id":       sid,
                "output_item_id": cid,
                "reagents":       (
                    {str(iid): qty for iid, qty in data["reagents"].items()}
                    if data.get("reagents") else None
                ),
            }

            if entry["reagents"]:
                for iid_str in entry["reagents"]:
                    iid = int(iid_str)
                    if iid not in items:
                        missing.add(iid)
                with_r += 1
            else:
                no_r += 1

            recipes.append(entry)

        print(f"  {filename:24} {with_r + no_r:4} recipes  ({with_r} priced, {no_out} non-item)")

    # Finalize files
    for r in recipes:
        cid = r["output_item_id"]
        if cid not in items: items[cid] = f"Item #{cid}"
    for mid in missing:
        items[mid] = f"Item #{mid}"

    recipes.sort(key=lambda r: (r["category"], r["name"]))
    RECIPES_FILE.write_text(json.dumps(recipes, indent=2) + "\n")
    ITEMS_FILE.write_text(json.dumps({str(k): v for k, v in sorted(items.items())}, indent=2) + "\n")

    cats = Counter(r["category"] for r in recipes)
    print(f"\nWrote {len(recipes)} recipes → {RECIPES_FILE.name}")
    print(f"Wrote {len(items)} item names → {ITEMS_FILE.name}")
    print(f"\nPer category:")
    for cat, n in sorted(cats.items()):
        print(f"  {cat:25} {n:4}")

if __name__ == "__main__":
    main()