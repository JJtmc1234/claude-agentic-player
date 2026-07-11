# Factorio — a Small Guide for a New Player

Written for JJ's friend. Not a walkthrough; more a set of "wish I'd
known this on day one" notes. Play at your own pace. Read tooltips.

## The mindset

- **Everything is about ratios and flow.** A furnace has an input,
  an output, and a rate. A belt has a speed. A drill has a mining
  speed. If you can name the numbers for one thing, you can plan
  around it.
- **Don't try to solve future problems.** Solve the one in front of
  you. If you need more iron, add a drill. If a belt is empty, ask
  why (upstream missing?). If it's overflowing, ask why (downstream
  bottleneck?). Iterate.
- **Save often.** F5 saves. F9 loads. Factorio doesn't punish
  experimentation.
- **Read tooltips.** Hover any item — it tells you the recipe,
  time, materials, place-radius, and what unlocks it. That's the
  cheat code.

## Fuel — the thing that eats your day

- Burner drills, burner inserters, boilers, and stone-furnaces all
  need FUEL — coal or wood. If they say `no fuel`, put fuel in their
  bottom slot.
- One drill worth of coal keeps a drill alive for a couple minutes
  at most. Set up a coal patch EARLY.
- Electric versions (electric-mining-drill, yellow inserter, assembly
  machine) don't need fuel — but they need power.

## Belts and inserters

- Belts have **two lanes** — items ride the left and right sides
  independently. You can put iron on one side and copper on the other
  if you're clever. Or don't; it works either way.
- An **inserter's arrow shows where it PICKS FROM**, not where it
  drops. If you rotate it and it says "waiting for source" — its
  arrow is pointing at a tile with nothing on it. Flip it.
- Inserters can pick from belts, chests, furnaces, or assemblers.
  They drop into anything with an input slot.
- Yellow (basic) inserter is slow but cheap. Long-handed inserter
  reaches 2 tiles. Fast inserter is faster. Stack inserter carries
  more per swing.

## Getting your first science pack (red)

The tech tree opens up once you have RED SCIENCE PACKS going into a
lab. To make red science packs you need:
- **1 copper plate** (smelt copper ore in a furnace)
- **1 iron gear wheel** (2 iron plates in an assembler or hand-crafted)

So the minimum viable science:
1. Two iron patches, one copper patch, one coal patch. Manual mine
   or burner-drill them.
2. Furnaces to smelt ore → plates.
3. Assembler-1 (need to research `automation` first — hand-craft it
   from iron plates, iron gears, and stone bricks).
4. Set the assembler recipe to `automation-science-pack` (or hand-
   craft the packs one at a time — slower but works).
5. Feed a lab. Research things.

## Automation-1 tech (yellow science-pack tech)

The FIRST tech you research. It unlocks the assembler-1. Do this
early — assembler-1 is way better than hand-crafting for anything
you need in bulk.

## Turrets and biters

- Gun-turret needs `firearm-magazine` (an inserter can load it).
- Biters attack when they smell pollution (the red cloud on the map).
  Reducing pollution (electric furnaces, boilers away from base,
  efficiency modules later) means fewer attacks.
- Kill nests near your base early with the pistol / submachine gun.
  Two nests near your iron is what JJ wiped in your run — that's the
  right instinct.
- Small biter worms are hard to kill in melee; wait until you have a
  submachine gun (research `military-1`) before poking one.
- WALL off your base. Stone-wall is cheap (5 stone) and works. A
  circle of walls + a handful of turrets buys you tons of time.

## Power

- Boiler + steam-engine + offshore-pump (on water) = electricity.
- Ratio: **1 offshore-pump : 20 boilers : 40 steam-engines**.
  That's max scale though — for a starter base, 1 pump + 1 boiler +
  2 engines is plenty (1.8 MW).
- Boilers burn coal. Feed them.

## Belt direction and orientation

- Belts flow in the direction of the arrow on them. Rotate with `R`.
- Underground belts skip up to 5 tiles (yellow) or 7 (red) or 9
  (blue). Very useful for crossing another belt or a river.
- Splitters take one belt in and split output between two belts —
  useful for balancing lanes.

## Small tips that save time

- Hold `Shift` while clicking a belt to force-place regardless of
  what's under it. Use with caution.
- `Q` swaps to whatever your cursor's hovering over. Try it on a
  belt, on a furnace, on anything.
- `Alt` toggles item-icon overlay — you can see what's in every
  chest, assembler, and furnace on the map.
- Right-click on a chest to open it. Right-click on a belt to pull
  items off.
- The map (`M`) is your friend — see your whole factory zoomed out.

## Don't get overwhelmed

- If you feel stuck, look at your most recent problem (drill out of
  coal? assembler out of iron?) and just fix that one.
- Everyone builds "spaghetti" at first. It's fine. Refactoring the
  base is part of the fun later.
- JJ has been playing forever and could optimize this whole thing
  in his sleep — but you're the one calling shots. If he suggests
  something and you'd rather do it your way, tell him to shush.
  Building your own base is how you actually learn.

## When to ask for help

- If a machine has a red icon on it, hover — the tooltip says why
  it's not working (no fuel / no ingredients / no power / no space).
- If a belt looks stopped, hover — check upstream.
- If you're overwhelmed, save + take a break + come back.

## Long term (weeks-ish)

- Red → green → military → chemical (blue) → production (purple) →
  utility (yellow) → space (white) is the science pack progression.
  Each unlocks the next major tier of tech.
- The end goal in vanilla is launching a rocket. In Space Age (the
  DLC) it's exploring other planets.

Have fun. Break things. Build things. Ask questions.
