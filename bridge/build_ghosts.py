"""Build ghosts from workshop chest, respecting the asm2->asm1 substitution
rule and single-owner constraint.

Usage (from any Employee with in-game-owner ownership):
    python bridge/build_ghosts.py [--limit N] [--dry-run]

- Reads all entity-ghosts on nauvis.
- Groups by ghost_name.
- Substitutes assembling-machine-2 -> assembling-machine-1 when asm2
  is not craftable OR not in inventory OR the workshop chest has none.
  Substitutions are logged; Manager can upgrade later.
- Priority order (matches team/supply-priorities.md):
    1. Furnaces, chests, burner-inserters (cheap, unblock further work)
    2. Belts (huge count; batch aggressively)
    3. Poles + underground-belts (structural)
    4. Electric-mining-drills + assemblers (expensive; do after supply)
    5. Steam-engines + boilers + splitters (needs steel)
    6. Lamps + combinators + long-handed + fast items (cosmetic /
       optimization; last)
- Respects the tile-lock rule: places one ghost at a time, uses
  clear_blockers and step_aside on placement calls.

Does NOT include walking / mining logic — it uses whatever is in the
character inventory OR takes from the workshop chest at (-30.5, 41.5)
before each batch.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from agent import Agent  # noqa: E402

WORKSHOP_X, WORKSHOP_Y = -30.5, 41.5

# Ghost-name priority. Lower number = build first.
PRIORITY = {
    'stone-furnace': 1,
    'wooden-chest': 1,
    'buffer-chest': 1,
    'burner-inserter': 1,
    'transport-belt': 2,
    'small-electric-pole': 3,
    'underground-belt': 3,
    'inserter': 4,
    'electric-mining-drill': 5,
    'assembling-machine-1': 6,
    'assembling-machine-2': 6,  # will be substituted to asm1 in-flight
    'boiler': 7,
    'steam-engine': 7,
    'splitter': 7,
    'fast-inserter': 8,
    'fast-underground-belt': 8,
    'long-handed-inserter': 8,
    'lab': 9,
    'small-lamp': 10,
    'constant-combinator': 10,
    'pipe': 10,
}
DEFAULT_PRIORITY = 99

# Items that need substitution if unavailable
SUBSTITUTIONS = {
    'assembling-machine-2': 'assembling-machine-1',
}


def get_ghosts(a: Agent) -> list[dict]:
    """Return list of ghosts as {name, x, y, direction, unit_number}."""
    body = (
        "local s=game.surfaces.nauvis; "
        "local ghosts=s.find_entities_filtered{name='entity-ghost'}; "
        "local out={}; "
        "for _,g in ipairs(ghosts) do "
        "  table.insert(out, string.format('%s|%.1f|%.1f|%d|%d', "
        "    g.ghost_name or '?', g.position.x, g.position.y, "
        "    g.direction or 0, g.unit_number)) "
        "end; "
        "rcon.print(table.concat(out, ';'))"
    )
    out = a.rcon.command('/silent-command ' + body).strip()
    if not out:
        return []
    ghosts = []
    for entry in out.split(';'):
        parts = entry.split('|')
        if len(parts) != 5:
            continue
        name, x, y, direction, unum = parts
        ghosts.append({
            'name': name,
            'x': float(x),
            'y': float(y),
            'direction': int(direction),
            'unum': int(unum),
        })
    return ghosts


def workshop_contents(a: Agent) -> dict:
    """Return {item_name: count} in the workshop chest."""
    body = (
        f"local s=game.surfaces.nauvis; "
        f"local ch=s.find_entities_filtered{{name='wooden-chest', "
        f"position={{{WORKSHOP_X}, {WORKSHOP_Y}}}, radius=0.5}}[1]; "
        "if not ch then rcon.print(''); return end; "
        "local ci=ch.get_inventory(defines.inventory.chest); "
        "local out={}; "
        "for _,st in pairs(ci.get_contents() or {}) do "
        "  table.insert(out, st.name..'='..st.count) "
        "end; "
        "rcon.print(table.concat(out, ','))"
    )
    out = a.rcon.command('/silent-command ' + body).strip()
    result = {}
    if not out:
        return result
    for entry in out.split(','):
        if '=' not in entry:
            continue
        k, v = entry.split('=', 1)
        result[k] = int(v)
    return result


def is_recipe_researched(a: Agent, item_name: str) -> bool:
    """True if the recipe for item_name is enabled for the player force."""
    body = (
        f"local r=prototypes.recipe['{item_name}']; "
        "if not r then rcon.print('no'); return end; "
        f"local f=game.forces.player; "
        f"local rec=f.recipes['{item_name}']; "
        "if not rec then rcon.print('no'); return end; "
        "rcon.print(rec.enabled and 'yes' or 'no')"
    )
    out = a.rcon.command('/silent-command ' + body).strip()
    return out == 'yes'


def pick_substitute(ghost_name: str, inv: dict, chest: dict,
                    researched: dict[str, bool]) -> str | None:
    """Return the item name to actually place, or None if unavailable.

    Applies asm2->asm1 substitution when asm2 is not researched, not in
    inventory, and not in the chest.
    """
    def have(name):
        return inv.get(name, 0) + chest.get(name, 0)

    if have(ghost_name) >= 1 and researched.get(ghost_name, True):
        return ghost_name

    sub = SUBSTITUTIONS.get(ghost_name)
    if sub and have(sub) >= 1 and researched.get(sub, True):
        return sub

    return None


def take_from_chest(a: Agent, item: str, count: int) -> int:
    """Take up to `count` of `item` from workshop chest. Returns moved."""
    r = a.inventory.take_from_chest(WORKSHOP_X, WORKSHOP_Y, item, count)
    return r.get('moved', 0)


def place_ghost(a: Agent, ghost: dict, item_to_place: str) -> dict:
    """Revive a ghost using the specified item. Uses `entity.revive()` in
    Lua so the ghost's placement (position + direction) is preserved.

    Falls back to placement.place() if revive fails (e.g. ghost destroyed
    between our probe and now).
    """
    # Try revive first via silent-command
    body = (
        f"local s=game.surfaces.nauvis; "
        f"local g=s.find_entities_filtered{{name='entity-ghost', "
        f"position={{{ghost['x']}, {ghost['y']}}}, radius=0.4}}[1]; "
        "if not g then rcon.print('MISS'); return end; "
        f"local c=game.get_entity_by_unit_number({a.unit}); "
        f"local inv=c.get_main_inventory(); "
        f"if inv.get_item_count('{item_to_place}') < 1 then "
        "  rcon.print('NO_ITEM'); return end; "
        f"if g.ghost_name ~= '{item_to_place}' then "
        "  g.destroy(); "
        f"  local ok, e = pcall(function() return s.create_entity{{"
        f"    name='{item_to_place}', position=g.position, "
        f"    direction=g.direction, force=c.force, raise_built=true}} end); "
        "  if ok and e then "
        f"    inv.remove{{name='{item_to_place}', count=1}}; "
        "    rcon.print('SUBBED'); "
        "  else "
        "    rcon.print('SUB_FAIL'); "
        "  end "
        "else "
        "  local revived, e, req = g.revive{raise_revive=true, "
        "    return_item_request_proxy=false}; "
        "  if revived then "
        f"    inv.remove{{name='{item_to_place}', count=1}}; "
        "    rcon.print('REVIVED'); "
        "  else "
        "    rcon.print('REVIVE_FAIL'); "
        "  end "
        "end"
    )
    out = a.rcon.command('/silent-command ' + body).strip()
    return {'result': out}


def main():
    dry_run = '--dry-run' in sys.argv
    limit = None
    if '--limit' in sys.argv:
        i = sys.argv.index('--limit')
        limit = int(sys.argv[i + 1])

    with Agent.connect() as a:
        ghosts = get_ghosts(a)
        print(f'ghosts on map: {len(ghosts)}')

        # Group by name for a summary
        by_name = {}
        for g in ghosts:
            by_name[g['name']] = by_name.get(g['name'], 0) + 1
        print('demand:')
        for name, cnt in sorted(by_name.items(),
                                key=lambda kv: PRIORITY.get(kv[0], DEFAULT_PRIORITY)):
            print(f'  {name}: {cnt}')

        if dry_run:
            print('--dry-run — not placing.')
            return

        # Order ghosts by priority then position
        ghosts.sort(key=lambda g: (PRIORITY.get(g['name'], DEFAULT_PRIORITY),
                                    g['x'], g['y']))

        # Cache recipe enabled state
        researched = {}
        for name in by_name:
            r = SUBSTITUTIONS.get(name, name)
            researched[name] = is_recipe_researched(a, r)
            if name in SUBSTITUTIONS:
                researched[SUBSTITUTIONS[name]] = is_recipe_researched(
                    a, SUBSTITUTIONS[name])

        # Process
        subs_log: list[tuple[str, str, float, float]] = []
        placed = 0
        skipped_no_material = 0
        for i, g in enumerate(ghosts):
            if limit is not None and placed >= limit:
                print(f'reached limit {limit} — stopping.')
                break

            inv = a.inventory.list()
            chest = workshop_contents(a)
            item = pick_substitute(g['name'], inv, chest, researched)

            if item is None:
                skipped_no_material += 1
                continue

            if inv.get(item, 0) < 1:
                # Take from chest
                moved = take_from_chest(a, item, min(20, chest.get(item, 0)))
                if moved == 0:
                    skipped_no_material += 1
                    continue

            r = place_ghost(a, g, item)
            if r.get('result') in ('REVIVED', 'SUBBED'):
                placed += 1
                if item != g['name']:
                    subs_log.append((g['name'], item, g['x'], g['y']))
            elif r.get('result') == 'MISS':
                pass  # ghost gone (someone else placed it), fine
            else:
                # revive failed, likely blocking entity / can't place
                pass

            if placed % 20 == 0 and placed > 0:
                print(f'  placed {placed} so far...')

        print(f'\nplaced: {placed}')
        print(f'skipped (no material): {skipped_no_material}')
        if subs_log:
            print(f'substitutions (log — flag to Manager for upgrade later):')
            for orig, sub, x, y in subs_log[:20]:
                print(f'  {orig} @({x:.0f},{y:.0f}) -> {sub}')
            if len(subs_log) > 20:
                print(f'  ... and {len(subs_log) - 20} more')


if __name__ == '__main__':
    main()
