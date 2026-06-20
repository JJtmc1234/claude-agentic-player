"""Walking + pathfinding helpers with retry on long-distance failures."""
from __future__ import annotations
import time
from typing import Optional


class Movement:
    def __init__(self, agent):
        self.a = agent

    def walk_to(self, x: float, y: float, radius: float = 1.5,
                timeout_s: int = 120) -> dict:
        """Walk to (x, y) within radius. Returns the final get_walk_status dict."""
        self.a.call('walk_to', self.a.unit, x, y, radius)
        for i in range(timeout_s):
            time.sleep(1)
            st = self.a.call('get_walk_status', self.a.unit)
            if st.get('status') in ('completed', 'error', 'idle'):
                return st
        # Timeout
        self.a.call('cancel_walk', self.a.unit)
        return {'status': 'timeout', 'after_s': timeout_s}

    def walk_chunked(self, x: float, y: float, *,
                     chunk_size: int = 30,
                     radius_final: float = 1.5) -> dict:
        """Walk to (x, y) breaking long paths into intermediate hops.
        Useful for goals 100+ tiles away where pathfinder times out.
        """
        cx, cy = self.a.position()
        dx, dy = x - cx, y - cy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= chunk_size:
            return self.walk_to(x, y, radius_final)
        # Step in chunk_size units toward target
        steps = max(1, int(dist / chunk_size))
        last = None
        for s in range(1, steps + 1):
            t = s / steps
            wx, wy = cx + dx * t, cy + dy * t
            r = radius_final if s == steps else max(2.0, chunk_size * 0.1)
            last = self.walk_to(wx, wy, r)
            if last.get('status') == 'error' and 'no path' in str(last.get('error', '')):
                # Try one tile offset
                last = self.walk_to(wx + 1, wy, r)
        return last

    def step_aside(self, distance: float = 3.0) -> dict:
        """Move the character a short distance off its current spot, used to
        clear a tile for placement when the character is in the footprint."""
        cx, cy = self.a.position()
        # Try moving south then east (low-risk in open terrain)
        for dx, dy in [(0, distance), (distance, 0), (-distance, 0), (0, -distance)]:
            res = self.walk_to(cx + dx, cy + dy, 1.0, timeout_s=15)
            if res.get('status') == 'completed':
                return res
        return res
