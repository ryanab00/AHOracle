import json
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "api" / "recipes.json"

RECIPES = [
    # ─── Flasks ───
    {"category": "Flasks", "name": "Flask of the Titans", "reagents": {"Gromsblood": 30, "Stonescale Oil": 10, "Black Lotus": 1, "Crystal Vial": 1}},
    {"category": "Flasks", "name": "Flask of Supreme Power", "reagents": {"Dreamfoil": 30, "Mountain Silversage": 10, "Black Lotus": 1, "Crystal Vial": 1}},
    {"category": "Flasks", "name": "Flask of Distilled Wisdom", "reagents": {"Dreamfoil": 30, "Icecap": 10, "Black Lotus": 1, "Crystal Vial": 1}},
    {"category": "Flasks", "name": "Flask of Chromatic Resistance", "reagents": {"Icecap": 30, "Mountain Silversage": 10, "Black Lotus": 1, "Crystal Vial": 1}},
    {"category": "Flasks", "name": "Flask of Petrification", "reagents": {"Stonescale Oil": 30, "Mountain Silversage": 10, "Black Lotus": 1, "Crystal Vial": 1}},

    # ─── Protection Potions ───
    {"category": "Protection Potions", "name": "Greater Fire Protection Potion", "reagents": {"Firebloom": 1, "Dreamfoil": 1, "Crystal Vial": 1}},
    {"category": "Protection Potions", "name": "Greater Frost Protection Potion", "reagents": {"Dreamfoil": 1, "Crystal Vial": 1}},
    {"category": "Protection Potions", "name": "Greater Nature Protection Potion", "reagents": {"Elemental Earth": 1, "Dreamfoil": 1, "Crystal Vial": 1}},
    {"category": "Protection Potions", "name": "Greater Shadow Protection Potion", "reagents": {"Shadow Oil": 1, "Dreamfoil": 1, "Crystal Vial": 1}},
    {"category": "Protection Potions", "name": "Greater Arcane Protection Potion", "reagents": {"Dreamfoil": 1, "Dream Dust": 1, "Crystal Vial": 1}},

    # ─── Elixirs ───
    {"category": "Elixirs", "name": "Elixir of the Mongoose", "reagents": {"Mountain Silversage": 2, "Plaguebloom": 2, "Crystal Vial": 1}},
    {"category": "Elixirs", "name": "Elixir of Superior Defense", "reagents": {"Stonescale Oil": 2, "Sungrass": 1, "Crystal Vial": 1}},
    {"category": "Elixirs", "name": "Elixir of Fortitude", "reagents": {"Wild Steelbloom": 1, "Goldthorn": 1, "Leaded Vial": 1}},
    {"category": "Elixirs", "name": "Elixir of Greater Firepower", "reagents": {"Firefin Snapper": 6, "Firebloom": 3, "Crystal Vial": 1}},
    {"category": "Elixirs", "name": "Mageblood Potion", "reagents": {"Dreamfoil": 2, "Plaguebloom": 2, "Crystal Vial": 1}},
    {"category": "Elixirs", "name": "Elixir of Greater Agility", "reagents": {"Sungrass": 1, "Goldthorn": 1, "Crystal Vial": 1}},

    # ─── Oils / Alchemy Intermediates ───
    {"category": "Oils", "name": "Stonescale Oil", "reagents": {"Stonescale Eel": 1, "Leaded Vial": 1}},
    {"category": "Oils", "name": "Shadow Oil", "reagents": {"Fadeleaf": 4, "Grave Moss": 4, "Leaded Vial": 1}},
    {"category": "Oils", "name": "Blackmouth Oil", "reagents": {"Oily Blackmouth": 1, "Leaded Vial": 1}},

    # ─── Weapon Imbues ───
    {"category": "Weapon Imbues", "name": "Elemental Sharpening Stone", "reagents": {"Elemental Earth": 2, "Dense Stone": 3}},
    {"category": "Weapon Imbues", "name": "Brilliant Wizard Oil", "reagents": {"Large Brilliant Shard": 2, "Firebloom": 3}},
    {"category": "Weapon Imbues", "name": "Brilliant Mana Oil", "reagents": {"Large Brilliant Shard": 2, "Purple Lotus": 3}},

    # ─── Safety / Utility ───
    {"category": "Safety", "name": "Free Action Potion", "reagents": {"Blackmouth Oil": 2, "Stranglekelp": 1, "Crystal Vial": 1}},
    {"category": "Safety", "name": "Limited Invulnerability Potion", "reagents": {"Blindweed": 2, "Ghost Mushroom": 1, "Crystal Vial": 1}},
    {"category": "Safety", "name": "Greater Stoneshield Potion", "reagents": {"Stonescale Oil": 3, "Thorium Ore": 1}},
    {"category": "Safety", "name": "Mighty Rage Potion", "reagents": {"Gromsblood": 3, "Crystal Vial": 1}},
    {"category": "Safety", "name": "Major Troll's Blood Potion", "reagents": {"Gromsblood": 1, "Plaguebloom": 2}},

    # ─── Engineering ───
    {"category": "Engineering", "name": "Masterwork Target Dummy", "reagents": {"Mithril Casing": 1, "Thorium Tube": 1, "Thorium Widget": 2, "Truesilver Bar": 1, "Rugged Leather": 2, "Runecloth": 4}},
    {"category": "Engineering", "name": "Advanced Target Dummy", "reagents": {"Iron Strut": 1, "Bronze Framework": 1, "Gyrochronatom": 1, "Heavy Leather": 4}},
    {"category": "Engineering", "name": "Iron Grenade", "reagents": {"Iron Bar": 1, "Heavy Blasting Powder": 1, "Silk Cloth": 1}},
    {"category": "Engineering", "name": "Goblin Sapper Charge", "reagents": {"Mageweave Cloth": 1, "Solid Blasting Powder": 1, "Firebloom": 1}},
    
    # ─── Smelting & Engineering Intermediates ───
    {"category": "Smelting", "name": "Iron Bar", "reagents": {"Iron Ore": 1}},
    {"category": "Smelting", "name": "Thorium Bar", "reagents": {"Thorium Ore": 1}},
    {"category": "Smelting", "name": "Mithril Bar", "reagents": {"Mithril Ore": 1}},
    {"category": "Smelting", "name": "Truesilver Bar", "reagents": {"Truesilver Ore": 1}},
    {"category": "Smelting", "name": "Copper Bar", "reagents": {"Copper Ore": 1}},
    {"category": "Smelting", "name": "Tin Bar", "reagents": {"Tin Ore": 1}},
    {"category": "Smelting", "name": "Bronze Bar", "reagents": {"Copper Bar": 1, "Tin Bar": 1}},
    {"category": "Smelting", "name": "Gold Bar", "reagents": {"Gold Ore": 1}},

    {"category": "Engineering Parts", "name": "Solid Blasting Powder", "reagents": {"Solid Stone": 2}},
    {"category": "Engineering Parts", "name": "Heavy Blasting Powder", "reagents": {"Heavy Stone": 1}},
    {"category": "Engineering Parts", "name": "Thorium Tube", "reagents": {"Thorium Bar": 6}},
    {"category": "Engineering Parts", "name": "Mithril Casing", "reagents": {"Mithril Bar": 3}},
    {"category": "Engineering Parts", "name": "Thorium Widget", "reagents": {"Thorium Bar": 3, "Runecloth": 1}},
    {"category": "Engineering Parts", "name": "Iron Strut", "reagents": {"Iron Bar": 2}},
    {"category": "Engineering Parts", "name": "Bronze Framework", "reagents": {"Bronze Bar": 2, "Medium Leather": 1}},
    {"category": "Engineering Parts", "name": "Gold Power Core", "reagents": {"Gold Bar": 1, "Greater Magic Essence": 1}},
    {"category": "Engineering Parts", "name": "Gyrochronatom", "reagents": {"Iron Bar": 1, "Gold Power Core": 1}},

    # ─── Food ───
    {"category": "Food", "name": "Dirge's Kickin' Chimaerok Chops", "reagents": {"Chimaerok Tenderloin": 1, "Deeprock Salt": 1}},
    {"category": "Food", "name": "Smoked Desert Dumplings", "reagents": {"Sandworm Meat": 1, "Soothing Spices": 1}},
    {"category": "Food", "name": "Runn Tum Tuber Surprise", "reagents": {"Runn Tum Tuber": 1, "Soothing Spices": 1}}
]

recipe_index = {r["name"]: r for r in RECIPES}

def validate():
    """Report reagents that aren't defined AND aren't known raw materials."""
    missing = set()
    for r in RECIPES:
        for reagent in r["reagents"]:
            if reagent not in recipe_index:
                missing.add(reagent)
    return sorted(missing)

def expand(name, crafts=1, _stack=None):
    """Recursively flatten a recipe to raw materials for N crafts."""
    if _stack is None: _stack = set()
    if name in _stack:
        raise ValueError(f"Cycle: {name}")
    if name not in recipe_index:
        return {name: crafts}
    _stack.add(name)
    out = {}
    for reagent, qty in recipe_index[name]["reagents"].items():
        for k, v in expand(reagent, qty * crafts, _stack).items():
            out[k] = out.get(k, 0) + v
    _stack.remove(name)
    return out

# per single output unit:
def expand_per_unit(name):
    r = recipe_index[name]
    total = expand(name, 1)
    return {k: v / r.get("output_qty", 1) for k, v in total.items()}