"""Find Claude's character (free-standing, no player_index) and report state."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
# Find all characters on nauvis
print("=== all characters on nauvis ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local chars = s.find_entities_filtered{name='character'}; "
    "for _, c in ipairs(chars) do "
    "  if c.valid then "
    "    local owner = 'free'; "
    "    if c.player then owner = 'player:' .. c.player.name end; "
    "    rcon.print(string.format('char unum=%d pos=(%.1f,%.1f) owner=%s', "
    "      c.unit_number, c.position.x, c.position.y, owner)) "
    "  end "
    "end"
))
print("=== players ===")
print(r.command(
    "/silent-command "
    "for _, p in pairs(game.players) do "
    "  local pos = p.character and p.character.position or {x=0,y=0}; "
    "  rcon.print('player ' .. p.name .. ' connected=' .. tostring(p.connected) .. "
    "             ' has_char=' .. tostring(p.character ~= nil)) "
    "end"
))
r.close()
