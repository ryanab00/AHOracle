# Contributing

## Ground rules

- **Never commit `.env`.** Rotate any credential that leaks.
- **Never hand-edit generated files** (`backend/api/recipes.json`,
  `backend/api/items.json`). Regenerate them.
- **Keep `items.json` small.** Adding one placeholder entry today becomes
  ten thousand tomorrow. See [Adding a recipe](#adding-a-recipe).

## Code style

### Python

- PEP 8, 4-space indent, single quotes for strings unless embedded in `{}`.
- Type hints on new functions (existing code is inconsistent — match the
  file you're editing).
- Prefer `pathlib.Path` over `os.path` for new code.
- No print statements in library code; use `logger` or return values.

### Lua (addon + profession data)

- The `backend/profession_data/` files are **auto-generated** — do not edit.
- The `Addon/AHOracle/` files are hand-written. 4-space indent, `local`
  every variable.

### Vue / JS

- `<script setup>` + Composition API (matches existing pages).
- Use the Pinia stores in `frontend/stores/` — don't call `fetch` directly
  from a page unless there's a reason (see `app.vue` for the one exception).
- Tailwind for styling; avoid new `<style>` blocks.

## Adding a recipe

If a curated recipe is missing from the dashboard, its entry in
`profession_data/core/<Profession>.lua` is probably absent.

1. Find the spell in `LibProfessionDB` upstream
   (see [its repo](https://github.com/…)). Get the `craftSpellID`.
2. If the spell exists in `core/<Profession>.lua` but not in
   `backend/api/recipes.json`, check `scripts/build_recipes.py` — the
   `PROFESSIONS` dict and `NAME_PREFIX_CATEGORY` may filter it out.
3. Otherwise, the source of truth (`profession_data/`) is stale. Regenerate
   it upstream (out of scope for this repo) or add the entry manually with
   a comment noting the origin.
4. Run `python scripts/build_recipes.py` and commit **only** the two JSONs
   (`recipes.json`, `items.json`).

**Do not add items to `items.json` by hand.** That file is populated from
the `craftedItemId` fields in the profession data plus a small `ITEM_NAMES`
fallback dict in `build_recipes.py`. If you need a specific vendor item in
the map, add it to `ITEM_NAMES` in the script — it'll survive regeneration.

## Adding an API endpoint

1. Add a function to `backend/api/routes.py` with `@router.get(...)`.
2. Add the corresponding type in `frontend/stores/<store>.js`
   (Pinia stores wrap all fetches — no direct calls from pages).
3. Add a page in `frontend/pages/` that consumes the store.
4. Document the endpoint in the docstring; the OpenAPI UI at
   `http://localhost:8000/docs` picks it up automatically.

## Adding a data migration

`backend/scripts/migrate.py` is intentionally minimal. If you need a real
migration:

1. Add the new column to `backend/ahoracle_etl/models.py`.
2. Add explicit `ALTER TABLE` / data-copy logic to `scripts/migrate.py` —
   do not add a generic migrator without discussion.
3. Update `backend/SCHEMA.md` with the new column.

## Pull requests

- One logical change per PR. A migration + a new endpoint + a frontend
  redesign should be three PRs.
- Include a screenshot for any UI change.
- If you touched the pipeline, include before/after numbers from
  `python etl.py inspect`.

## Reporting bugs

Include:

- What you ran (command + working directory).
- The last ~20 lines of output.
- `python etl.py inspect` output (redact your DB URL).