"""
arena_void_watch.py — keep the out-of-map PLUS-cross extended as the world grows.

JJ's spec (2026-07-15): "whenever a chunk is generated, generate more PLUS-cross." The
claude-companion mod isn't loaded, so instead of an on_chunk_generated mod hook this is a
standalone RCON watcher: every few seconds it reads the surface's generated-chunk bounds and,
if the map has grown beyond the range already voided, it lays the 20-wide axis bands into the
new area (and clears any entity sitting on the fresh void). Net effect matches the event hook —
the cross always reaches the ends of the generated world.

Reuses the band geometry from arena_build.py so the two stay consistent.

    python bridge/agent/arena_void_watch.py            # poll forever (Ctrl-C to stop)
    python bridge/agent/arena_void_watch.py --once      # single extend pass then exit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent.compete as c
from agent.arena_build import SURF, BAND_MIN, BAND_MAX, EXTENT, VOID_SEG
from rcon_client import RconClient


def _bounds(cmd) -> list:
    out = cmd("local s=game.surfaces['" + SURF + "']; local a,b,cc,d=1e9,1e9,-1e9,-1e9;"
              "for ch in s.get_chunks() do if ch.x<a then a=ch.x end; if ch.y<b then b=ch.y end;"
              "if ch.x>cc then cc=ch.x end; if ch.y>d then d=ch.y end end;"
              "rcon.print(helpers.table_to_json({a*32,b*32,(cc+1)*32,(d+1)*32}))")
    try:
        return [int(v) for v in json.loads(out)]
    except Exception:  # noqa: BLE001
        return [0, 0, 0, 0]


def _void_range(cmd, vertical: bool, lo: int, hi: int) -> int:
    """Void + clear one axis band over the arm coordinate range [lo,hi). Returns tiles set."""
    total = 0
    a = lo
    while a < hi:
        b = min(a + VOID_SEG, hi)
        if vertical:   # x in band, y in [a,b)
            x0, x1, y0, y1 = BAND_MIN, BAND_MAX, a, b - 1
        else:          # y in band, x in [a,b)
            x0, x1, y0, y1 = a, b - 1, BAND_MIN, BAND_MAX
        out = cmd(f"local s=game.surfaces['{SURF}']; local t={{}};"
                  f"for x={x0},{x1} do for y={y0},{y1} do t[#t+1]={{name='out-of-map',position={{x,y}}}} end end;"
                  "s.set_tiles(t);"
                  f"local k=0; for _,e in pairs(s.find_entities_filtered{{area={{{{{x0},{y0}}},{{{x1+1},{y1+1}}}}}}}) do"
                  " if e.valid and e.type~='character' then e.destroy(); k=k+1 end end;"
                  "rcon.print(#t)")
        try:
            total += int(out)
        except ValueError:
            pass
        a = b
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="extend the void cross as the map grows")
    ap.add_argument("--once", action="store_true", help="one extend pass then exit")
    ap.add_argument("--poll", type=float, default=10.0, help="seconds between checks")
    args = ap.parse_args()

    os.environ.setdefault("FACTORIO_RCON_PASSWORD", c._resolve_rcon_password())
    r = RconClient(); r.connect()

    def cmd(lua: str) -> str:
        return r.command("/silent-command " + lua, drain_timeout=60).strip()

    # already-voided extent (arena_build laid +-EXTENT on both arms)
    vy0, vy1 = -EXTENT, EXTENT      # vertical arm covers y in [vy0, vy1)
    hx0, hx1 = -EXTENT, EXTENT      # horizontal arm covers x in [hx0, hx1)
    print(f"[void-watch] start; cross covers +-{EXTENT}. polling every {args.poll}s.", flush=True)

    try:
        while True:
            minx, miny, maxx, maxy = _bounds(cmd)
            done = 0
            if miny < vy0:
                done += _void_range(cmd, True, miny, vy0); vy0 = miny
            if maxy > vy1:
                done += _void_range(cmd, True, vy1, maxy); vy1 = maxy
            if minx < hx0:
                done += _void_range(cmd, False, minx, hx0); hx0 = minx
            if maxx > hx1:
                done += _void_range(cmd, False, hx1, maxx); hx1 = maxx
            if done:
                print(f"[void-watch] extended cross: +{done} void tiles "
                      f"(vert y[{vy0},{vy1}) horiz x[{hx0},{hx1})).", flush=True)
            if args.once:
                break
            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("[void-watch] stopped.", flush=True)
    finally:
        r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
