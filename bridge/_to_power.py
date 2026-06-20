"""Walk to base, gather copper plates, craft power infrastructure, build it on water.

Power chain needed:
- offshore-pump (1 circuit + 1 gear + 1 pipe) — on water tile
- pipes connecting pump -> boiler
- boiler (1 stone-furnace + 4 pipe) — converts water+coal -> steam
- steam-engine (8 gear + 10 iron + 5 pipe) — converts steam -> power
- small-electric-poles (1 wood + 2 copper-cable each) — connect things
- electronic-circuit (3 copper-cable + 1 iron-plate)
- copper-cable (1 copper-plate -> 2 copper-cable)
- pipe (1 iron-plate)
- iron-stick (1 iron -> 2 sticks; needed for boilers? actually no)

Recipe check (2.0):
- pipe: 1 iron-plate -> 1 pipe
- copper-cable: 1 copper-plate -> 2 cable
- electronic-circuit: 3 cable + 1 iron-plate -> 1 circuit
- small-electric-pole: 1 wood + 1 copper-cable -> 2 pole (2.0)
- offshore-pump: 3 pipe + 2 electronic-circuit + 1 iron-gear-wheel (varies)
- boiler: 1 stone-furnace + 4 pipe -> 1 boiler
- steam-engine: 10 iron-gear-wheel + 5 iron-plate + 5 pipe

For ONE working setup: 1 pump + 1 boiler + 1 engine + ~3 poles + connectors
Approx iron needed: 5(engine) + 5(pipe for engine) + 4(pipe for boiler) + 3(pipe for pump path) + 10(gears for engine) + 1(circuit base) + 1(gear for pump) ~ 30 iron
Copper needed: 1 (cable for circuit) + 2 (cable for poles) = 3 copper-plate
Stone: 0 (boiler uses an EXISTING furnace as ingredient, but we want to keep our smelters)
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

print("=== walk back to base ===")
call_mod(r, 'walk_to', unum, -11, 56, 2.0)
for i in range(120):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 10 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st.get('status')}")
    if st.get('status') in ('completed', 'error', 'idle'): break
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# Take copper plates from copper chest at (-10.5, 54.5)
print("\n=== pull copper plates from base chest ===")
res = call_mod(r, 'transfer_items', unum, -10.5, 54.5, 'copper-plate', 8, 'from_chest')
print(f"  {res}")

# Find nearest water for offshore pump location
print("\n=== finding water ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
    "local water_tiles = s.find_tiles_filtered{position=c.position, radius=50, name={'water', 'deepwater'}}; "
    "if #water_tiles == 0 then rcon.print('NO WATER NEAR'); return end; "
    "local best, bd = nil, 1e9; "
    "for _, t in ipairs(water_tiles) do "
    "  local dx = t.position.x - c.position.x; local dy = t.position.y - c.position.y; "
    "  local d = dx*dx + dy*dy; "
    "  if d < bd then bd = d; best = t end "
    "end; "
    "rcon.print(string.format('nearest water at (%.1f, %.1f) dist=%.1f', "
    "  best.position.x, best.position.y, math.sqrt(bd)))"
))
r.close()
