"""
World-wide resource snapshot on the player force.

Aggregates across all surfaces:
- 'stored': total counts of items inside containers (regular chests + logistic
  chests). Excludes belts, assembler buffers, furnaces, vehicles, character
  inventories — those are in-process / on-the-move, not "in storage."
- 'built': total counts of each entity type placed in the world. Excludes
  characters and ghosts (planned but not yet built).

Run:
    python bridge/resources.py
"""

import json
import sys

from rcon_client import RconClient

LUA = r"""
local out = { stored = {}, built = {} }
for _, s in pairs(game.surfaces) do
  for _, e in pairs(s.find_entities_filtered{force='player'}) do
    if e.type == 'container' or e.type == 'logistic-container' then
      local inv = e.get_inventory(defines.inventory.chest)
      if inv then
        for _, stack in ipairs(inv.get_contents()) do
          out.stored[stack.name] = (out.stored[stack.name] or 0) + stack.count
        end
      end
    end
    if e.type ~= 'character' and e.type ~= 'entity-ghost' and e.type ~= 'tile-ghost' then
      out.built[e.name] = (out.built[e.name] or 0) + 1
    end
  end
end
rcon.print(helpers.table_to_json(out))
"""


def main() -> int:
    with RconClient() as r:
        body = r.command("/silent-command " + LUA).strip()
    if not body:
        print("[resources] empty response", file=sys.stderr)
        return 1
    if body.startswith("Cannot execute command"):
        print(f"[resources] server error: {body}", file=sys.stderr)
        return 2
    data = json.loads(body)

    stored = data.get("stored") or {}
    built = data.get("built") or {}

    print(
        f"stored in chests ({len(stored)} kinds, "
        f"{sum(stored.values())} total items):"
    )
    if stored:
        for name, count in sorted(stored.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>8} x {name}")
    else:
        print("  (nothing)")

    print(
        f"\nbuilt entities ({len(built)} kinds, "
        f"{sum(built.values())} total):"
    )
    if built:
        for name, count in sorted(built.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>6} x {name}")
    else:
        print("  (nothing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
