"""Switch the arena to the copper-cable task.

Inputs:  iron-plate=20 + copper-plate=20 (JJ wants both for now;
         iron is the 'distractor' that agent should learn to ignore)
Target:  copper-cable, 20 (each copper-plate makes 2 cables)
sim_max: 1800 ticks
"""

import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
spec = {
    'recipe_name': 'copper-cable',
    'output_item': 'copper-cable',
    'target_output': 20,
    'input_items': [
        {'name': 'iron-plate', 'count': 20},
        {'name': 'copper-plate', 'count': 20},
    ],
    'sim_max_ticks': 1800,
}
print('set_task:', json.dumps(call_mod(r, 'arena_set_task', spec, interface='claude_rl'), indent=2))
print('reset:', call_mod(r, 'arena_reset', interface='claude_rl'))
state = call_mod(r, 'arena_debug_state', interface='claude_rl')
print()
print('verify input chests:')
for ch in state.get('input_chests') or []:
    pos = ch.get('position')
    contents = ch.get('contents') or []
    if isinstance(contents, list):
        s = ', '.join(f"{c.get('name')}={c.get('count')}" for c in contents)
    else:
        s = 'empty'
    print(f"  @ {pos}: {s}")
r.close()
