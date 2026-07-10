"""
Self-bootstrapping blueprint BUILD engine (JJ's hosted 2.0 SE burner base).

Turns the team into a burner-base builder that mines only what the build needs,
then smelts, fabricates and revives JJ's placed ghosts:

  MINE (buffered -- only when stock is low, so they don't "just mine"):
    builder 187 -> coal (fuel),  scout 1584 -> stone (furnaces),
    miner 186 -> iron-ore (plates).  courier 188 fabricates instead of mining.
  STATION: rebuild/keep 6 smelting furnaces at fixed coords (scout crafts them
    from its stone + places them, one op/cycle).
  SMELT: feed furnaces iron-ore(186)+coal(187); collect iron-plate -> supply chest.
  FABRICATE (courier 188): tiered gear->motor->stick->{iron-chest,burner-inserter,
    transport-belt} toward the plate-only ghosts first. Craft-status guarded.
  BUILD (courier 188): park at the blueprint, revive any ghost it has the item for.
  DEFENSE: builder crafts magazines; top up gun-turrets.

Unums re-resolve if changed: miner=186 builder=187 courier=188 scout=1584.
Run in background; TaskStop to end.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _exec import _ensure_password  # noqa: E402
from rcon_client import RconClient  # noqa: E402

_ensure_password()

CHEST = "(s.find_entities_filtered{name='iron-chest',position={-38,-40},radius=3,limit=1})[1]"

# Buffered mining + station rebuild + smelt, all in one server-side pass.
MINE_SMELT = (
    "/silent-command "
    "local s=game.surfaces['nauvis']; local chest=" + CHEST + "; "
    "local function remine(u,res,thresh) "
    "  local c=game.get_entity_by_unit_number(u); if not(c and c.valid) then return end; "
    "  if c.get_main_inventory().get_item_count(res)>=thresh then return end; "
    "  local ms=remote.call('claude','get_mining_status',u); if ms.mining then return end; "
    "  local es=s.find_entities_filtered{name=res,position=c.position,radius=64}; local best,bd=nil,1e18; "
    "  for _,e in ipairs(es) do local dx=e.position.x-c.position.x; local dy=e.position.y-c.position.y; local d=dx*dx+dy*dy; if d<bd then bd=d;best=e end end; "
    "  if best then local r=remote.call('claude','start_mining',u,best.position.x,best.position.y); if not(r and r.ok) then remote.call('claude','walk_to',u,best.position.x,best.position.y) end end "
    "end; "
    "remine(187,'coal',300); remine(1584,'stone',150); remine(186,'iron-ore',300); "
    "local coords={{-46,-40},{-44,-40},{-42,-40},{-40,-40},{-46,-38},{-44,-38},{-52,-40},{-46,-36}};"
    "for _,p in ipairs(coords) do "
    "  local f=(s.find_entities_filtered{name='stone-furnace',position={p[1],p[2]},radius=0.6,limit=1})[1]; "
    "  if not f then local sc=game.get_entity_by_unit_number(1584); if sc and sc.valid then local si=sc.get_main_inventory(); "
    "      if si.get_item_count('stone-furnace')>=1 then remote.call('claude','place_entity',1584,'stone-furnace',p[1],p[2],0) "
    "      elseif si.get_item_count('stone')>=5 then remote.call('claude','craft',1584,'stone-furnace',3) end end; break end "
    "end; "
    "for _,p in ipairs(coords) do "
    "  local f=(s.find_entities_filtered{name='stone-furnace',position={p[1],p[2]},radius=0.6,limit=1})[1]; "
    "  if f then "
    "    if f.get_inventory(defines.inventory.fuel).get_item_count('coal')<5 then remote.call('claude','insert_into_entity',187,p[1],p[2],'coal',20,defines.inventory.fuel) end; "
    "    if f.get_inventory(defines.inventory.furnace_source).get_item_count('iron-ore')<10 then remote.call('claude','insert_into_entity',186,p[1],p[2],'iron-ore',30,defines.inventory.furnace_source) end; "
    "    if chest and f.get_inventory(defines.inventory.furnace_result).get_item_count('iron-plate')>0 then remote.call('claude','take_from_entity',186,p[1],p[2],'iron-plate',100,defines.inventory.furnace_result); remote.call('claude','transfer_items',186,chest.position.x,chest.position.y,'iron-plate',1000,'to_chest') end "
    "  end "
    "end"
)

FAB = (
    "/silent-command "
    "local s=game.surfaces['nauvis']; local u=188; local c=game.get_entity_by_unit_number(u); if not(c and c.valid) then return end; "
    "local ci=c.get_main_inventory(); local cs=remote.call('claude','get_craft_status',u); if cs.status=='crafting' then return end; "
    "local chest=" + CHEST + "; if chest and ci.get_item_count('iron-plate')<80 then remote.call('claude','transfer_items',u,chest.position.x,chest.position.y,'iron-plate',150,'from_chest') end; "
    "local plate=ci.get_item_count('iron-plate'); local gear=ci.get_item_count('iron-gear-wheel'); local motor=ci.get_item_count('motor'); local stick=ci.get_item_count('iron-stick'); "
    "local function cr(rec,n) remote.call('claude','craft',u,rec,n) end; "
    "if plate<24 then return end; "
    "if gear<24 and plate>=60 then cr('iron-gear-wheel',24) return end; "
    "if motor<16 and gear>=16 then cr('motor',16) return end; "
    "if stick<32 and plate>=48 then cr('iron-stick',32) return end; "
    "if motor>=8 and stick>=16 then cr('burner-inserter',8) return end; "
    "if plate>=80 then cr('iron-chest',8) return end; "
    "if motor>=8 then cr('transport-belt',8) return end"
)

BUILD = (
    "/silent-command "
    "local u=188; local c=game.get_entity_by_unit_number(u); if not(c and c.valid) then return end; "
    "local cx,cy=7,-34; local dx=c.position.x-cx; local dy=c.position.y-cy; "
    "if dx*dx+dy*dy>361 then remote.call('claude','walk_to',u,cx,cy); rcon.print('walking-to-site') return end; "
    "local r=remote.call('claude','build_ghosts_in_range',u,26); "
    "rcon.print('BUILT='..#(r.built or {})..' missing='..#(r.missing or {})..' seen='..(r.ghosts_seen or 0))"
)

DEFENSE = (
    "/silent-command "
    "local s=game.surfaces['nauvis']; local b=game.get_entity_by_unit_number(187); if not(b and b.valid) then return end; "
    "local bi=b.get_main_inventory(); local cs=remote.call('claude','get_craft_status',187); local chest=" + CHEST + "; "
    "if cs.status~='crafting' and bi.get_item_count('firearm-magazine')<30 then "
    "  if chest and bi.get_item_count('iron-plate')<120 then remote.call('claude','transfer_items',187,chest.position.x,chest.position.y,'iron-plate',160,'from_chest') end; "
    "  if bi.get_item_count('iron-plate')>=40 then remote.call('claude','craft',187,'firearm-magazine',30) end end; "
    "local mags=bi.get_item_count('firearm-magazine'); "
    "for _,t in ipairs(s.find_entities_filtered{name='gun-turret'}) do if mags<=0 then break end; local ta=t.get_inventory(defines.inventory.turret_ammo); "
    "  if ta and ta.get_item_count('firearm-magazine')<10 then local m=ta.insert{name='firearm-magazine',count=math.min(10,mags)}; if m>0 then bi.remove{name='firearm-magazine',count=m}; mags=mags-m end end end"
)


def main() -> int:
    period = 0.8
    cyc = 0
    while True:
        try:
            with RconClient() as r:
                # No chat announce -- build silently (JJ: stop the "BUILD MODE" spam).
                while True:
                    r.command(MINE_SMELT)
                    if cyc % 5 == 0:
                        r.command(FAB)
                    if cyc % 9 == 0:
                        r.command(BUILD)
                    if cyc % 40 == 0:
                        r.command(DEFENSE)
                    cyc += 1
                    time.sleep(period)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[build] rcon error: {e}; reconnecting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
