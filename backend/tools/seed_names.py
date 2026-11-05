import json
from pathlib import Path

ITEMS_FILE = Path(__file__).resolve().parent.parent / "ahoracle" / "api" / "items.json"

SEED = {
    12359: "Thorium Bar", 12360: "Arcanite Bar", 12361: "Blue Sapphire", 12363: "Arcane Crystal", 12364: "Huge Emerald", 12365: "Dense Stone",
    3575: "Iron Bar", 3576: "Tin Bar", 3577: "Gold Bar", 3859: "Steel Bar", 3860: "Mithril Bar", 6037: "Truesilver Bar", 11371: "Dark Iron Bar",
    7911: "Truesilver Ore", 10620: "Thorium Ore", 11370: "Dark Iron Ore", 2770: "Copper Ore", 2771: "Tin Ore", 2772: "Iron Ore", 2775: "Silver Ore", 2776: "Gold Ore", 3858: "Mithril Ore",
    8150: "Deeprock Salt", 8151: "Flask of Mojo", 8152: "Flask of Big Mojo", 8153: "Wildvine", 8165: "Worn Dragonscale", 8167: "Turtle Scale", 8168: "Jet Black Feather", 8169: "Thick Hide", 8170: "Rugged Leather", 8171: "Rugged Hide", 8172: "Cured Thick Hide", 8343: "Heavy Silken Thread",
    13463: "Dreamfoil", 13464: "Golden Sansam", 13465: "Mountain Silversage", 13466: "Plaguebloom", 13467: "Icecap", 13468: "Black Lotus",
    8831: "Purple Lotus", 8836: "Arthas' Tears", 8838: "Sungrass", 8839: "Blindweed", 8845: "Ghost Mushroom", 8846: "Gromsblood",
    2450: "Briarthorn", 2452: "Swiftthistle", 2453: "Bruiseweed", 3355: "Wild Steelbloom", 3356: "Kingsblood", 3357: "Liferoot", 3358: "Khadgar's Whisker", 3369: "Grave Moss", 3818: "Fadeleaf", 3819: "Dragon's Teeth", 3820: "Stranglekelp", 3821: "Goldthorn", 4625: "Firebloom",
    6370: "Blackmouth Oil", 6371: "Fire Oil", 8925: "Crystal Vial", 13423: "Stonescale Oil", 13422: "Stonescale Eel",
    3371: "Crystal Vial", 3372: "Leaded Vial",
    7067: "Elemental Earth", 7068: "Elemental Fire", 7069: "Elemental Air", 7070: "Elemental Water", 7075: "Core of Earth", 7076: "Essence of Earth", 7077: "Heart of Fire", 7078: "Essence of Fire", 7079: "Globe of Water", 7080: "Essence of Water", 7081: "Breath of Wind", 7082: "Essence of Air",
    12803: "Living Essence", 12804: "Powerful Mojo", 12808: "Essence of Undeath", 12809: "Guardian Stone", 12810: "Enchanted Leather", 12811: "Righteous Orb",
    10938: "Lesser Magic Essence", 10939: "Greater Magic Essence", 10940: "Strange Dust", 10978: "Small Glimmering Shard", 10998: "Lesser Astral Essence", 11082: "Greater Astral Essence", 11083: "Soul Dust", 11084: "Large Glimmering Shard", 11134: "Lesser Mystic Essence", 11135: "Greater Mystic Essence", 11137: "Vision Dust", 11138: "Small Glowing Shard", 11139: "Large Glowing Shard", 11174: "Lesser Nether Essence", 11175: "Greater Nether Essence", 11176: "Dream Dust", 11177: "Small Radiant Shard", 11178: "Large Radiant Shard",
    14341: "Rune Thread", 14342: "Mooncloth", 14343: "Small Brilliant Shard", 14344: "Large Brilliant Shard",
    17010: "Fiery Core", 17011: "Lava Core", 17012: "Core Leather", 17056: "Essence of Water",
    7071: "Iron Buckle", 7072: "Elemental Air", 7073: "Elemental Fire", 7074: "Elemental Earth",
    13452: "Elixir of the Mongoose", 13453: "Elixir of Brute Force", 13454: "Greater Arcane Elixir", 13455: "Greater Stoneshield Potion", 13456: "Greater Frost Protection Potion", 13457: "Greater Fire Protection Potion", 13458: "Greater Nature Protection Potion", 13459: "Greater Shadow Protection Potion", 13460: "Greater Holy Protection Potion", 13461: "Greater Arcane Protection Potion", 13462: "Purification Potion", 13463: "Dreamfoil", 13464: "Golden Sansam", 13465: "Mountain Silversage", 13466: "Plaguebloom", 13467: "Icecap", 13468: "Black Lotus",
    20002: "Greater Dreamless Sleep Potion", 20004: "Major Troll's Blood Potion", 20007: "Mageblood Potion", 20008: "Living Action Potion",
    21546: "Elixir of Greater Firepower"
}

def main():
    existing = {}
    if ITEMS_FILE.exists():
        existing = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    
    for k, v in SEED.items():
        existing[str(k)] = v

    ITEMS_FILE.write_text(json.dumps(dict(sorted(existing.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(SEED)} names into items.json")

if __name__ == "__main__":
    main()