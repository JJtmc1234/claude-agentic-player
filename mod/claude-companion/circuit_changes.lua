-- DRAFT: changes needed in claude-companion control.lua for circuit task.
-- This file is reference-only, NOT loaded by Factorio. Apply manually
-- when ready to bump mod to 0.9.0.

-- ============================================================
-- 1. storage init: add recipe_name + input_items
-- ============================================================
-- Replace the inline init in arena_setup with this style:
--
--   storage.arena = {
--     ...
--     recipe_name = 'iron-gear-wheel',   -- new
--     output_item = 'iron-gear-wheel',
--     target_output = 50,
--     input_items = { { name = 'iron-plate', count = 100 } },  -- list, was single
--     ...
--   }
--
-- Old hardcoded `input_item` + `refill_amount` fields stay for backward
-- compat (gear task) but reset prefers input_items if present.


-- ============================================================
-- 2. arena_reset: refill from input_items list
-- ============================================================
--   if in_c and in_c.valid then
--     local inv = in_c.get_inventory(defines.inventory.chest)
--     if inv then
--       inv.clear()
--       if a.input_items and #a.input_items > 0 then
--         for _, it in ipairs(a.input_items) do
--           inv.insert{ name = it.name, count = it.count }
--         end
--       else
--         -- legacy path
--         inv.insert{ name = a.input_item, count = a.refill_amount }
--       end
--     end
--   end


-- ============================================================
-- 3. arena_place: set assembler recipe from storage, not hardcoded
-- ============================================================
--   if name == 'assembling-machine-1' then
--     e.set_recipe(a.recipe_name or 'iron-gear-wheel')
--   end


-- ============================================================
-- 4. New remote: arena_set_task
-- ============================================================
local function arena_set_task(spec)
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  if spec.recipe_name then
    if not prototypes.recipe[spec.recipe_name] then
      return { ok = false, error = 'no such recipe ' .. spec.recipe_name }
    end
    a.recipe_name = spec.recipe_name
  end
  if spec.output_item then
    a.output_item = spec.output_item
  end
  if spec.target_output then
    a.target_output = spec.target_output
  end
  if spec.input_items then
    a.input_items = spec.input_items
  end
  return {
    ok = true,
    recipe_name = a.recipe_name,
    output_item = a.output_item,
    target_output = a.target_output,
    input_items = a.input_items,
  }
end

-- Register in remote.add_interface("claude_rl", { ..., arena_set_task = arena_set_task, ... })


-- ============================================================
-- 5. arena_score: generalize gear-specific accumulators
-- ============================================================
-- Anywhere the score code says 'iron-gear-wheel' literally, change to
-- a.output_item. Already uses a.output_item in most places — just audit
-- the activity_reward section (which checks asm.products_finished
-- regardless of recipe) for completeness.


-- ============================================================
-- 6. arena_get_constants: include current task spec in the response
-- ============================================================
-- Add:
--   recipe_name = a.recipe_name,
--   input_items = a.input_items,
-- to the constants table so the bridge can introspect what task is active.
