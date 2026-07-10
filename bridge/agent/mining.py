"""Mining tiles + trees, with proper completion waits + walk-in retry."""
from __future__ import annotations
import time
from typing import Optional


class Mining:
    REACH = 2.7  # mod's MINING_REACH

    def __init__(self, agent):
        self.a = agent

    def mine_at(self, x: float, y: float, walk_in: bool = True,
                tight_radius: float = 0.6) -> dict:
        """Hand-mine the entity at (x, y). Waits for completion.
        On out-of-reach, walks closer once and retries."""
        res = self.a.call('start_mining', self.a.unit, x, y)
        if not res.get('ok') and 'out of reach' in str(res.get('error', '')):
            if walk_in:
                self.a.movement.walk_to(x, y, tight_radius)
                res = self.a.call('start_mining', self.a.unit, x, y)
        if not res.get('ok'):
            return res
        eta_s = (res.get('eta_ticks', 60) / 60) + 1.0
        waited = 0.0
        st = res
        while waited < eta_s + 6:
            time.sleep(0.5)
            waited += 0.5
            st = self.a.call('get_mining_status', self.a.unit)
            if not st.get('mining'):
                break
        if st.get('mining'):
            self.a.call('stop_mining', self.a.unit)
            return {'ok': False, 'error': 'mining timeout'}
        return {'ok': True}

    def mine_nearest(self, resource_name: str, max_radius: int = 30,
                     n: int = 1) -> int:
        """Find + mine n nearest tiles of resource_name. Returns count actually mined."""
        got = 0
        for _ in range(n):
            near = self.a.call('find_nearest_resource', self.a.unit,
                               resource_name, max_radius)
            if not near.get('ok'):
                break
            p = near['position']
            res = self.mine_at(p['x'], p['y'])
            if not res.get('ok'):
                break
            got += 1
        return got

    def chop_trees(self, n: int, search_radius: int = 100) -> int:
        """Find + chop n trees within search_radius. Returns count chopped.

        Trees we walk to but cannot reach (blocked path, island) are
        blacklisted by position so the next 'nearest' query skips them —
        otherwise the same unreachable tree gets re-selected forever.
        """
        chopped = 0
        blacklist = set()  # '%.1f,%.1f' position keys of unreachable trees
        for _ in range(n):
            excl = "{" + ",".join(f"['{k}']=true" for k in blacklist) + "}"
            out = self.a.rcon.command(
                "/silent-command "
                f"local c = game.get_entity_by_unit_number({self.a.unit}); "
                "local s = c.surface; "
                f"local bl = {excl}; "
                f"local trees = s.find_entities_filtered{{position=c.position, "
                f"radius={search_radius}, type='tree'}}; "
                "if #trees == 0 then rcon.print('NONE'); return end; "
                "local best, bestd = nil, 1e9; "
                "for _, t in ipairs(trees) do "
                "  local key = string.format('%.1f,%.1f', t.position.x, t.position.y); "
                "  if not bl[key] then "
                "    local dx = t.position.x - c.position.x; "
                "    local dy = t.position.y - c.position.y; "
                "    local d = dx * dx + dy * dy; "
                "    if d < bestd then bestd = d; best = t end "
                "  end "
                "end; "
                "if not best then rcon.print('NONE'); return end; "
                "rcon.print(string.format('%.1f,%.1f', best.position.x, best.position.y))"
            ).strip()
            if out == 'NONE' or ',' not in out:
                break
            sx, sy = out.split(',')
            tx, ty = float(sx), float(sy)
            wst = self.a.movement.walk_to(tx, ty, 1.2)
            if wst.get('status') != 'completed':
                # Couldn't reach the tree — blacklist so we don't retry it.
                blacklist.add(out)
                continue
            res = self.mine_at(tx, ty)
            if res.get('ok'):
                chopped += 1
            else:
                # Reached but mining failed (still out of reach, gone) — skip it.
                blacklist.add(out)
        return chopped
