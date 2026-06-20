"""Fuel-loading with single-slot awareness (won't overflow mixed fuels)."""
from __future__ import annotations
from typing import Optional


class FuelManager:
    def __init__(self, agent):
        self.a = agent

    def fuel(self, entity_name: str, x: float, y: float,
             fuel_item: str = 'wood', want_amount: int = 5,
             search_radius: float = 0.6) -> dict:
        """Insert `want_amount` of `fuel_item` into the named entity at (x, y).
        Skips if entity already has a different fuel type (avoids 'count must be positive' error).
        Returns {ok, moved, status}."""
        body = (
            f"local c = game.get_entity_by_unit_number({self.a.unit}); "
            f"local s = c.surface; local ci = c.get_main_inventory(); "
            f"local e = s.find_entities_filtered{{position={{{x}, {y}}}, "
            f"radius={search_radius}, name='{entity_name}'}}[1]; "
            "if not e then rcon.print('MISS'); return end; "
            "local fi = e.get_fuel_inventory(); "
            "if not fi then rcon.print('NO_FUEL_INV'); return end; "
            f"local have = ci.get_item_count('{fuel_item}'); "
            "if have < 1 then rcon.print('NONE_IN_INV'); return end; "
            f"local moved = fi.insert{{name='{fuel_item}', count=math.min({want_amount}, have)}}; "
            f"if moved > 0 then ci.remove{{name='{fuel_item}', count=moved}} end; "
            "rcon.print(string.format('%d,%d', moved, e.status))"
        )
        out = self.a.rcon.command('/silent-command ' + body).strip()
        if out in ('MISS', 'NO_FUEL_INV', 'NONE_IN_INV'):
            return {'ok': False, 'reason': out}
        moved, status = out.split(',')
        return {'ok': True, 'moved': int(moved), 'status': int(status)}

    def fuel_chain(self, entries: list) -> list:
        """Fuel a list of [(entity_name, x, y, fuel_item, count), ...].
        Returns list of result dicts."""
        results = []
        for entry in entries:
            if len(entry) == 3:
                name, x, y = entry
                results.append(self.fuel(name, x, y))
            elif len(entry) == 5:
                name, x, y, fuel, n = entry
                results.append(self.fuel(name, x, y, fuel, n))
            else:
                results.append({'ok': False, 'reason': 'bad entry'})
        return results
