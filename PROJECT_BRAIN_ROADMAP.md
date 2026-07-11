# Project BRAIN — Roadmap

**Goal:** make the companion feel like *playing with someone intelligent* — a real co-op
teammate, not a scripted bot or a flaily reactive loop.

The feeling of intelligence comes from four things, **in this order**: **competent →
responsive → communicative → proactive.** A chatty agent that builds broken factories feels
dumb; nail competence first.

---

## Phase 1 — Competence (it builds things that *work*)
*Why:* nothing feels intelligent if the base is non-functional spaghetti. This is the macro
pivot (deterministic builders replace the flaky per-action loop).

- [x] `build_burner_mine` — drills on ore, fueled, into chests. **Validated live.**
- [x] `build_smelt_from_chests` — fueled furnace columns, exact geometry. **Validated live.**
      (Uses burner-inserters — electric ones sit no_power until the grid is up.)
- [ ] `build_steam_power` — pump → boilers → engines → poles → live grid. (stub; finish live)
- [ ] `connect_belt` — L-path belt router. (written; test live)
- [ ] `build_lab_bank` — labs placed + powered + fed science packs.
- [ ] `build_mall` — assemblers making gears/cable/circuits/belts/inserters into labeled chests.
- [ ] `craft_prereqs` — auto-craft what a macro needs before building (never fail on "out of parts").
- **MILESTONE:** a powered base that researches `automation` end-to-end, hands-off.

## Phase 2 — Responsiveness (it does what *you* ask, fast)  ← biggest jump in "feels smart"
- [ ] **Pings = commands:** JJ Alt-clicks a spot → companion goes there and helps / builds
      what he meant. (Ping reading already wired via `[gps=]` chat tags.)
- [ ] **Chat requests:** parse natural language ("build green circuits here", "mine that
      copper", "wall the east") → dispatch the right macro.
- [ ] Fast acknowledgement so it never looks frozen.

## Phase 3 — Communication (talks like a teammate)
- [ ] Brief, contextual acks + milestones + blockers ("On it — copper line at your ping.").
- [ ] Good judgment on when to speak; never spam (rate-limit + no-questions filter in place).
- [ ] Occasional *smart* suggestions, offered not forced.

## Phase 4 — Initiative & memory (thinks ahead, remembers)
- [ ] Persistent world-model: knows the base, what it built, goals, JJ's playstyle.
- [ ] Bounded proactivity: when idle, fix the worst bottleneck / prep the next tier.
- [ ] Anticipation: sees coal running low and fixes it before JJ notices.

## Phase 5 — Smart core (rich context → contextual decisions)
- [ ] Feed the Opus planner rich context each cycle: JJ's recent actions, chat, base state,
      tech-tree position, what JJ is working on.
- [ ] Reason about *JJ's* goals, not just its own.
- [ ] Use the issue #1 A/B to keep the right model on the right tier.

---

## Architecture (BRAIN v2)
- **Planner (Opus 4.8):** reasons about strategy + JJ's intent, picks *what/where*.
- **Executor:** deterministic **build macros** (`bridge/agent/build_macros.py`) — reliable,
  correct, connected blocks. (Replaces the flaky Haiku per-action loop for construction.)
- **Fast reactions (Haiku 4.5):** moment-to-moment tending (fuel, extract, respond to pings).
- **Steering:** `bridge/agent/goal.txt`, injected live every cycle.

## Immediate order
1. Fresh map with water + trees + clustered ore (in progress).
2. Phase 1 → powered base + `automation` researched (proves competence).
3. Phase 2 → ping-to-command (the moment it starts *feeling* like a teammate).
4. Layer in 3–5 as it stabilizes.
