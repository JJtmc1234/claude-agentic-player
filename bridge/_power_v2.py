"""Mine the misplaced engine, build a clean E-facing chain: pump->pipe->boiler->engine."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Mine the existing pump + engine + pole, start over
print("=== mine existing ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function take(name, x, y) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=1.5, name=name}[1]; "
    "  if not e then return name..':missing' end; "
    "  local fi = e.get_fuel_inventory(); if fi then for _,st in ipairs(fi.get_contents()) do ci.insert{name=st.name,count=st.count} end end; "
    "  ci.insert{name=name, count=1}; e.destroy(); return name..':taken' "
    "end; "
    "rcon.print(take('offshore-pump', -41.5, 21.5)); "
    "rcon.print(take('steam-engine', -41.5, 12.5)); "
    "rcon.print(take('small-electric-pole', -39.5, 13.5))"
))

# Walk close to placement zone (~−40, 21)
print("\n=== walk to (-39, 22) ===")
call_mod(r, 'walk_to', unum, -39, 22, 1.5)
for _ in range(30):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Layout (E-facing chain):
# pump (water) at (-41.5, 21.5) dir=E (output to east)
# pipe at (-40.5, 21.5)
# boiler 3w x 2t at (-39, 22) dir=E (water in west, steam out east)
# pipe at (-37.5, 22.5) [east of boiler]
# steam-engine at (-35.5, 22) dir=E (3w x 2t when E-facing)
# pole at (-33.5, 21.5)

print("\n=== place pump (-41.5, 21.5) dir=E (4) ===")
pump = call_mod(r, 'place_entity', unum, 'offshore-pump', -41.5, 21.5, 4)
print(f"  {pump}")

print("\nplace pipe (-40.5, 21.5)...")
pipe1 = call_mod(r, 'place_entity', unum, 'pipe', -40.5, 21.5, 0)
print(f"  {pipe1}")

print("\nplace boiler (-39, 22) dir=E (4)...")
boiler = call_mod(r, 'place_entity', unum, 'boiler', -39, 22, 4)
print(f"  {boiler}")
if not boiler.get('ok'):
    # Try other Y or center positions
    for cx, cy in [(-39, 21), (-38, 22), (-38, 21), (-39, 23)]:
        boiler = call_mod(r, 'place_entity', unum, 'boiler', cx, cy, 4)
        print(f"  try ({cx},{cy}): {boiler}")
        if boiler.get('ok'): break

if boiler.get('ok'):
    bx, by = boiler['position']['x'], boiler['position']['y']
    # Steam engine east of boiler
    print(f"\nplace engine east of boiler (at +3, same y)...")
    for off_x in [3, 3.5, 4]:
        engine = call_mod(r, 'place_entity', unum, 'steam-engine', bx + off_x, by, 4)
        if engine.get('ok'):
            print(f"  {engine}")
            break
        else:
            print(f"  off={off_x} fail: {engine.get('error')}")

# Place pole adjacent to engine area
print("\nplace pole at (-33.5, 21.5)...")
pole = call_mod(r, 'place_entity', unum, 'small-electric-pole', -33.5, 21.5, 0)
print(f"  {pole}")

# Fuel boiler
print("\n=== fuel boiler ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local b = s.find_entities_filtered{position={-39, 22}, radius=3, name='boiler'}[1]; "
    "if not b then rcon.print('NO boiler'); return end; "
    "local fi = b.get_fuel_inventory(); "
    "local have_wood = ci.get_item_count('wood'); "
    "local m = fi.insert{name='wood', count=math.min(20, have_wood)}; "
    "if m > 0 then ci.remove{name='wood', count=m} end; "
    "rcon.print('boiler +' .. m .. ' wood (st=' .. b.status .. ')')"
))

time.sleep(15)

# Status of full chain
print("\n=== status after 15s ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local p = s.find_entities_filtered{position={-41.5, 21.5}, radius=1, name='offshore-pump'}[1]; "
    "local b = s.find_entities_filtered{position={-39, 22}, radius=3, name='boiler'}[1]; "
    "local engines = s.find_entities_filtered{position={-36, 22}, radius=4, name='steam-engine'}; "
    "local poles = s.find_entities_filtered{position={-34, 22}, radius=5, name='small-electric-pole'}; "
    "local msg = ''; "
    "msg = msg .. 'pump=' .. (p and p.status or 'NA'); "
    "msg = msg .. ' boiler=' .. (b and b.status or 'NA'); "
    "msg = msg .. ' engines=' .. #engines; "
    "msg = msg .. ' poles=' .. #poles; "
    "if #engines > 0 then msg = msg .. ' engine_st=' .. engines[1].status .. ' production=' .. (engines[1].energy_generated_last_tick or 0) end; "
    "rcon.print(msg)"
))
r.close()
