"""
arena_build.py — carve the competition world for the agent tournament.

JJ's spec (2026-07-15): isolate four corners with a 20-wide out-of-map PLUS-cross on the axes
through (0,0) extending to the ends of the generated world; delete all existing ore; and give
each corner (quadrant) its own water / iron / copper / coal / stone / oil / tree patches within
reasonable distance; then remove every entity left sitting on the void.

All base-game RCON world editing (no claude-companion mod needed). DESTRUCTIVE — it deletes all
resources and everything on the axes. Run only when JJ asks.

    python bridge/agent/arena_build.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent.compete as c          # reuse RCON password resolver
from rcon_client import RconClient

SURF = "nauvis"
BAND_MIN, BAND_MAX = -10, 9        # 20-wide band, centered on the axis (x in [-10,9])
EXTENT = 640                       # half-length of each cross arm (covers generated area ~+-580)
VOID_SEG = 128                     # tiles per set_tiles batch along the arm
TREE = "tree-01"

# quadrant centers (name -> corner). big patches clustered ~45-65 tiles around each center.
CORNERS = {
    "miner":   (150, 150),         # +x +y
    "courier": (-150, 150),        # -x +y
    "builder": (-150, -150),       # -x -y
    "scout":   (150, -150),        # +x -y
}
# resource offsets from a corner center (kept clear of the void; well-separated big patches)
LAYOUT = {
    "iron-ore":  (-45, -45),
    "copper-ore": (45, -45),
    "coal":      (-45, 45),
    "stone":      (45, 45),
    "water":      (0, -65),         # pond
    "crude-oil":  (0, 65),
    "trees":      (0, 0),
}
GEN_RADIUS = 7                     # chunks to force-generate around each corner (~224 tiles)
ORE_AMOUNT = 20000
ORE_HALF = 16                      # ore blob is (2*ORE_HALF+1)^2 tiles ~ 33x33
WATER_HALF = 10                    # 21x21 pond
TREE_COUNT = 90
TREE_SPREAD = 22                   # trees scattered over ~44x44
OIL_WELLS = 9                      # 3x3 field
OIL_AMOUNT = 500000


def main() -> int:
    os.environ.setdefault("FACTORIO_RCON_PASSWORD", c._resolve_rcon_password())
    r = RconClient(); r.connect()

    def cmd(lua: str, t: float = 60.0) -> str:
        return r.command("/silent-command " + lua, drain_timeout=t).strip()

    # 1) delete ALL existing resources (ore + crude-oil are type='resource')
    n = cmd("local s=game.surfaces['" + SURF + "']; local k=0;"
            "for _,e in pairs(s.find_entities_filtered{type='resource'}) do e.destroy(); k=k+1 end;"
            "rcon.print(k)")
    print(f"[1] deleted resources: {n}")

    # 2) lay the 20-wide out-of-map plus-cross out to +-EXTENT, in segments
    def lay_void(vertical: bool) -> int:
        total = 0
        a = -EXTENT
        while a < EXTENT:
            b = min(a + VOID_SEG, EXTENT)
            if vertical:      # band spans x in [BAND_MIN,BAND_MAX], y in [a,b]
                x0, x1, y0, y1 = BAND_MIN, BAND_MAX, a, b
            else:             # band spans y in [BAND_MIN,BAND_MAX], x in [a,b]
                x0, x1, y0, y1 = a, b, BAND_MIN, BAND_MAX
            out = cmd(f"local s=game.surfaces['{SURF}']; local t={{}};"
                      f"for x={x0},{x1} do for y={y0},{y1} do t[#t+1]={{name='out-of-map',position={{x,y}}}} end end;"
                      "s.set_tiles(t); rcon.print(#t)")
            try:
                total += int(out)
            except ValueError:
                pass
            a = b
        return total

    print(f"[2] void tiles set (vertical arm): {lay_void(True)}")
    print(f"[2] void tiles set (horizontal arm): {lay_void(False)}")

    # 3) destroy every non-character entity sitting on the void band, in segments
    def clear_band(vertical: bool) -> int:
        total = 0
        a = -EXTENT
        while a < EXTENT:
            b = min(a + VOID_SEG, EXTENT)
            if vertical:
                area = f"{{{{{BAND_MIN},{a}}},{{{BAND_MAX},{b}}}}}"
            else:
                area = f"{{{{{a},{BAND_MIN}}},{{{b},{BAND_MAX}}}}}"
            out = cmd(f"local s=game.surfaces['{SURF}']; local k=0;"
                      f"for _,e in pairs(s.find_entities_filtered{{area={area}}}) do"
                      " if e.valid and e.type~='character' then e.destroy(); k=k+1 end end;"
                      "rcon.print(k)")
            try:
                total += int(out)
            except ValueError:
                pass
            a = b
        return total

    print(f"[3] entities cleared off void (vertical): {clear_band(True)}")
    print(f"[3] entities cleared off void (horizontal): {clear_band(False)}")

    # 4) build each quadrant's resource patches
    for name, (cx, cy) in CORNERS.items():
        # force-generate the corner's chunks so far-out placements land on real terrain
        cmd(f"local s=game.surfaces['{SURF}']; s.request_to_generate_chunks({{{cx},{cy}}},{GEN_RADIUS});"
            "s.force_generate_chunk_requests(); rcon.print('gen')", t=120)
        for res, (dx, dy) in LAYOUT.items():
            px, py = cx + dx, cy + dy
            if res == "trees":
                out = cmd(
                    f"local s=game.surfaces['{SURF}']; local k=0;"
                    f"for i=1,{TREE_COUNT} do local x={px}+((i*13)%(2*{TREE_SPREAD}))-{TREE_SPREAD};"
                    f"  local y={py}+((i*7)%(2*{TREE_SPREAD}))-{TREE_SPREAD};"
                    f"  local p=s.find_non_colliding_position('{TREE}',{{x,y}},4,0.5);"
                    f"  if p then s.create_entity{{name='{TREE}',position=p}}; k=k+1 end end;"
                    "rcon.print(k)")
                print(f"    {name} trees: {out}")
            elif res == "water":
                cmd(f"local s=game.surfaces['{SURF}'];"
                    f"for _,e in pairs(s.find_entities_filtered{{area={{{{{px-WATER_HALF-1},{py-WATER_HALF-1}}},{{{px+WATER_HALF+1},{py+WATER_HALF+1}}}}}}}) do"
                    " if e.valid and e.type~='character' then e.destroy() end end;"
                    "local t={};"
                    f"for x={px-WATER_HALF},{px+WATER_HALF} do for y={py-WATER_HALF},{py+WATER_HALF} do t[#t+1]={{name='water',position={{x,y}}}} end end;"
                    "s.set_tiles(t)")
                print(f"    {name} water pond @ ({px},{py})")
            elif res == "crude-oil":
                out = cmd(f"local s=game.surfaces['{SURF}']; local k=0;"
                          f"for i=0,{OIL_WELLS-1} do local x={px}+(i%3)*4; local y={py}+math.floor(i/3)*4;"
                          f"  for _,e in pairs(s.find_entities_filtered{{area={{{{x-1,y-1}},{{x+1,y+1}}}}}}) do if e.valid and e.type~='character' then e.destroy() end end;"
                          f"  local p=s.find_non_colliding_position('crude-oil',{{x,y}},3,1) or {{x,y}};"
                          f"  s.create_entity{{name='crude-oil',position=p,amount={OIL_AMOUNT}}}; k=k+1 end;"
                          "rcon.print(k)")
                print(f"    {name} oil wells: {out}")
            else:  # ore blob
                out = cmd(f"local s=game.surfaces['{SURF}'];"
                          f"for _,e in pairs(s.find_entities_filtered{{area={{{{{px-ORE_HALF},{py-ORE_HALF}}},{{{px+ORE_HALF},{py+ORE_HALF}}}}},type={{'tree','simple-entity','cliff'}}}}) do if e.valid then e.destroy() end end;"
                          "local k=0;"
                          f"for x={px-ORE_HALF},{px+ORE_HALF} do for y={py-ORE_HALF},{py+ORE_HALF} do"
                          f"  if s.get_tile(x,y).name~='out-of-map' then s.create_entity{{name='{res}',position={{x,y}},amount={ORE_AMOUNT}}}; k=k+1 end end end;"
                          "rcon.print(k)")
                print(f"    {name} {res}: {out} tiles")
        print(f"[4] quadrant '{name}' @ ({cx},{cy}) done")

    # verify
    for name, (cx, cy) in CORNERS.items():
        out = cmd(f"local s=game.surfaces['{SURF}']; local o={{}};"
                  f"for _,rn in ipairs({{'iron-ore','copper-ore','coal','stone','crude-oil'}}) do"
                  f"  o[rn]=#s.find_entities_filtered{{name=rn,area={{{{{cx-120},{cy-120}}},{{{cx+120},{cy+120}}}}}}} end;"
                  f"  o.trees=#s.find_entities_filtered{{type='tree',area={{{{{cx-120},{cy-120}}},{{{cx+120},{cy+120}}}}}}};"
                  "rcon.print(helpers.table_to_json(o))")
        print(f"[verify] {name}: {out}")
    print("[verify] void@(0,50):", cmd(f"rcon.print(game.surfaces['{SURF}'].get_tile(0,50).name)"))
    print("[verify] void@(50,0):", cmd(f"rcon.print(game.surfaces['{SURF}'].get_tile(50,0).name)"))
    r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
