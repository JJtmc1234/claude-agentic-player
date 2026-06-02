import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
spec = {
    'recipe_name': 'electronic-circuit',
    'output_item': 'electronic-circuit',
    'target_output': 10,
    'input_items': [
        {'name': 'iron-plate', 'count': 20},
        {'name': 'copper-cable', 'count': 60},
    ],
    'sim_max_ticks': 1800,
}
print('arena_set_task:', call_mod(r, 'arena_set_task', spec, interface='claude_rl'))
print()
print('arena state:')
state = call_mod(r, 'arena_debug_state', interface='claude_rl')
import json
print(json.dumps(state, indent=2)[:2000])
r.close()
