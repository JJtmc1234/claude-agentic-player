# Supply Priorities

The workshop chest at (-30.5, 41.5) is the shared supply-drop.
JJ places ghosts; we fulfill them by depositing crafted items there.

## Read the demand

```lua
-- get all ghosts + count by type
local ghosts = surfaces.nauvis.find_entities_filtered{name='entity-ghost'}
local by_name = {}
for _, g in ipairs(ghosts) do
  by_name[g.ghost_name] = (by_name[g.ghost_name] or 0) + 1
end
```

Compare against workshop chest inventory. Delta = still-needed.

## Priority order (2026-07-04, review as ghost totals change)

1. **Fuel infrastructure** — coal supply for burner tools. Nothing
   else works if base is dark.
2. **Furnaces** — smelting is the bottleneck for iron+copper.
   Cheap (5 stone each).
3. **Burner-inserters + wooden-chests** — cheap, get JJ moving on
   his belt/mining designs.
4. **Belts** — highest ghost count. Bulk-craft in batches of 50.
5. **Small-electric-poles** — needed for electric drills.
6. **Electric-mining-drills** — needed for iron scale.
7. **Steam engines + boilers** — power scale. Bigger materials,
   fewer of them.
8. **Underground-belts + splitters** — smaller counts, but
   splitters need steel-plate (smelt first).
9. **Assemblers, labs** — expensive, low count.

## Common recipe costs (per unit, Space Age 2.0)

| Item | Ingredients | Notes |
|---|---|---|
| transport-belt (×2) | 1 iron + 1 gear | craft in batches of 25 (50 belts) |
| burner-inserter | 1 iron + 1 gear | |
| inserter (yellow, electric) | 1 iron + 1 gear + 1 circuit | needs power to work |
| wooden-chest | 2 wood | |
| stone-furnace | 5 stone | |
| small-electric-pole (×2) | 1 wood + 2 cable | wire reach 7.5 |
| medium-electric-pole (×1) | 2 copper-plate + 2 steel-plate + 2 iron-stick | reach 9 |
| big-electric-pole (×1) | 5 iron-stick + 5 steel + 4 cable | reach 30 (needs elec-dist-1 tech) |
| burner-mining-drill | 3 iron + 3 gear + 1 furnace | 0.25 ore/sec |
| electric-mining-drill | 10 iron + 5 gear + 3 circuit | 0.5 ore/sec, needs power |
| stone-brick | 2 stone (smelt) | needs furnace |
| steel-plate | 5 iron-plate (smelt) | slow — 16 sec |
| copper-cable (×2) | 1 copper-plate | |
| electronic-circuit | 1 iron + 3 cable | ~1.5 copper per circuit |
| assembling-machine-1 | 9 iron + 5 gear + 5 circuit | |
| lab | 10 gear + 10 circuit + 4 belt | in 2.0 |
| logistic-science-pack (green) | 1 belt + 1 inserter | in 2.0 |
| automation-science-pack (red) | 1 copper-plate + 1 gear | in 2.0 |
| pumpjack | 5 gear + 5 steel + 10 pipe + 5 circuit | oil chain |
| oil-refinery | 15 steel + 10 stone-brick + 10 gear + 10 circuit | huge |

## Batching rules

- Craft in batches of 25 (belts) or 10 (inserters) to keep script
  timeout under 60 sec.
- After each batch, deposit to workshop chest, then start next batch.
- Split across workers: assign different items to different agents.

## Depletion + refresh

- Iron stockpile threshold: keep ≥200 iron-plate in personal inv.
  Drop below? Trigger a mining trip.
- Stone threshold: ≥100 stone. Below? Trip to stone patch (57, -1).
- Wood threshold: ≥50 wood. Below? Chop 20 trees.
- Copper: ≥100 copper-plate.
- Coal: ≥50 coal at boiler + surplus in drill fuel slots.

## Workshop chest audit

After each supply drop, log to your context.txt:
```
Deposited: <n> belts, <n> furnaces, <n> poles ...
Workshop now: (query via find_entities_filtered → get_inventory).
```

Manager watches this — sudden drops (JJ taking things) are normal;
sudden empty (no one supplying) means a worker stopped.

## Requesting from JJ

JJ has a buffer chest at (-6.5, -32.5) — he'll drop items there if
asked via in-game chat. He said "intermediate-products tab only" —
meaning gears, circuits, plates, cables. NOT machines, belts,
inserters (logistics tab), or raw ores (raw tab).

To ask: `bridge/say.py "REQUEST: <n> <item>. Reason: <short>."`

Rate limit: about 1 item type per minute. Don't spam.

## Steel-plate note

Steel-plate is the choke point once we get past the basic supply.
- Recipe: 5 iron-plate → 1 steel-plate in a furnace, 16 sec each.
- For 60 e-drills + 8 boilers, we need many steel-plates.
- Solution: dedicate 4+ furnaces to steel-plate production, feed
  them directly from iron-plate chests.
