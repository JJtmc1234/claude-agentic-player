# Power chain — design notes and discovery-driven deploy procedure

Status: **DRAFT — not yet successfully deployed in-game.** Day 2 of agentic
play (2026-06-20) got pump + boiler + engine + pole crafted and individually
placed, but their pipe topology didn't connect. This doc captures what we
learned about 2.0's constraints so the next deploy attempt is precise.

## The three hard constraints

### 1. offshore-pump direction is **auto-detected by terrain**, not the `direction` arg

Verified empirically: rotating `pump.direction` after placement produced no
change in the pump's `fluidbox.get_pipe_connections(1)[1].target_position`.
The target stayed at `(pump_x - 1, pump_y)` regardless of direction value 0/4/8/12.

Conclusion: the pump auto-orients to the nearest LAND side. To force a
particular output direction, **place the pump on a water tile where only the
desired side is land**. Or: place it anywhere and read the actual output
target from `fluidbox.get_pipe_connections` before laying pipes.

### 2. boiler 3×2 water inputs are perpendicular to flow, not collinear

For a boiler at center `(bx, by)` with `direction = DIR_EAST (4)` (steam flows east):
- Footprint: 3 wide (E-W) × 2 tall (N-S), tiles `(bx-1..bx+1) × (by..by+1)`
- **Water input 1** at `(bx-0.5, by-0.5)` targets pipe at `(bx-0.5, by-1.5)` — **NORTH of west tile**
- **Water input 2** at `(bx-0.5, by+1.5)` targets pipe at `(bx-0.5, by+2.5)` — **SOUTH of west tile**
- **Steam output** at `(bx+1.5, by+0.5)` targets pipe at `(bx+2.5, by+0.5)` — east of east tile

This means you CAN'T put a boiler "in line" with the pump and expect it to
receive water from a pipe directly west. You must elbow the pipes north or
south to hit one of the perpendicular input ports.

### 3. steam-engine 2×3 steam input is collinear with flow direction

For an engine at center `(ex, ey)` with `direction = DIR_EAST (4)`:
- Footprint: 3 wide (E-W) × 2 tall (N-S)
- **Steam input** on the west end
- **Electricity output** is implicit (small-electric-pole within 7.5 tiles)

So the engine CAN sit directly east of the boiler with steam flowing
straight across — that part is clean.

## Layout that should work

Given pump at water tile `(px, py)` with land to the east:

```
                                  pole
        (out of frame, ~7 tiles from engine)
                                    │
y-1     ╔═══════════════════════════╧═══════════════════════════════╗
y       ║ pump ⟶ pipe ⟶ ┐                                         ║
y+1     ║              elbow ⟶ pipe                                ║
y+2     ║                       ↓                                   ║
y+3     ║              ┌─────boiler─────┐ ⟶ pipe ⟶ ┌──engine──┐  ║
y+4     ║              │                │           │           │  ║
y+5     ║              └────────────────┘           └───────────┘  ║
        ╚══════════════════════════════════════════════════════════╝
```

But that's hand-waved. The **real** layout depends on which pipe-connection
target the pump exposes after placement. Use the discovery procedure below.

## Discovery-driven deploy procedure

1. **Place offshore-pump on water tile.** Direction is ignored. Just put it down.

   ```python
   pump = agent.place('offshore-pump', water_x, water_y, 0)
   ```

2. **Query the pump's fluid connection** to learn where it expects a pipe.

   ```lua
   local p = surface.find_entities_filtered{position={px,py}, name='offshore-pump'}[1]
   local conn = p.fluidbox.get_pipe_connections(1)[1]
   -- conn.target_position is where pipe #1 must go
   ```

3. **Place pipe at `conn.target_position`.** If that target is on water, the
   pump is mis-placed — try a different water tile until target is land.

4. **Extend pipes** toward where the boiler will go. Stay one tile away from
   the eventual boiler footprint for now.

5. **Place boiler** with `direction = DIR_EAST` so its water inputs are
   N+S of its west column. Query `boiler.fluidbox.get_pipe_connections` and
   verify the water-input target lines up with your last pipe.

6. **Connect boiler water input** with a pipe elbow if needed (the pump
   line goes straight; the boiler input is N or S of that line, so 1-2 pipes
   form an L).

7. **Place steam-engine** east of boiler with `direction = DIR_EAST`. The
   engine's steam-input target should equal `boiler.fluidbox.get_pipe_connections(2)[1].target_position`
   (which is `(bx+2.5, by+0.5)` per §2). Place a pipe at that target.

8. **Place a small-electric-pole** within ~7 tiles of the engine — that's
   the engine's connection radius. The pole will auto-receive power.

9. **Fuel the boiler** with coal (preferred) or wood. Boiler `status = 1`
   means working; `status = 32` (no fuel) means add fuel; `status = 27`
   (missing fluid) means the water pipeline isn't connected.

10. **Verify**: `engine.energy_generated_last_tick > 0` confirms power is
    flowing. The pole's `electric_network_id` should match the engine's.

## Status codes to look for (decoded from `defines.entity_status`)

| Code | Name | What it means for this chain |
|---|---|---|
| 1 | working | Good. |
| 12 | full_output | Boiler steam-out is blocked — engine isn't draining. |
| 17 | no_power | Pole isn't connected to any generator. |
| 19 | no_fuel | Boiler fuel slot is empty. |
| 27 | missing_required_fluid | Boiler has no water (pipeline broken). |
| 32 | waiting_for_source_items | n/a for power (this is inserter language). |
| 34 | waiting_for_space_in_destination | n/a for power. |

## Why this isn't auto-solvable in `plan_power_chain`

The pump's auto-direction means we can't compute the layout fully ahead of
time without knowing the terrain. The library's `plan_power_chain` returns
just the pump placement; the rest needs to be discovered at deploy time
via the procedure above. Could be made fully autonomous by:

1. Walking the water/land edge and finding a water tile whose pump output
   would land on land in a chosen direction.
2. Computing boiler+engine positions from that constraint.
3. Computing pipe-routing between them.

That's a ~150-line solver — worth doing if power becomes a regular pattern
to deploy. For now, do it once manually with the discovery procedure,
then back-port the working coordinates into a `plan_power_chain` that
hardcodes the verified layout.
