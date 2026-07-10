"""Entity placement with auto-snap, blocker clearing, character-self-collision avoidance."""
from __future__ import annotations
from typing import Optional, Tuple

from agent.geometry import snap_2x2_center, snap_1x1_center


# Ghost item substitutions applied when reviving ghosts: if the ghost's own
# item isn't in the character inventory, build it with the fallback item
# instead. asm2 ghosts get built as asm1 when only asm1 is on hand (Manager
# upgrades later). Mirrors bridge/build_ghosts.py SUBSTITUTIONS.
_GHOST_SUBSTITUTIONS = {
    'assembling-machine-2': 'assembling-machine-1',
}


def _subs_lua() -> str:
    """Lua table literal for the ghost substitution map."""
    pairs = ",".join(f"['{k}']='{v}'" for k, v in _GHOST_SUBSTITUTIONS.items())
    return "{" + pairs + "}"


# Which target snap to use for each entity name. Defaults to 1x1 if unknown.
_ENTITY_SNAP = {
    'burner-mining-drill': '2x2',
    'electric-mining-drill': '2x2',
    'stone-furnace': '2x2',
    'steel-furnace': '2x2',
    'assembling-machine-1': '3x3',
    'assembling-machine-2': '3x3',
    'assembling-machine-3': '3x3',
}


