"""Entity placement with auto-snap, blocker clearing, character-self-collision avoidance."""
from __future__ import annotations
from typing import Optional, Tuple

from agent.geometry import snap_2x2_center, snap_1x1_center


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
        Resources are mineable_properties.minable but type='resource', not 'tree'."""
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
            "    e.destroy() "
            "  end "
            "end"
        )
        self.a.rcon.command('/silent-command ' + body)

    def take_back(self, item: str, x: float, y: float) -> bool:
        """Mine an entity and return its name + inventory contents to character.
        Bypasses reach checks for large entities like crash-site-spaceship."""
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
        """Pick up + replace at new position (uses take_back + place)."""
        self.take_back(item, old_x, old_y)
        return self.place(item, new_x, new_y, direction)
