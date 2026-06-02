import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
res = call_mod(r, 'arena_set_config',
               {'target_output': 10, 'sim_max_ticks': 1800, 'refill_amount': 20},
               interface='claude_rl')
print('patch:', res)
print('verify:', call_mod(r, 'arena_get_constants', interface='claude_rl'))
r.close()
