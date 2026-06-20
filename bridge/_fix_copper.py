"""Mine the misplaced copper inserter + chest, replace them 1 tile north.

Iron pattern works: furnace(-14, 53) + inserter(-13.5, 54.5) + chest(-13.5, 55.5).
Copper has furnace at Y=52 not 53 -- I copy-pasted offsets and forgot to shift.
Fix: inserter (-10.5, 53.5) instead of (-10.5, 54.5);
     chest    (-10.5, 54.5) instead of (-10.5, 55.5)."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Mine via silent-command (avoids reach issues)
print("=== mining misplaced copper inserter + chest ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function pickup(name, x, y) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.5, name=name}[1]; "
    "  if not e then return name..':missing' end; "
    # Take its inventory contents too if it's a chest
    "  local total_inv = e.get_inventory(defines.inventory.chest); "
    "  if total_inv then "
    "    for _, st in ipairs(total_inv.get_contents()) do "
    "      ci.insert{name=st.name, count=st.count} "
    "    end "
    "  end; "
    # Take fuel inventory too if it's an inserter
    "  local fi = e.get_fuel_inventory(); "
    "  if fi then "
    "    for _, st in ipairs(fi.get_contents()) do "
    "      ci.insert{name=st.name, count=st.count} "
    "    end "
    "  end; "
    # Return the entity to inventory
    "  ci.insert{name=name, count=1}; "
    "  e.destroy(); "
    "  return name..':removed' "
    "end; "
    "rcon.print(pickup('burner-inserter', -10.5, 54.5)); "
    "rcon.print(pickup('wooden-chest', -10.5, 55.5))"
))

# Re-place at correct positions
print("\n=== placing corrected ===")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', -11, 53, 0)
print(f"  inserter: {ins}")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', -11, 54, 0)
print(f"  chest: {chest}")

# Fuel
print("\n=== fueling new inserter ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={-10.5, 53.5}, radius=0.5, name='burner-inserter'}[1]; "
    "if not i then rcon.print('missing'); return end; "
    "local fi = i.get_fuel_inventory(); "
    "local moved = fi.insert{name='wood', count=5}; "
    "if moved > 0 then ci.remove{name='wood', count=moved} end; "
    "rcon.print('+' .. moved .. ' wood, dir=' .. i.direction .. ' status=' .. i.status)"
))

# Wait + verify
time.sleep(20)
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local ch = s.find_entities_filtered{position={-10.5, 54.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local f = s.find_entities_filtered{position={-11, 52}, radius=0.5, name='stone-furnace'}[1]; "
    "local fres = f and f.get_inventory(defines.inventory.furnace_result); "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print('furnace_output=' .. (fres and fres.get_item_count('copper-plate') or 0) "
    "  .. ' copper_chest=' .. (chi and chi.get_item_count('copper-plate') or 0))"
))
r.close()
