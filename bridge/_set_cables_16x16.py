"""Configure 16x16 arena for cable task with iron+copper inputs."""
import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
spec = {
    'recipe_name': 'copper-cable',
    'output_item': 'copper-cable',
    'target_output': 40,  # 16x16 has room for 2-3 parallel chains; target pressures parallelism
    'input_items': [
        {'name': 'iron-plate', 'count': 30},   # row 4 input (distractor for cable task)
        {'name': 'copper-plate', 'count': 30}, # row 5 input (the real input)
    ],
    'sim_max_ticks': 3600,
}
print(json.dumps(call_mod(r, 'arena_set_task', spec, interface='claude_rl'), indent=2))
print('reset:', call_mod(r, 'arena_reset', interface='claude_rl'))
print('consts:', json.dumps(call_mod(r, 'arena_get_constants', interface='claude_rl'), indent=2)[:500])
r.close()
