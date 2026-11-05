import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
CORE_DIR = BACKEND / "data" / "professions" / "core"
NAMES_DIR = BACKEND / "data" / "professions" / "names"
OUT_RECIPES = BACKEND / "ahoracle" / "api" / "recipes.json"
OUT_ITEMS = BACKEND / "ahoracle" / "api" / "items.json"

PROFESSIONS = {171: "Alchemy", 185: "Cooking", 202: "Engineering", 333: "Enchanting", 164: "Blacksmithing"}
FILE_NAMES = {171: "Alchemy.lua", 185: "Cooking.lua", 202: "Engineering.lua", 333: "Enchanting.lua", 164: "Blacksmithing.lua"}

def _extract_block(text: str, opener_re: str) -> str | None:
    m = re.search(opener_re, text)
    if not m: return None
    start = text.find('{', m.start())
    depth, i = 1, start + 1
    while i < len(text) and depth > 0:
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        i += 1
    return text[start:i]

def parse_core(text: str, skill_line: int) -> dict[int, dict]:
    block = _extract_block(text, rf'lib:LoadCore\(\s*{skill_line}\s*,\s*\{{')
    if not block: return {}
    out = {}
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{', block):
        spell_id = int(m.group(1))
        start = m.end() - 1
        depth, i = 1, start + 1
        while i < len(block) and depth > 0:
            if block[i] == '{': depth += 1
            elif block[i] == '}': depth -= 1
            i += 1
        entry = block[start+1:i]
        mc = re.search(r'\["craftedItemId"\]\s*=\s*(\d+)', entry)
        mr = re.search(r'\["reagents"\]\s*=\s*\{([^}]*)\}', entry)
        reagents = {}
        if mr:
            for rm in re.finditer(r'\[(\d+)\]\s*=\s*(\d+)', mr.group(1)):
                reagents[int(rm.group(1))] = int(rm.group(2))
        if mc:
            out[spell_id] = {"crafted_item_id": int(mc.group(1)), "reagents": reagents}
    return out

def parse_names(text: str, skill_line: int) -> dict[int, str]:
    block = _extract_block(text, rf'lib:LoadNames\(\s*{skill_line}\s*,\s*\{{')
    if not block: return {}
    out = {}
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{[^}]*?\["name"\]\s*=\s*"([^"]+)"', block, re.DOTALL):
        out[int(m.group(1))] = m.group(2)
    return out

def main() -> None:
    recipes = []
    items_needed: set[int] = set()

    for skill_line, prof in PROFESSIONS.items():
        fname = FILE_NAMES[skill_line]
        core_file = CORE_DIR / fname
        names_file = NAMES_DIR / fname
        if not core_file.exists(): continue

        core = parse_core(core_file.read_text(encoding="utf-8"), skill_line)
        names = parse_names(names_file.read_text(encoding="utf-8"), skill_line)

        for spell_id, data in core.items():
            output_id = data["crafted_item_id"]
            if output_id == 0: continue # Skip non-item spells
            
            output_name = names.get(spell_id, f"Item #{output_id}")
            reagents = {str(k): v for k, v in data["reagents"].items()}

            items_needed.add(output_id)
            items_needed.update(int(k) for k in reagents)

            recipes.append({
                "spell_id": spell_id,
                "profession": prof,
                "category": "Other", # We'll rely on the profession tab for now
                "name": output_name,
                "output_item_id": output_id,
                "output_quantity": 1,
                "reagents": reagents,
            })

    recipes.sort(key=lambda r: (r["profession"], r["name"]))
    OUT_RECIPES.write_text(json.dumps(recipes, indent=2) + "\n", encoding="utf-8")

    existing = {}
    if OUT_ITEMS.exists():
        existing = json.loads(OUT_ITEMS.read_text(encoding="utf-8"))
    for iid in sorted(items_needed):
        existing.setdefault(str(iid), f"Item #{iid}")
    OUT_ITEMS.write_text(json.dumps(dict(sorted(existing.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(recipes)} recipes to {OUT_RECIPES}")