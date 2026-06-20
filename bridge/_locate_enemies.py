"""Pinpoint biter spawners + worms (the stationary threats)."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = c.surface; "
    "local enemies = s.find_entities_filtered{position=c.position, radius=300, force='enemy'}; "
    "rcon.print(string.format('claude at (%.1f, %.1f)', c.position.x, c.position.y)); "
    "for _, e in ipairs(enemies) do "
    "  local dx = e.position.x - c.position.x; "
    "  local dy = e.position.y - c.position.y; "
    "  local dist = math.sqrt(dx*dx + dy*dy); "
    "  local bearing; "
    "  if math.abs(dx) > math.abs(dy) then bearing = dx > 0 and 'E' or 'W' "
    "  else bearing = dy > 0 and 'S' or 'N' end; "
    "  rcon.print(string.format('  %-22s at (%6.1f,%6.1f) dist=%4.1f %s', "
    "    e.name, e.position.x, e.position.y, dist, bearing)) "
    "end"
))
r.close()
