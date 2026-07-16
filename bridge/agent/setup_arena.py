"""
setup_arena.py — put each employee on its OWN force in its OWN corner.

Run this once after the claude-companion mod is loaded and the 4 brains have spawned their
characters (state/<name>.unum written). It:
  1. Creates a Factorio force per employee (miner/courier/builder/scout).
  2. Makes all four forces + 'player' mutually friendly + cease-fire (peaceful run).
  3. Sets each employee's character onto its force and teleports it to its corner center
     (from arena_build.CORNERS). The 20-wide void cross then physically seals each corner.

Idempotent: safe to re-run (e.g. after a respawn) to re-assert forces + reposition.

    python bridge/agent/setup_arena.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent.compete as c
from agent.arena_build import SURF, CORNERS
from rcon_client import RconClient

_STATE = Path(__file__).resolve().parent / "state"


def _unum(name: str):
    f = _STATE / f"{name}.unum"
    try:
        s = f.read_text(encoding="utf-8").strip()
        return int(s) if s.isdigit() else None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    os.environ.setdefault("FACTORIO_RCON_PASSWORD", c._resolve_rcon_password())
    r = RconClient(); r.connect()

    def cmd(lua: str) -> str:
        return r.command("/silent-command " + lua, drain_timeout=30).strip()

    names = list(CORNERS.keys())
    forces_lua = "{" + ",".join("'" + n + "'" for n in names) + "}"

    # 1) create forces
    print("[1] create forces:", cmd(
        f"for _,n in ipairs({forces_lua}) do if not game.forces[n] then game.create_force(n) end end;"
        "rcon.print('ok')"))

    # 2) peace: every force + player friendly + cease-fire with each other
    print("[2] peace:", cmd(
        f"local ns={{'miner','courier','builder','scout','player'}}; for _,a in ipairs(ns) do "
        "local fa=game.forces[a]; if fa then for _,b in ipairs(ns) do if a~=b then local fb=game.forces[b]; "
        "if fb then fa.set_cease_fire(fb,true); fa.set_friend(fb,true) end end end end end; rcon.print('ok')"))

    # 3) assign each char to its force + teleport to its corner center
    for name in names:
        u = _unum(name)
        cx, cy = CORNERS[name]
        if u is None:
            print(f"    {name}: NO saved unum — brain hasn't spawned yet?")
            continue
        out = cmd(
            f"local e=game.get_entity_by_unit_number({u}); "
            "if not (e and e.valid) then rcon.print('NOCHAR') return end; "
            f"e.force=game.forces['{name}']; "
            f"local p=e.surface.find_non_colliding_position('character',{{{cx},{cy}}},64,0.5) or {{{cx},{cy}}}; "
            "e.teleport(p); "
            "rcon.print('ok '..math.floor(e.position.x)..','..math.floor(e.position.y)..' force='..e.force.name)")
        print(f"    {name} (unum {u}) -> corner ({cx},{cy}): {out}")

    r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
