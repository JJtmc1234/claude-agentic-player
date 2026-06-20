"""Pull iron from chest, craft full power chain."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Pull iron plates from chest
print("=== pull iron from chest ===")
res = call_mod(r, 'transfer_items', unum, -13.5, 55.5, 'iron-plate', 40, 'from_chest')
print(f"  {res}")

inv = call_mod(r, 'get_character_inventory', unum)
print(f"  iron now: {next((it['count'] for it in inv['items'] if it['name'] == 'iron-plate'), 0)}")

# Wait helper
def wait():
    while True:
        time.sleep(1)
        st = call_mod(r, 'get_craft_status', unum)
        if st.get('status') != 'crafting':
            return st

print("\n=== crafting power chain ===")
# Pipes (15)
print("15 pipe..."); call_mod(r, 'craft', unum, 'pipe', 15); print(f"  {wait()}")
# Gears (12 for engine + pump + buffer)
print("12 iron-gear-wheel..."); call_mod(r, 'craft', unum, 'iron-gear-wheel', 12); print(f"  {wait()}")
# Copper-cable (8: 1 from each of 4 copper plates -> 8 cables; 6 needed for 2 circuits + 4 poles)
print("4 copper-cable batches (8 cables)..."); call_mod(r, 'craft', unum, 'copper-cable', 4); print(f"  {wait()}")
# Electronic-circuit (2 — pump needs 2)
print("2 electronic-circuit..."); call_mod(r, 'craft', unum, 'electronic-circuit', 2); print(f"  {wait()}")
# Small-electric-pole (2 batches = 4 poles)
print("2 small-electric-pole batches (4 poles)..."); call_mod(r, 'craft', unum, 'small-electric-pole', 2); print(f"  {wait()}")
# Boiler (uses our 1 stone-furnace + 4 pipe)
print("1 boiler..."); call_mod(r, 'craft', unum, 'boiler', 1); print(f"  {wait()}")
# Steam-engine
print("1 steam-engine..."); call_mod(r, 'craft', unum, 'steam-engine', 1); print(f"  {wait()}")
# Offshore-pump
print("1 offshore-pump..."); call_mod(r, 'craft', unum, 'offshore-pump', 1); print(f"  {wait()}")

inv = call_mod(r, 'get_character_inventory', unum)
print("\n=== final inventory ===")
for it in sorted(inv['items'], key=lambda x: -x['count']):
    print(f"  {it['name']}: {it['count']}")
r.close()