class Placement:
    def __init__(self, agent):
        self.a = agent

    def _snap(self, item: str, x: float, y: float) -> Tuple[float, float]:
        kind = _ENTITY_SNAP.get(item, '1x1')
        if kind == '2x2':
            return snap_2x2_center(x, y)
        if kind == '3x3':
            return (round(x), round(y))  # 3x3 also snaps to integer center
        return snap_1x1_center(x, y)

    def place(self, item: str, x: float, y: float, direction: int = 0,
              clear_blockers: bool = True, step_aside: bool = True,
              mine_resources: bool = False) -> dict:
        """Place an entity, returning the place_entity result dict.
        If `clear_blockers`, removes trees/rocks at the snapped center first.
        If `step_aside`, walks the character off the spot if it's in the way.
        If `mine_resources`, mines any resource tiles (iron-ore, copper-ore, coal, stone)
            in the entity's bbox first — needed when placing entities on dense ore patches.
            Off by default because most placements shouldn't destroy resources accidentally.
            Mined ore goes into the character's inventory.
        """
        sx, sy = self._snap(item, x, y)
        if step_aside:
            cx, cy = self.a.position()
            kind = _ENTITY_SNAP.get(item, '1x1')
            tile_extent = 1.0 if kind == '2x2' else (1.5 if kind == '3x3' else 0.5)
            dx, dy = cx - sx, cy - sy
            if abs(dx) < tile_extent + 0.5 and abs(dy) < tile_extent + 0.5:
                self.a.movement.step_aside(tile_extent + 1.5)
        if clear_blockers:
            self._clear_blockers(sx, sy, kind=_ENTITY_SNAP.get(item, '1x1'))
        if mine_resources:
            self._mine_resources(sx, sy, kind=_ENTITY_SNAP.get(item, '1x1'))
        res = self.a.call('place_entity', self.a.unit, item, sx, sy, direction)
        return res

    def _clear_blockers(self, cx: float, cy: float, kind: str = '1x1'):
        """Destroy trees + rocks (simple-entity), pick up item-on-ground in the bbox.
        Items get inserted into character inventory (free loot).
        """
        half = {'1x1': 0.5, '2x2': 1.0, '3x3': 1.5}.get(kind, 0.5)
        body = (
            f"local c = game.get_entity_by_unit_number({self.a.unit}); "
            f"local s = game.surfaces['nauvis']; "
            f"local ci = c.get_main_inventory(); "
            f"local b = s.find_entities_filtered{{area={{{{{cx-half}, {cy-half}}}, "
            f"{{{cx+half}, {cy+half}}}}}}}; "
            "for _, e in ipairs(b) do "
            "  if e.valid then "
            "    if e.type == 'tree' or e.type == 'simple-entity' then "
            "      e.destroy() "
            "    elseif e.name == 'item-on-ground' and e.stack and e.stack.valid_for_read then "
            "      ci.insert{name=e.stack.name, count=e.stack.count}; "
            "      e.destroy() "
            "    end "
            "  end "
            "end"
        )
        self.a.rcon.command('/silent-command ' + body)

    def _mine_resources(self, cx: float, cy: float, kind: str = '2x2'):
        """Mine ore/coal/stone resource tiles in the bbox; ore goes to character inv.
        Needed when placing entities (furnace, asm) inside a dense ore patch.
        Resources are mineable_properties.minable but type='resource', not 'tree'.

        Decrement-safe (mirrors the control.lua 0.10.4 hand-mine fix): each
        resource entity carries an `amount` (ore remaining in the tile). We mine
        ONE unit — insert its products and decrement `amount` — and only
        `destroy()` the entity when it is down to its last unit (amount <= 1).
        The old code called `e.destroy()` unconditionally, wiping a whole ore
        tile (thousands of ore) per placement."""
        half = {'1x1': 0.5, '2x2': 1.0, '3x3': 1.5}.get(kind, 1.0)
        body = (
            f"local c = game.get_entity_by_unit_number({self.a.unit}); "
            f"local s = c.surface; local ci = c.get_main_inventory(); "
            f"local b = s.find_entities_filtered{{area={{{{{cx-half}, {cy-half}}}, "
            f"{{{cx+half}, {cy+half}}}}}, type='resource'}}; "
            "for _, e in ipairs(b) do "
            "  if e.valid and e.prototype.mineable_properties.products then "
            "    for _, p in ipairs(e.prototype.mineable_properties.products) do "
            "      local amt = p.amount or 1; "
            "      ci.insert{name=p.name, count=amt} "
            "    end; "
            "    if e.amount and e.amount > 1 then "
            "      e.amount = e.amount - 1 "
            "    else "
            "      e.destroy() "
            "    end "
            "  end "
            "end"
        )
        self.a.rcon.command('/silent-command ' + body)

    def take_back(self, item: str, x: float, y: float) -> bool:
        """Mine an entity and return its name + inventory contents to character.
        Bypasses reach checks for large entities like crash-site-spaceship."""
        # Convention: Factorio 2.0 get_contents() returns an ARRAY of
        # {name, count, quality} records (not a name->count map), so ipairs +
        # st.name/st.count is the correct iteration below.
        body = (
            f"local c = game.get_entity_by_unit_number({self.a.unit}); "
            f"local s = c.surface; local ci = c.get_main_inventory(); "
            f"local e = s.find_entities_filtered{{position={{{x}, {y}}}, "
            f"radius=1.5, name='{item}'}}[1]; "
            "if not e then rcon.print('MISS'); return end; "
            "local fi = e.get_fuel_inventory(); "
            "if fi then for _, st in ipairs(fi.get_contents()) do "
            "  ci.insert{name=st.name, count=st.count} end end; "
            "local chinv = e.get_inventory(defines.inventory.chest); "
            "if chinv then for _, st in ipairs(chinv.get_contents()) do "
            "  ci.insert{name=st.name, count=st.count} end end; "
            f"ci.insert{{name='{item}', count=1}}; "
            "e.destroy(); rcon.print('OK')"
        )
        out = self.a.rcon.command('/silent-command ' + body).strip()
        return out == 'OK'

    def relocate(self, item: str, old_x: float, old_y: float,
                 new_x: float, new_y: float, direction: int = 0) -> dict:
        """Pick up + replace at new position (uses take_back + place).
        Guards the place on take_back success: if the pickup fails (entity not
        found), skip placing so we don't emit a silent MISS by placing with no
        item in inventory."""
        if not self.take_back(item, old_x, old_y):
            return {'result': 'take_back_failed', 'name': item}
        return self.place(item, new_x, new_y, direction)

    def revive_ghost(self, x: float, y: float, radius: float = 0.4) -> dict:
        """Revive a single entity-ghost near (x, y) from the character's main
        inventory. Applies the asm2->asm1 substitution when only the fallback
        item is on hand (destroys the ghost + builds the substitute in place).
        Returns {'result': REVIVED|SUBBED|MISS|NO_ITEM|REVIVE_FAIL|SUB_FAIL}.
        """
        body = (
            f"local c=game.get_entity_by_unit_number({self.a.unit}); "
            f"local s=c.surface; local inv=c.get_main_inventory(); "
            f"local subs={_subs_lua()}; "
            f"local g=s.find_entities_filtered{{name='entity-ghost', "
            f"position={{{x}, {y}}}, radius={radius}}}[1]; "
            "if not g then rcon.print('MISS'); return end; "
            "local gn=g.ghost_name; local item=nil; "
            "if inv.get_item_count(gn) >= 1 then item=gn "
            "elseif subs[gn] and inv.get_item_count(subs[gn]) >= 1 then item=subs[gn] end; "
            "if not item then rcon.print('NO_ITEM'); return end; "
            "if item == gn then "
            "  local rev = g.revive{raise_revive=true, return_item_request_proxy=false}; "
            "  if rev then inv.remove{name=item, count=1}; rcon.print('REVIVED') "
            "  else rcon.print('REVIVE_FAIL') end "
            "else "
            "  local pos, dir = g.position, g.direction; g.destroy(); "
            "  local ok, e = pcall(function() return s.create_entity{name=item, "
            "    position=pos, direction=dir, force=c.force, raise_built=true} end); "
            "  if ok and e then inv.remove{name=item, count=1}; rcon.print('SUBBED') "
            "  else rcon.print('SUB_FAIL') end "
            "end"
        )
        out = self.a.rcon.command('/silent-command ' + body).strip()
        return {'result': out}

    def build_nearby_ghosts(self, radius: float = 10.0) -> dict:
        """Revive every entity-ghost within `radius` tiles of the character,
        using items from the character's main inventory. Applies the asm2->asm1
        substitution when only the fallback item is on hand. One RCON round-trip.
        Returns {'revived': int, 'subbed': int, 'skipped': int}.
        """
        body = (
            f"local c=game.get_entity_by_unit_number({self.a.unit}); "
            f"local s=c.surface; local inv=c.get_main_inventory(); "
            f"local subs={_subs_lua()}; local p=c.position; "
            f"local gs=s.find_entities_filtered{{name='entity-ghost', "
            f"area={{{{p.x-{radius}, p.y-{radius}}}, {{p.x+{radius}, p.y+{radius}}}}}}}; "
            "local rv,sb,sk = 0,0,0; "
            "for _, g in ipairs(gs) do "
            "  if g.valid then "
            "    local gn=g.ghost_name; local item=nil; "
            "    if inv.get_item_count(gn) >= 1 then item=gn "
            "    elseif subs[gn] and inv.get_item_count(subs[gn]) >= 1 then item=subs[gn] end; "
            "    if not item then sk=sk+1 "
            "    elseif item == gn then "
            "      local rev = g.revive{raise_revive=true, return_item_request_proxy=false}; "
            "      if rev then inv.remove{name=item, count=1}; rv=rv+1 else sk=sk+1 end "
            "    else "
            "      local pos, dir = g.position, g.direction; g.destroy(); "
            "      local ok, e = pcall(function() return s.create_entity{name=item, "
            "        position=pos, direction=dir, force=c.force, raise_built=true} end); "
            "      if ok and e then inv.remove{name=item, count=1}; sb=sb+1 else sk=sk+1 end "
            "    end "
            "  end "
            "end; "
            "rcon.print(string.format('%d|%d|%d', rv, sb, sk))"
        )
        out = self.a.rcon.command('/silent-command ' + body).strip()
        parts = out.split('|')
        if len(parts) != 3:
            return {'revived': 0, 'subbed': 0, 'skipped': 0, 'raw': out}
        return {'revived': int(parts[0]), 'subbed': int(parts[1]),
                'skipped': int(parts[2])}
