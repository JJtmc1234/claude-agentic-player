"""
Snapshot of what's currently happening on the server.

Reads game state via RCON+Lua and prints a friendly summary:
- current tick
- each surface (a "surface" in Factorio is a world/map plane — vanilla has
  one called 'nauvis'; Space Age has many, one per planet)
- each online player: name, position, surface, health, and top inventory
  items by count

Run:
    set FACTORIO_RCON_PASSWORD=<same password as in start-server.bat>
    python bridge/look.py
"""

import json
import sys

from rcon_client import RconClient

# One-line Lua expression: build a Lua table that mirrors the game state we
# care about, serialize it to JSON with game.table_to_json, send it back via
# rcon.print. Python then json.loads it.
SCAN_RADIUS = 500  # tiles around each player; constructions outside this are ignored

# Lua snippet sent over RCON via /silent-command. Builds one Lua table that
# mirrors the game state we want, JSON-encodes it, and prints it back through
# the RCON connection. Newlines are fine inside the body of a /silent-command.
LUA_SNAPSHOT = f"""
local R = {SCAN_RADIUS}
local alert_names = {{}}
for name, idx in pairs(defines.alert_type) do alert_names[idx] = name end

local out = {{ tick = game.tick, surfaces = {{}}, forces = {{}}, players = {{}} }}

for _, s in pairs(game.surfaces) do
  table.insert(out.surfaces, {{ name = s.name, daytime = s.daytime }})
end

for _, f in pairs(game.forces) do
  if f.name ~= 'enemy' and f.name ~= 'neutral' and f.name ~= 'capture' then
    local r = {{
      name = f.name,
      current_research = f.current_research and f.current_research.name or nil,
      progress = f.research_progress,
      queue = {{}},
      researched_count = 0,
      total_count = 0,
    }}
    for _, t in pairs(f.technologies) do
      r.total_count = r.total_count + 1
      if t.researched then r.researched_count = r.researched_count + 1 end
    end
    for _, t in ipairs(f.research_queue) do
      table.insert(r.queue, t.name)
    end
    table.insert(out.forces, r)
  end
end

for _, p in pairs(game.connected_players) do
  local e = {{
    name = p.name,
    position = {{ x = p.position.x, y = p.position.y }},
    surface = p.surface.name,
    force = p.force.name,
    online_time = p.online_time,
  }}
  if p.character then
    e.health = p.character.health
    local inv = p.get_main_inventory()
    if inv then e.inventory = inv.get_contents() end
    local px, py = p.position.x, p.position.y
    local ents = p.surface.find_entities_filtered{{
      area = {{ {{ px-R, py-R }}, {{ px+R, py+R }} }},
      force = 'player'
    }}
    local c = {{}}
    for _, ent in pairs(ents) do
      if ent.name ~= 'character' then
        c[ent.name] = (c[ent.name] or 0) + 1
      end
    end
    e.constructions = c
  end
  -- player-specific alerts (low-power, no-fuel, biters attacking, etc.)
  local alerts = p.get_alerts{{}}
  local alert_summary = {{}}
  for _, surf_alerts in pairs(alerts) do
    for atype, type_alerts in pairs(surf_alerts) do
      local an = alert_names[atype] or tostring(atype)
      for _, _a in pairs(type_alerts) do
        alert_summary[an] = (alert_summary[an] or 0) + 1
      end
    end
  end
  e.alerts = alert_summary
  table.insert(out.players, e)
end

rcon.print(helpers.table_to_json(out))
"""


def _normalize_inventory(inv: object) -> list[tuple[str, int]]:
    """Factorio 2.0 returns inventory as a list of {name,count,quality} records;
    older versions returned a dict {name: count}. Accept either."""
    if isinstance(inv, dict):
        return list(inv.items())
    if isinstance(inv, list):
        # Quality-aware: collapse per-quality counts into total per item name.
        totals: dict[str, int] = {}
        for row in inv:
            name = row.get("name")
            count = int(row.get("count", 0))
            if name:
                totals[name] = totals.get(name, 0) + count
        return list(totals.items())
    return []


def main() -> int:
    with RconClient() as r:
        body = r.command("/silent-command " + LUA_SNAPSHOT).strip()
    if not body:
        print(
            "[look] empty response — Lua likely errored. Check the "
            "server console for an error line.",
            file=sys.stderr,
        )
        return 1
    # Factorio reports Lua errors as plain text starting with
    # "Cannot execute command. Error: ..." — catch that before json.loads.
    if body.startswith("Cannot execute command"):
        print(f"[look] server returned a Lua error:\n  {body}", file=sys.stderr)
        return 2
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        print(f"[look] not valid JSON: {exc}\nraw: {body!r}", file=sys.stderr)
        return 3

    print(f"tick: {data['tick']}")
    print("surfaces:")
    for s in data["surfaces"] or []:
        print(f"  - {s['name']} (daytime={s['daytime']:.2f})")
    forces = data.get("forces") or []
    print("research:")
    for f in forces:
        if f.get("current_research"):
            pct = (f.get("progress") or 0) * 100
            print(
                f"  - force '{f['name']}': researching {f['current_research']} "
                f"({pct:.0f}%), {f['researched_count']}/{f['total_count']} techs done"
            )
        else:
            print(
                f"  - force '{f['name']}': no active research, "
                f"{f['researched_count']}/{f['total_count']} techs done"
            )
        queue = f.get("queue") or []
        if queue:
            print(f"      queue ({len(queue)}): {', '.join(queue)}")
        else:
            print(f"      queue: empty")
    players = data.get("players") or []
    print(f"players online ({len(players)}):")
    if not players:
        print("  (nobody)")
    for p in players:
        pos = p["position"]
        print(f"  - {p['name']} @ ({pos['x']:.1f}, {pos['y']:.1f}) on {p['surface']}")
        if "health" in p:
            print(f"      health: {p['health']:.0f}")
        if "health" not in p:
            print("      (no character entity right now — dead, respawning, or in editor)")
        else:
            inv_items = _normalize_inventory(p.get("inventory"))
            if inv_items:
                top = sorted(inv_items, key=lambda kv: -kv[1])[:10]
                print(f"      inventory ({len(inv_items)} kinds, top {len(top)} by count):")
                for name, count in top:
                    print(f"        {count:>6} x {name}")
            else:
                print("      inventory: empty")
        constructions = p.get("constructions") or {}
        if constructions:
            ordered = sorted(constructions.items(), key=lambda kv: -kv[1])
            total = sum(constructions.values())
            print(
                f"      constructions on player force within {SCAN_RADIUS} tiles "
                f"({total} entities, {len(ordered)} kinds):"
            )
            for name, count in ordered:
                print(f"        {count:>6} x {name}")
        else:
            print(f"      constructions: none within {SCAN_RADIUS} tiles")
        alerts = p.get("alerts") or {}
        if alerts:
            ordered = sorted(alerts.items(), key=lambda kv: -kv[1])
            total = sum(alerts.values())
            summary = ", ".join(f"{c} {n}" for n, c in ordered)
            print(f"      alerts: {total} ({summary})")
        else:
            print("      alerts: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
