"""
Team growth engine for JJ's hosted 2.0 SE world.

Two jobs per cycle, all server-side Lua so the Python side just re-sends it:

  MINING (bulk raw materials): miner(186)->iron-ore, builder(187)->coal,
    courier(188)->copper-ore. Each start_mining yields ONE ore then clears, so
    we re-arm any idle char with the nearest ore of its type (walk to it if the
    nearest tile fell out of reach).

  GHOST BUILDING (scout 189): JJ places entity-ghosts live. Scout keeps a stock
    of stone-furnace items (crafts a batch when it runs out) and revives any
    stone-furnace ghost it can reach, roaming toward the nearest ghost cluster.
    (Drill/other ghosts need a smelted-plate production run -- added later.)

Roster unums change on death/respawn -- update MINE/SCOUT below if so.
Run in background; TaskStop to end.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _exec import _ensure_password  # noqa: E402
from rcon_client import RconClient  # noqa: E402

_ensure_password()

LUA = r"""
local s=game.surfaces['nauvis']
-- ---- bulk mining ----
local mine={[186]='iron-ore',[188]='copper-ore'}
for u,t in pairs(mine) do
  local c=game.get_entity_by_unit_number(u)
  if c and c.valid and c.type=='character' then
    local ms=remote.call('claude','get_mining_status',u)
    if not ms.mining then
      local near=s.find_entities_filtered{name=t,position=c.position,radius=48}
      local best,bd=nil,1e18
      for _,e in ipairs(near) do
        local dx=e.position.x-c.position.x; local dy=e.position.y-c.position.y
        local d=dx*dx+dy*dy
        if d<bd then bd=d; best=e end
      end
      if best then
        local r=remote.call('claude','start_mining',u,best.position.x,best.position.y)
        if not (r and r.ok) then remote.call('claude','walk_to',u,best.position.x,best.position.y) end
      end
    end
  end
end
-- ---- smelting station upkeep: keep the 6 furnaces fed, plates -> supply chest ----
-- No distance check on insert/take, so the mining chars feed the station from
-- wherever they are: builder(187) fuels with coal, miner(186) feeds iron-ore,
-- courier(188) feeds copper-ore + hauls finished plates into the supply chest.
local ironF={{-46,-40},{-44,-40},{-42,-40},{-40,-40}}
local copF={{-46,-38},{-44,-38}}
local chest=(s.find_entities_filtered{name='iron-chest',position={-38,-40},radius=3,limit=1})[1]
local function tend(p, feeder, ore, plate)
  local f=(s.find_entities_filtered{name='stone-furnace',position={p[1],p[2]},radius=0.6,limit=1})[1]
  if not f then return end
  if f.get_inventory(defines.inventory.fuel).get_item_count('coal')<5 then
    remote.call('claude','insert_into_entity',187,p[1],p[2],'coal',20,defines.inventory.fuel)
  end
  if f.get_inventory(defines.inventory.furnace_source).get_item_count(ore)<10 then
    remote.call('claude','insert_into_entity',feeder,p[1],p[2],ore,30,defines.inventory.furnace_source)
  end
  local res=f.get_inventory(defines.inventory.furnace_result)
  if res.get_item_count(plate)>0 and chest then
    remote.call('claude','take_from_entity',188,p[1],p[2],plate,100,defines.inventory.furnace_result)
    remote.call('claude','transfer_items',188,chest.position.x,chest.position.y,plate,1000,'to_chest')
  end
end
for _,p in ipairs(ironF) do tend(p,186,'iron-ore','iron-plate') end
for _,p in ipairs(copF) do tend(p,188,'copper-ore','copper-plate') end
-- ---- defense: top up every gun-turret from courier's crafted magazines ----
local cr8=game.get_entity_by_unit_number(188)
if cr8 and cr8.valid then
  local ci=cr8.get_main_inventory()
  local mags=ci.get_item_count('firearm-magazine')
  if mags>0 then
    for _,t in ipairs(s.find_entities_filtered{name='gun-turret'}) do
      if mags<=0 then break end
      local ta=t.get_inventory(defines.inventory.turret_ammo)
      if ta and ta.get_item_count('firearm-magazine')<10 then
        local put=math.min(10,mags)
        local m=ta.insert{name='firearm-magazine',count=put}
        if m>0 then ci.remove{name='firearm-magazine',count=m}; mags=mags-m end
      end
    end
  end
end
rcon.print('t'..game.tick)
"""

CMD = "/silent-command " + LUA

# Rotating, grounded next-step suggestions the team pipes into chat so JJ + his
# friend always see what we can do next. Kept to what's actually unlocked
# (burner tech; electricity/belts/circuits are still research-gated here).
SUGGESTIONS = [
    "[Builder] Idea: add a couple burner-assemblers to auto-craft drills/gears/motors so the base scales without hand-crafting.",
    "[Scout] I can range out for a richer iron/copper patch or find the next resource we need -- just point a direction.",
    "[Miner] Biggest unlock next is electricity (boiler/steam) -- it is research-gated, so keeping the labs fed jumps us to electric drills + belts.",
    "[Courier] I can haul plates/ore between your builds or keep a supply chest stocked for you and your friend.",
    "[Claude team] Place ghosts and we build them; point us at ore and we mine it. Happy to help you and your friend both.",
]


def _say(r, msg):
    esc = msg.replace("\\", "\\\\").replace("'", "\\'")
    lua = "game.print('" + esc + "', {color={r=0.6,g=0.85,b=1}})"
    r.command("/silent-command " + lua)


# Keep courier stocked with magazines to feed the turrets. Guarded on craft
# status so we never reset a running craft job. Pulls plates from the supply
# chest as needed. iron-plate x4 -> 1 magazine.
AMMO_CRAFT = (
    "/silent-command "
    "local c=game.get_entity_by_unit_number(188); "
    "if c and c.valid then "
    "  local ci=c.get_main_inventory(); "
    "  local cs=remote.call('claude','get_craft_status',188); "
    "  if cs.status~='crafting' and ci.get_item_count('firearm-magazine')<40 then "
    "    local ch=(game.surfaces['nauvis'].find_entities_filtered{name='iron-chest',position={-38,-40},radius=3,limit=1})[1]; "
    "    if ch then "
    "      if ci.get_item_count('iron-plate')<160 then remote.call('claude','transfer_items',188,ch.position.x,ch.position.y,'iron-plate',240,'from_chest') end; "
    "      if ci.get_item_count('iron-plate')>=40 then remote.call('claude','craft',188,'firearm-magazine',40) end "
    "    end "
    "  end "
    "end"
)


def main() -> int:
    period = 0.8
    suggest_every = 225  # ~3 min at 0.8s/cycle
    ammo_every = 75      # ~60s: re-craft magazines when courier is low
    cyc = 0
    sidx = 0
    while True:
        try:
            with RconClient() as r:
                while True:
                    r.command(CMD)
                    cyc += 1
                    if cyc % ammo_every == 0:
                        try:
                            r.command(AMMO_CRAFT)
                        except Exception:  # noqa: BLE001
                            pass
                    # Chat auto-suggestions removed (JJ: "they keep repeating
                    # random stuff") -- only speak on real events now.
                    time.sleep(period)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[engine] rcon error: {e}; reconnecting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
