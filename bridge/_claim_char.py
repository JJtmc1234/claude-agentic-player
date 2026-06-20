"""Claim an existing free-standing character as Claude's, top up inventory."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

TARGET_UNUM = 437827

r = RconClient(); r.connect()
# Set storage pointer + check current inventory
print(r.command(
    "/silent-command "
    f"storage.claude_char_unum = {TARGET_UNUM}; "
    f"local c = game.get_entity_by_unit_number({TARGET_UNUM}); "
    "if not (c and c.valid) then rcon.print('TARGET MISSING'); return end; "
    "local inv = c.get_main_inventory(); "
    "local lines = {string.format('claimed unum=%d at (%.1f,%.1f)', c.unit_number, c.position.x, c.position.y)}; "
    "if inv then "
    "  for _, st in ipairs(inv.get_contents()) do "
    "    table.insert(lines, '  ' .. st.name .. ': ' .. st.count) "
    "  end "
    "end; "
    "rcon.print(table.concat(lines, '\\n'))"
))
# Top up if needed
print("\ntopping up inventory...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({TARGET_UNUM}); "
    "local inv = c.get_main_inventory(); "
    "if inv then "
    "  local function ensure(name, target) "
    "    local have = inv.get_item_count(name); "
    "    if have < target then inv.insert{name=name, count=target-have} end "
    "  end; "
    "  ensure('iron-plate', 50); "
    "  ensure('wood', 50); "
    "  ensure('stone', 20); "
    "  ensure('burner-mining-drill', 2); "
    "  ensure('stone-furnace', 2); "
    "  ensure('wooden-chest', 5); "
    "end; "
    "rcon.print('topped up')"
))
r.close()
