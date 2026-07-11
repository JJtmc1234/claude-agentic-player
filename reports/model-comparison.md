# Project BRAIN — why Haiku executes and Opus plans (research report)

**Context.** Project BRAIN drives the Factorio "companion" with a two-tier loop: an **Opus 4.8
planner** (runs occasionally, sets strategy) + a **Haiku 4.5 executor** (runs every ~2s, takes
one action). This report backs that split with evidence, per issue #1.

---

## 1. Base model differences & the core tradeoff

Hard specs from Anthropic's official model overview (link below):

| | **Haiku 4.5** (executor) | **Opus 4.8** (planner) |
|---|---|---|
| Positioned as | "Fastest model with near-frontier intelligence" | "For complex agentic coding and enterprise work" |
| Comparative latency | **Fastest** | Moderate |
| Price (input / output per MTok) | **$1 / $5** | $5 / $25 |
| Context window | 200k tokens | 1M tokens |
| Max output | 64k | 128k |
| Adaptive (deep) thinking | No | **Yes** |
| Extended thinking | Yes | No |

**The tradeoff in one line:** Opus buys you *reasoning depth and long-context planning* at
**5× the price and higher latency**; Haiku buys you *speed and cost* (5× cheaper, lowest
latency) while keeping "near-frontier" quality on well-scoped tasks. Neither is strictly
better — they sit at different points on the capability↔speed/cost curve.

## 2. Why Haiku is right for the *executor*

The executor's job each cycle is narrow and repetitive: read a small JSON game-state, pick
**one** tool call (e.g. `mine_nearest('coal')`, `insert_into(...)`), return. This is a
*classification/selection* task, not open-ended reasoning — exactly where a fast model shines.

Why the numbers favor Haiku here:
- **Frequency → cost dominates.** The executor fires ~every 2s: **~1,800 cycles/hour, ~14k
  overnight.** At $1/$5 vs $5/$25, running this tier on Opus would cost **~5×** for decisions
  that don't need Opus-grade reasoning. On a multi-hour run that is the difference between
  ~$X and ~$5X.
- **Latency → responsiveness.** "Fastest" vs "Moderate" latency matters when you want a real-
  time co-op feel; a slow executor makes the character look idle between actions (we observed
  exactly this early on).
- **Context is ample.** The per-cycle prompt is small (state + tools ≈ a few k tokens), so
  Haiku's 200k window is far more than enough — Opus's 1M window is wasted here.

## 3. Why Opus is right for the *planner*

The planner's job is the opposite: infrequently (~every 20 cycles), read the *full* state +
mission + roadmap and produce a **multi-step strategy** that respects dependencies (tech-tree
gating, build order, tradeoffs). This is genuine reasoning.

Why the numbers favor Opus here:
- **Adaptive thinking = deep reasoning** on hard, multi-constraint problems — the planner's
  whole point. Haiku lacks adaptive thinking.
- **Cost is amortized.** Because the planner runs ~1/20th as often as the executor, its 5×
  higher price is a small slice of total spend — you pay for the smart tier only when it
  matters.
- **1M context** lets it hold the whole situation (state + long standing mission + history).

## Primary evidence from *our own* project (strongest signal)

- **Opus planner produced coherent, grounded plans**, e.g. *"fuel the furnaces at (38,-73)/
  (40,-73), mine iron at (41,-75), then place an assembler + lab for red science,"* and
  correctly reasoned about **trigger-tech gating** (e.g. "smelt 10 copper → unlocks
  electronics"). That multi-step, dependency-aware planning is what the smart tier is for.
- **Swapping the executor to a bigger model backfired.** When I tried Sonnet 5 as the
  executor, it emitted **malformed tool calls (missing arguments)** and cost more; reverting
  to Haiku 4.5 (with a higher `max_tokens`) gave reliable execution. So "bigger" did not mean
  "better" for the tight tool-loop — a concrete data point that the task, not the model tier,
  should pick the model. *(Caveat: part of that failure was likely `max_tokens` truncation
  interacting with the model, not pure capability — see the honest note below.)*

## Honest limitations & how to get the *exact* numbers Hunter wants

This report uses **authoritative published specs** (pricing, latency, context, thinking modes)
plus **direct project observations**. What it does *not* yet have is a controlled head-to-head
on *our* task. The rigorous way to prove the split (and the right next step):

> **A/B experiment:** run the same 100 executor cycles three times — once on Haiku 4.5, once
> on Opus 4.8, once on Sonnet 5 — and measure **(a) task-success rate** (did the chosen action
> advance the goal?), **(b) latency per cycle**, **(c) $ per cycle**. Do the same for the
> planner. That converts intuition into a table of real numbers.

## Sources
- Anthropic — Models overview (specs, pricing, latency): https://platform.claude.com/docs/en/about-claude/models/overview
- Anthropic — Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic — Adaptive thinking: https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
- (Comparison articles from the issue) Medium / Dev.to model round-ups — useful color, but treat
  third-party benchmarks with caution; prefer first-party specs above.
