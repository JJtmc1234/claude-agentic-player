"""Verify both production lines flowing; show chest counts over 30s."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()

# Locations: iron chest at (-13.5, 55.5); copper chest at (-10.5, 55.5)
# coal chest at (45.5, -38.5); coal-drill at (45, -41)
def status_block(label):
    print(f"\n--- {label} ---")
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local function chest_count(x, y, item) "
        "  local ch = s.find_entities_filtered{position={x,y}, radius=0.5, name='wooden-chest'}[1]; "
        "  if not ch then return -1 end; "
        "  local inv = ch.get_inventory(defines.inventory.chest); "
        "  if not inv then return -2 end; "
        "  return inv.get_item_count(item) "
        "end; "
        "local ip = chest_count(-13.5, 55.5, 'iron-plate'); "
        "local cp = chest_count(-10.5, 55.5, 'copper-plate'); "
        "local kp = chest_count(45.5, -38.5, 'coal'); "
        "local cins = s.find_entities_filtered{position={-10.5, 54.5}, radius=0.5, name='burner-inserter'}[1]; "
        "local kd = s.find_entities_filtered{position={45, -41}, radius=0.5, name='burner-mining-drill'}[1]; "
        "local ground_coal = s.find_entities_filtered{position={45, -39}, radius=1.5, name='item-on-ground'}; "
        "local ground_n = 0; "
        "for _, g in ipairs(ground_coal) do "
        "  if g.stack and g.stack.valid_for_read and g.stack.name == 'coal' then "
        "    ground_n = ground_n + g.stack.count "
        "  end "
        "end; "
        "rcon.print(string.format('iron_chest=%d | copper_chest=%d (ins=%s) | coal_chest=%d (drill=%s, ground=%d)', "
        "  ip, cp, cins and cins.status or '?', kp, kd and kd.status or '?', ground_n))"
    ))

for i, t in enumerate([0, 15, 30]):
    if t > 0: time.sleep(15)
    status_block(f"t+{t}s")
r.close()
