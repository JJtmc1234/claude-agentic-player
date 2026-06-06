"""Probe what's at col 13-16 row 7 to debug output flow."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "for col = 13, 17 do "
       "  local x = -20 + col + 0.5; "
       "  local y = 77.5; "
       "  local ents = s.find_entities_filtered{position={x, y}, radius=0.4}; "
       "  rcon.print('col ' .. col .. ' (' .. x .. ',' .. y .. '):'); "
       "  for _, e in ipairs(ents) do "
       "    if e.valid then "
       "      local items = ''; "
       "      if e.type == 'transport-belt' then "
       "        for i = 1, e.get_max_transport_line_index() do "
       "          local tl = e.get_transport_line(i); "
       "          if tl then "
       "            for _, st in ipairs(tl.get_contents()) do "
       "              items = items .. ' ' .. st.name .. '=' .. st.count "
       "            end "
       "          end "
       "        end "
       "      end "
       "      rcon.print('  ' .. e.name .. ' dir=' .. e.direction .. items) "
       "    end "
       "  end "
       "end")
print(r.command(cmd))
r.close()
