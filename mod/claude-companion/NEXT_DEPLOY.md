# Staged changes for next mod deploy

These are improvements I want in the next bump (probably 0.9.0 or 0.8.21).
Per [[feedback-batch-mod-changes]], DON'T deploy each one separately — wait
until JJ asks for the next restart, then ship them all in one version bump.

## Pending list

### 1. Action mask: assembler footprint
`arena_get_observation` could include per-tile valid-asm flag (3x3 fits in
bounds). Bridge could mask out tile indices where the asm anchor would put
the 3x3 outside bounds. Saves ~30 invalid_action penalties per episode in
the worst case.

Implementation:
- Add to obs.globals or a new "valid_asm_tiles" mask field.
- Bridge masked_env consumes it when entity_choice == 2.

### 2. `arena_apply_layout` remote
For BC eval / scripted layout testing, place all entities in one RCON call
instead of N. Saves ~25 round-trips per episode (~5 sec).

Signature:
```lua
arena_apply_layout({ actions = { {ec, ti, d}, {ec, ti, d}, ... } })
  -> { ok, placed = N, errors = [...] }
```

### 3. Cables curriculum (was 0.9.0 plan)
Apply circuit_changes.lua draft:
- storage.arena.recipe_name (default 'iron-gear-wheel')
- storage.arena.input_items list (replaces single input_item)
- arena_reset uses input_items if present
- arena_place sets recipe from a.recipe_name (already done in 0.8.15)
- NEW remote `arena_set_task(spec)` for switching task mid-session

### 4. Speed up `arena_get_observation`
Currently does `find_entities_filtered` over the whole arena every call.
For 8×8 that's 64 tiles × a few entities each = ~100 entity scans. Could
maintain a cached grid in storage that updates on arena_place / arena_reset.

### 5. Better display panel text
combinator_description renders but may be too narrow. Try multi-line via
`\n` in one panel instead of stacked entities; or just go back to
rendering.draw_text but track ids more carefully.

### 6. (Optional) Make arena_reset idempotent across mod-version migrations
If the storage layout changes between mod versions, `init_arena` should
migrate the existing storage instead of starting fresh. Useful when JJ's
save has lots of in-progress state.

## When NOT pending
- Reward shaping changes (done; let the agent learn the current setup first).
- Display panel position/style (working now).
- Per-step chain_bonus values (calibrated, leave alone until eval shows otherwise).
