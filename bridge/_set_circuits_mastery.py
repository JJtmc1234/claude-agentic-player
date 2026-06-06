"""Configure the 16x16 arena for the circuit MASTERY task (multi-product).

Recipe options: copper-cable (dir=0), electronic-circuit (dir=1).
Output: electronic-circuit.
Inputs: iron-plate (row 7 loader) + copper-plate (row 8 loader).
"""
import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
spec = {
    'recipe_name': 'electronic-circuit',  # default for non-direction asms (none here)
    # List, NOT dict — lua_repr turns dicts into string-keyed tables, but the
    # mod expects integer keys (a.recipe_options[dir_idx + 1]).
    'recipe_options': ['copper-cable', 'electronic-circuit'],
    'output_item': 'electronic-circuit',
    'target_output': 20,
    'input_items': [
        {'name': 'iron-plate', 'count': 30},
        {'name': 'copper-plate', 'count': 60},
    ],
    'sim_max_ticks': 3600,
}
res = call_mod(r, 'arena_set_task', spec, interface='claude_rl')
print(json.dumps(res, indent=2))
print()
print('reset:', call_mod(r, 'arena_reset', interface='claude_rl'))
r.close()
