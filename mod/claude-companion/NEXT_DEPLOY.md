# Staged for next mod deploy

Per [[feedback-batch-mod-changes]]: don't ship each change individually
to avoid restart churn. Bundle these into the next mod deploy.

## Already shipped — historical reference

- **0.9.8** (cf7b107): belt continuity +1→+5 each side, loader-proximity
  belt bonus (+1 to +6 scaling), multi-machine bonus +80/extra asm,
  speed_bonus multiplier 0.1→0.3.
- **0.9.9** (af6976c): chain-completion bonuses boosted to give PPO a
  clear gradient toward reaching the loader:
  - reach_output_loader: 50 → 300
  - each output belt in chain: 5 → 10
  - direct asm→loader inserter: 60 → 200

## Still staged for next deploy (0.10.0 candidate)

### 1. 3rd input loader infrastructure (REQUIRES JJ in-game)

Mastery stages (belt mastery: iron-plate only; circuit mastery: iron+
copper plate; gear mastery: ore) need a 3rd input belt to route
distinct upstream items. Currently 2 loaders (rows 7 and 8).

Plan: JJ places a 3rd loader at `(-21, 79.5)` row 9 in-game (similar
to how he placed the 2nd), or the `bridge/_place_input3.py` script can
do it programmatically once we have a `_place_input2.py`-style version.

Bridge support already accepts multiple loaders via `arena_setup`
(since 0.9.1) and `arena_reset` distributes `input_items[i]` to
`input_chests[i]`.

If the 3-asm mastery chains feel cramped in 16×16, expand the arena
to 18×16 or 20×20. Would also need fresh BC v* with bigger demo.

### 2. Loader-proximity bonus tuning (depends on 0.9.9 outcome)

If belt v3 PPO under 0.9.9 STILL plateaus before chest delivery, the
loader-proximity scaling needs to ramp harder. Current `(7 - dx)` gives
+1 at dx=6, +6 at dx=1. Could:

- Make it `(7 - dx) * 3` so it scales +3 to +18 (3x).
- Or apply a multiplier ONLY when belt is on row 7 (= output loader's
  row) — punishing decorative belts on other rows.

Don't bundle until belt v3 result is in.

### 3. Per-asm recipe selection (NEXT — JJ asked for multi-product chains)

JJ said 2026-06-06: "I want it to build multiple-product chains like
cables+circuits". The canonical multi-product chain is:
  copper-plate → asm1 → copper-cable → asm2 → electronic-circuit
                                       ^ iron-plate also feeds in here
i.e. agent must build TWO assemblers with DIFFERENT recipes in the same
arena, route cables between them, and deliver circuits to the chest.

This unlocks the mastery curriculum stages and the bigger end-game from
ROADMAP_RL.txt (rocket from raw ore).

**Design**: re-use the action's `direction` field for asm placements as
a recipe index.

Action space stays MultiDiscrete([4, W*H, 4]). For asm (`entity_idx==2`),
`direction` now means recipe-index into `a.recipe_options`:
- dir=0 (N): recipes_options[1] (e.g. iron-gear-wheel)
- dir=1 (E): recipes_options[2] (e.g. copper-cable)
- dir=2 (S): recipes_options[3] (e.g. electronic-circuit)
- dir=3 (W): recipes_options[4] (e.g. transport-belt or unused)

For belts and inserters, direction stays directional.

**arena_set_task spec extension**:
```
{
  recipe_options = {
    [1] = 'copper-cable',
    [2] = 'electronic-circuit',
  },
  -- output_item / target_output now refers to the FINAL product
  output_item = 'electronic-circuit',
  target_output = 20,
  -- input_items as before; intermediate items NOT pre-provided once
  -- the agent has learned to make them (per JJ's compositional curriculum)
  input_items = [
    { name = 'iron-plate', count = 30 },
    { name = 'copper-plate', count = 60 },
  ],
}
```

For backward compat: if `recipe_options` is nil, fall back to current
single `recipe_name` behavior — all asms get the same recipe.

**arena_place asm branch**: if recipe_options is set, use
`a.recipe_options[dir_idx]` to look up the recipe. Otherwise default.

**Bridge changes (env.py)**:
- Action mask: when placing an asm, all 4 directions are still valid
  (each maps to a different recipe).
- Observation: probably want to encode "this tile has asm with recipe X"
  via per-recipe channels OR an additional per-tile encoding. Simplest
  path: extend asm channel (channel 9) into 4 channels (one per recipe),
  obs grows by 3 channels per tile = small.
- Demo encoding: existing demos use dir=0 for asm; new demos pick the
  correct dir for the intended recipe.

**Demo for circuit mastery** (iron + copper plate inputs, target circuit):
- asm cols 2-4 rows 7-9 dir=E (= copper-cable recipe)
- asm cols 8-10 rows 7-9 dir=S (= electronic-circuit recipe)
- input chain copper-plate row 8 → cable asm
- output of cable asm → inserter → belts → circuit asm input
- iron-plate row 7 → inserter → circuit asm
- circuit asm output → inserter → output belts → output loader

Demo is ~13-15 actions. Probably need fewer reps × more epochs in BC
since the demo is longer and more varied.

**Migration**: existing checkpoints (BC v4 cable, BC v3 belt, etc.) will
still load since the obs shape only grows; old asm-related obs slots
become "recipe-0" (whatever the default was).

### 4. Bridge auto-deploy script for arena placement

`_rebuild_16x16.py` + `_place_input2.py` are bespoke one-off scripts.
Future arena variations (bigger, more loaders, different recipes) would
benefit from a generic `arena_designer.py` that takes a spec and builds
it. Not urgent.

## Out of scope until something else lands

- New entity types (electric furnace, chemical plant, oil refinery,
  pumpjack) for Phase E/F roadmap stages. Would need:
  - Mod prototype mapping in `ENTITY_NAMES` (currently 0=belt, 1=ins,
    2=asm; add 3=furnace, 4=chem-plant, etc.)
  - Bridge action-space changes (MultiDiscrete `n_entities` grows)
  - Bigger obs (1 channel per entity-type)
  - Demos for each new entity
- Fluid entities (pipe, pumpjack output, oil refinery, etc.) — Phase F
  oil stages need this. Even more complex than solid entities.

These are all 0.11.0 / 0.12.0 territory; not staged.
