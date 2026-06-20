"""Place boiler + engine + connection pipes + pole north of the offshore-pump."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk a bit north of pump so we can place boiler etc
print("walking north a bit (-41, 15)...")
call_mod(r, 'walk_to', unum, -41, 15, 2.0)
for _ in range(40):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Pump at (-41.5, 21.5) facing N, outputs water north (at (-41.5, 20.5))
# Pipe at (-41.5, 20.5) connects to pump
print("\nplacing pipe at (-41.5, 20.5)...")
pipe1 = call_mod(r, 'place_entity', unum, 'pipe', -41.5, 20.5, 0)
print(f"  {pipe1}")

# Boiler 3x2 facing N (dir=0): outputs steam north, takes water south. Center at (-41, 18)?
# 3x2 boiler dir=0 covers 3 wide × 2 tall? Actually let me check by attempting placement
print("\nplacing boiler at (-41, 18) dir=N (water in south, steam out north)...")
boiler = call_mod(r, 'place_entity', unum, 'boiler', -41, 18, 0)
print(f"  {boiler}")
if not boiler.get('ok'):
    # Try dir=8 (south) instead, boiler at (-41, 17)
    print("  trying dir=8 at (-41, 18)...")
    boiler = call_mod(r, 'place_entity', unum, 'boiler', -41, 18, 8)
    print(f"  {boiler}")

# Steam engine facing N (dir=0), placed north of boiler
print("\nplacing steam-engine north of boiler at (-41.5, 14)...")
engine = call_mod(r, 'place_entity', unum, 'steam-engine', -41.5, 14, 0)
print(f"  {engine}")
if not engine.get('ok'):
    # Try various positions
    for cy in [13, 12, 15, 14]:
        for dr in [0, 8]:
            engine = call_mod(r, 'place_entity', unum, 'steam-engine', -41.5, cy, dr)
            if engine.get('ok'):
                print(f"  placed at (-41.5, {cy}) dir={dr}: {engine}")
                break
        if engine.get('ok'): break

# Electric pole somewhere near engine
print("\nplacing small-electric-pole at (-39.5, 13.5)...")
pole = call_mod(r, 'place_entity', unum, 'small-electric-pole', -39.5, 13.5, 0)
print(f"  {pole}")

# Fuel the boiler with coal
print("\n=== fuel boiler ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local b = s.find_entities_filtered{position={-41, 18}, radius=2, name='boiler'}[1]; "
    "if not b then rcon.print('NO boiler'); return end; "
    "local fi = b.get_fuel_inventory(); "
    "local have_coal = ci.get_item_count('coal'); "
    "local have_wood = ci.get_item_count('wood'); "
    "local moved = 0; "
    "if have_coal > 0 then moved = fi.insert{name='coal', count=have_coal}; ci.remove{name='coal', count=moved} "
    "elseif have_wood > 0 then moved = fi.insert{name='wood', count=math.min(20, have_wood)}; ci.remove{name='wood', count=moved} end; "
    "rcon.print('boiler fueled +' .. moved .. ' (st=' .. b.status .. ')')"
))

time.sleep(10)
# Status of whole chain
print("\n=== chain status ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local p = s.find_entities_filtered{position={-41.5, 21.5}, radius=1, name='offshore-pump'}[1]; "
    "local b = s.find_entities_filtered{position={-41, 18}, radius=3, name='boiler'}[1]; "
    "local e = s.find_entities_filtered{position={-41.5, 14}, radius=4, name='steam-engine'}[1]; "
    "local pol = s.find_entities_filtered{position={-39.5, 13.5}, radius=4, name='small-electric-pole'}[1]; "
    "rcon.print(string.format('pump=%s boiler=%s engine=%s pole=%s', "
    "  p and p.status or 'NA', b and b.status or 'NA', e and e.status or 'NA', pol and pol.status or 'NA'))"
))
r.close()
