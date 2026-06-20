"""Find tree clusters near Claude — return the nearest few."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = c.surface; "
    "local trees = s.find_entities_filtered{position=c.position, radius=200, type='tree'}; "
    "rcon.print('trees within 200: ' .. #trees); "
    "if #trees == 0 then return end; "
    "table.sort(trees, function(a, b) "
    "  local da = (a.position.x - c.position.x)^2 + (a.position.y - c.position.y)^2; "
    "  local db = (b.position.x - c.position.x)^2 + (b.position.y - c.position.y)^2; "
    "  return da < db "
    "end); "
    "for i = 1, math.min(10, #trees) do "
    "  local t = trees[i]; "
    "  local dx = t.position.x - c.position.x; "
    "  local dy = t.position.y - c.position.y; "
    "  local d = math.sqrt(dx*dx + dy*dy); "
    "  rcon.print(string.format('  %s at (%.1f, %.1f) dist=%.1f', "
    "    t.name, t.position.x, t.position.y, d)) "
    "end"
))
r.close()
