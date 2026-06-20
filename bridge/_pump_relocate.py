"""Find a water tile where the offshore-pump's auto-output target lands on land."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Mine current pump + boiler + engine (rebuild fresh)
print("=== mine existing chain ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function take(name, x, y, radius) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=radius or 1.5, name=name}[1]; "
    "  if not e then return name..':miss' end; "
    "  local fi = e.get_fuel_inventory(); if fi then for _,st in ipairs(fi.get_contents()) do ci.insert{name=st.name,count=st.count} end end; "
    "  ci.insert{name=name,count=1}; e.destroy(); return name..':taken' "
    "end; "
    "rcon.print(take('offshore-pump', -41.5, 21.5, 0.6)); "
    "rcon.print(take('boiler', -39, 22.5, 1.6)); "
    "rcon.print(take('steam-engine', -35.5, 22.5, 2)); "
    "rcon.print(take('pipe', -40.5, 21.5, 0.6))"
))

# Probe water tiles within 20 for one where the output target (1 tile in some direction) is LAND
print("\n=== scan water tiles for valid pump-output spots ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
    "local water = s.find_tiles_filtered{position=c.position, radius=20, name={'water','deepwater'}}; "
    "local good = {}; "
    "for _, wt in ipairs(water) do "
    "  local wx, wy = wt.position.x, wt.position.y; "
    # For each adjacent direction, check if the adjacent tile is LAND (not water)
    "  for _, off in ipairs({{1,0,'E'},{-1,0,'W'},{0,1,'S'},{0,-1,'N'}}) do "
    "    local nx, ny = wx + off[1], wy + off[2]; "
    "    local nt = s.get_tile(nx, ny); "
    "    local is_water = nt and (nt.name == 'water' or nt.name == 'deepwater' or string.find(nt.name, 'water')); "
    "    if nt and nt.valid and not is_water then "
    "      table.insert(good, {x=wx+0.5, y=wy+0.5, dir=off[3], lx=nx+0.5, ly=ny+0.5}); "
    "      break "
    "    end "
    "  end "
    "end; "
    "local n = math.min(3, #good); "
    "for i = 1, n do "
    "  rcon.print(string.format('water (%.1f,%.1f) → land %s at (%.1f,%.1f)', good[i].x, good[i].y, good[i].dir, good[i].lx, good[i].ly)) "
    "end; "
    "rcon.print('TOTAL ' .. #good .. ' water-edge tiles')"
))
r.close()
