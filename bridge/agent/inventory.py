"""Character inventory + chest transfers + crafting waits."""
from __future__ import annotations
import time
from typing import Optional, Dict


class Inventory:
    def __init__(self, agent):
        self.a = agent

    def list(self) -> Dict[str, int]:
        """Return {item_name: count} for character main inventory."""
        res = self.a.call('get_character_inventory', self.a.unit)
        return {it['name']: it['count'] for it in res.get('items', [])}

    def have(self, item_name: str) -> int:
        return self.list().get(item_name, 0)

    def take_from_chest(self, x: float, y: float, item_name: str, count: int) -> dict:
        return self.a.call('transfer_items', self.a.unit, x, y,
                           item_name, count, 'from_chest')

    def put_in_chest(self, x: float, y: float, item_name: str, count: int) -> dict:
        return self.a.call('transfer_items', self.a.unit, x, y,
                           item_name, count, 'to_chest')

    def chest_count(self, x: float, y: float, item_name: str,
                    chest_name: str = 'wooden-chest', radius: float = 0.5) -> int:
        """Read item count from a specific chest at (x, y)."""
        body = (
            f"local s = game.surfaces['nauvis']; "
            f"local ch = s.find_entities_filtered{{position={{{x}, {y}}}, "
            f"radius={radius}, name='{chest_name}'}}[1]; "
            "if not ch then rcon.print(-1); return end; "
            "local inv = ch.get_inventory(defines.inventory.chest); "
            "if not inv then rcon.print(-2); return end; "
            f"rcon.print(inv.get_item_count('{item_name}'))"
        )
        out = self.a.rcon.command('/silent-command ' + body).strip()
        try:
            return int(out)
        except ValueError:
            return -3

    def craft(self, recipe: str, count: int = 1, timeout_s: int = 120) -> dict:
        """Start a craft, poll until done, return the final get_craft_status dict."""
        res = self.a.call('craft', self.a.unit, recipe, count)
        if not res.get('ok'):
            return res
        for _ in range(timeout_s):
            time.sleep(1)
            st = self.a.call('get_craft_status', self.a.unit)
            if st.get('status') != 'crafting':
                return st
        return {'status': 'timeout'}

    def craft_recipe_chain(self, recipes: list) -> list:
        """Craft a sequence of (recipe, count) pairs sequentially. Returns results."""
        results = []
        for entry in recipes:
            if isinstance(entry, str):
                recipe, count = entry, 1
            else:
                recipe, count = entry[0], entry[1] if len(entry) > 1 else 1
            results.append(self.craft(recipe, count))
        return results
