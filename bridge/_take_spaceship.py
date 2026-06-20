"""Take spaceship contents (200 firearm-magazines) + the spaceship's own mining
products (iron-plate, copper-plate, etc), then destroy it. This bypasses the
distance-to-center reach check on a large entity."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = game.surfaces['nauvis']; "
    "local ship = s.find_entities_filtered{position={-5,-6}, radius=3, name='crash-site-spaceship'}[1]; "
    "if not ship then rcon.print('NO SHIP'); return end; "
    "local inv = c.get_main_inventory(); "
    "local lines = {}; "
    # Transfer contents of ships output inventory to character
    "local oi = ship.get_output_inventory(); "
    "if oi then "
    "  for _, st in ipairs(oi.get_contents()) do "
    "    local moved = inv.insert{name=st.name, count=st.count}; "
    "    table.insert(lines, 'took ' .. moved .. ' ' .. st.name .. ' from ship'); "
    "  end; "
    "  oi.clear(); "
    "end; "
    # Mine the ship itself (gives back materials from mineable_properties.products)
    "local mp = ship.prototype.mineable_properties; "
    "if mp and mp.products then "
    "  for _, p in ipairs(mp.products) do "
    "    local amt = p.amount or p.amount_max or 1; "
    "    if not p.probability or math.random() < p.probability then "
    "      local moved = inv.insert{name=p.name, count=amt}; "
    "      table.insert(lines, 'mined ' .. moved .. ' ' .. p.name); "
    "    end; "
    "  end; "
    "end; "
    "ship.destroy(); "
    "rcon.print(table.concat(lines, ' | '))"
))

inv = call_mod(r, 'get_character_inventory', unum)
print("\n=== inventory after spaceship loot ===")
for it in sorted(inv['items'], key=lambda x: -x['count']):
    print(f"  {it['name']}: {it['count']}")
r.close()
