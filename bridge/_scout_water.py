"""Find water tiles + their pump-output directions near my position."""
import sys
sys.path.insert(0, 'bridge')
from agent import Agent

with Agent.connect() as a:
    print(f'at {a.position()}')
    # Find water and edge tiles within 60
    body = (
        "local c = game.get_entity_by_unit_number(" + str(a.unit) + "); "
        "local s = c.surface; "
        "local water = s.find_tiles_filtered{position=c.position, radius=80, name={'water','deepwater'}}; "
        "rcon.print('total water tiles within 80: ' .. #water); "
        # For each water tile, check if any neighbor is land
        "local function isLand(t) return t and not (t.name == 'water' or t.name == 'deepwater') end; "
        "local edges = {}; "
        "for _, wt in ipairs(water) do "
        "  local wx, wy = wt.position.x, wt.position.y; "
        "  local n_land = {}; "
        "  if isLand(s.get_tile(wx, wy-1)) then table.insert(n_land, 'N') end; "
        "  if isLand(s.get_tile(wx+1, wy)) then table.insert(n_land, 'E') end; "
        "  if isLand(s.get_tile(wx, wy+1)) then table.insert(n_land, 'S') end; "
        "  if isLand(s.get_tile(wx-1, wy)) then table.insert(n_land, 'W') end; "
        "  if #n_land > 0 then "
        "    local dx = wx - c.position.x; local dy = wy - c.position.y; "
        "    local d = math.sqrt(dx*dx + dy*dy); "
        "    table.insert(edges, {x=wx+0.5, y=wy+0.5, d=d, sides=table.concat(n_land, ',')}) "
        "  end "
        "end; "
        "rcon.print('water-edge tiles: ' .. #edges); "
        # Sort by distance, show top 8 closest
        "table.sort(edges, function(a,b) return a.d < b.d end); "
        "for i = 1, math.min(8, #edges) do "
        "  local e = edges[i]; "
        "  rcon.print(string.format('  (%.1f, %.1f) dist=%.1f land sides: %s', e.x, e.y, e.d, e.sides)) "
        "end"
    )
    print(a.rcon.command('/silent-command ' + body))
