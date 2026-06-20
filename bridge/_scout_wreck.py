"""Find crash-site entities near spawn + show contents."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local ents = s.find_entities_filtered{position={-15, 0}, radius=60}; "
    "for _, e in ipairs(ents) do "
    "  if e.valid and string.find(e.name, 'crash') then "
    "    local inv_str = ''; "
    "    local oi = nil; "
    "    pcall(function() oi = e.get_output_inventory() end); "
    "    if oi then "
    "      for _, st in ipairs(oi.get_contents()) do "
    "        inv_str = inv_str .. ' [' .. st.name .. ':' .. st.count .. ']' "
    "      end "
    "    end; "
    "    local minable = e.prototype.mineable_properties.minable; "
    "    rcon.print(string.format('%s at (%.1f, %.1f) minable=%s inv=%s', "
    "      e.name, e.position.x, e.position.y, tostring(minable), inv_str)) "
    "  end "
    "end"
))
r.close()
