# Staged for next mod deploy

Per [[feedback-batch-mod-changes]]: don't ship each change individually
to avoid restart churn. Bundle these into the next 0.9.8 deploy.

## 1. Multi-machine bonus (NEW)

JJ wants the agent to discover parallel chains. The speed_bonus alone
isn't strong enough — it only fires on reached=True, which a single
chain can rarely achieve at target_output=40.

Add to `arena_score`, around the activity_reward block:

```lua
-- Multi-machine bonus: pay extra for each ACTIVE assembler beyond the
-- first. Strongly incentivizes parallel chains.
local active_asms = components.active_assemblers or 0
if active_asms > 1 then
  local mm_bonus = (active_asms - 1) * 80  -- +80 per extra working asm
  components.multi_machine_bonus = mm_bonus
  total = total + mm_bonus
end
```

Cap implicitly via env's TYPE_CAPS for asm=6, so max bonus = 5 * 80 = +400.

## 2. Speed_bonus boost

Currently `speed_bonus = (sim_max_ticks - ticks_taken) * 0.1`. For
3600-tick sims with chain finishing at 2000 ticks, that's +160. Bumping
multiplier 0.1 → 0.3 makes the time pressure 3x stronger. With multi-
machine bonus, agent has clear gradient: more asms = faster = more
speed bonus.

```lua
local base = (a.sim_max_ticks - ticks_taken) * 0.3  -- was 0.1
```

## 3. Per-step extension bonus (consider)

Currently the per-step chain_bonus (in arena_place) rewards belt-to-
belt continuity at +3 each. Could boost to +6 if the placed belt is
within 2 tiles of the output loader row — pushing the agent to extend
the chain toward the loader specifically.

Not staged yet — measure cable16_v3 final behavior first to see if
this is needed.

## 4. 3rd input loader infrastructure (LATER)

Mastery stages (belt mastery, circuit mastery) need a 3rd input belt to
route distinct items separately. Currently 2 loaders (rows 7 and 8).
Add a 3rd loader at (-21, 79.5) row 9 when JJ is ready.

Bridge support already accepts multiple loaders via arena_setup (since 0.9.1).
Just needs placement in-game + bigger arena (might want 18x16 to fit a 3-asm chain).
