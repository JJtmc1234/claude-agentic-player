-- Claude Companion 0.3.0
-- Server-side helpers for the Claude Agentic Player project.
--
-- Remote interface "claude":
--   ping()
--   get_chat(since_index), drain_chat()
--   set_walking(unit_number, direction, walking)     -- raw, manual direction
--   walk_to(unit_number, goal_x, goal_y, radius)     -- NEW: pathfind + drive
--   get_walk_status(unit_number)                     -- NEW
--   cancel_walk(unit_number)                         -- NEW
--   start_mining(character_unum, target_x, target_y)
--   stop_mining(character_unum)
--   get_mining_status(character_unum)
--
-- on_console_chat                       -> storage.chat_log buffer
-- on_script_path_request_finished       -> stores path in storage.path_requests, NEW
-- on_tick                               -> processes storage.mining_jobs + storage.walks
--
-- Why on_tick driving: the engine's built-in action loops (walking_state /
-- mining_state -> game effects) only run for characters with a player
-- controller. Our character has player_index = nil (created via
-- create_entity), so the engine ignores it. We run those loops here.

local MINING_REACH = 2.7
local WAYPOINT_REACHED_DIST = 0.6   -- how close to a path waypoint counts as "reached"


-- ---------- storage init ----------

local function init_chat_log()      if not storage.chat_log      then storage.chat_log      = {} end end
local function init_mining_jobs()   if not storage.mining_jobs   then storage.mining_jobs   = {} end end
local function init_walks()         if not storage.walks         then storage.walks         = {} end end
local function init_path_requests() if not storage.path_requests then storage.path_requests = {} end end
local function init_craft_jobs()    if not storage.craft_jobs    then storage.craft_jobs    = {} end end
local function init_arena()         if not storage.arena         then storage.arena         = {} end end
local function init_claude_chars()  if not storage.claude_chars  then storage.claude_chars  = {} end end

local function init_all()
  init_chat_log(); init_mining_jobs(); init_walks(); init_path_requests(); init_craft_jobs(); init_arena()
  init_claude_chars()
end

-- Migration: fold the legacy single-character key into the multi-char map.
-- Idempotent: only runs when the old key exists and the new map hasn't been
-- populated yet. The old key is kept as an alias (not deleted) for the bridge.
local function migrate_claude_chars()
  if storage.claude_char_unum and not storage.claude_chars then
    storage.claude_chars = { main = storage.claude_char_unum }
  end
end

script.on_init(init_all)
script.on_configuration_changed(function(_)
  migrate_claude_chars()   -- must run BEFORE init_all (which would create an empty map)
  init_all()
end)


-- ---------- chat buffer ----------

script.on_event(defines.events.on_console_chat, function(event)
  init_chat_log()
  local player_name = "<server>"
  if event.player_index then
    local p = game.get_player(event.player_index)
    if p then player_name = p.name end
  end
  table.insert(storage.chat_log, {
    tick = event.tick,
    player = player_name,
    message = event.message,
  })
end)


-- ---------- pathfinding ----------

-- The 8 driveable directions for a character, mapped to their unit vectors.
-- In Factorio 2.0 defines.direction has 16 values (extras added for rail
-- rotations); the underscored diagonal names from 1.x (north_east etc.)
-- don't exist anymore. Using raw integer values to avoid the renaming
-- guessing-game: 0=N, 2=NE, 4=E, 6=SE, 8=S, 10=SW, 12=W, 14=NW.
local DIRS_MAP = {
  [0]  = { dx =  0, dy = -1 },  -- north
  [2]  = { dx =  1, dy = -1 },  -- northeast
  [4]  = { dx =  1, dy =  0 },  -- east
  [6]  = { dx =  1, dy =  1 },  -- southeast
  [8]  = { dx =  0, dy =  1 },  -- south
  [10] = { dx = -1, dy =  1 },  -- southwest
  [12] = { dx = -1, dy =  0 },  -- west
  [14] = { dx = -1, dy = -1 },  -- northwest
}

-- Returns the defines.direction value whose unit vector is closest to (dx,dy)
-- by dot-product. Returns nil if the vector is essentially zero.
local function direction_toward(dx, dy)
  local len = math.sqrt(dx*dx + dy*dy)
  if len < 0.01 then return nil end
  local ux, uy = dx/len, dy/len
  local best_dir, best_score = nil, -math.huge
  for dir, v in pairs(DIRS_MAP) do
    local dlen = math.sqrt(v.dx*v.dx + v.dy*v.dy)
    local score = (ux * v.dx + uy * v.dy) / dlen
    if score > best_score then
      best_score = score
      best_dir = dir
    end
  end
  return best_dir
end

script.on_event(defines.events.on_script_path_request_finished, function(event)
  init_path_requests(); init_walks()
  local req = storage.path_requests[event.id]
  if not req then return end
  storage.path_requests[event.id] = nil
  if event.try_again_later then
    storage.walks[req.character_unum] = {
      completed = true,
      error = 'pathfinder asked to try again later',
    }
    return
  end
  if not event.path or #event.path == 0 then
    storage.walks[req.character_unum] = {
      completed = true,
      error = 'no path found',
    }
    return
  end
  storage.walks[req.character_unum] = {
    path = event.path,
    current_index = 1,
    goal_x = req.goal_x,
    goal_y = req.goal_y,
    radius = req.radius,
    started_tick = game.tick,
    waypoint_count = #event.path,
  }
end)


-- ---------- on_tick: mining + walking action loops ----------

local function find_mineable_at(surface, x, y)
  if not surface then return nil end
  local ents = surface.find_entities_filtered{position={x, y}, radius=0.5}
  for _, e in ipairs(ents) do
    if e.valid and e.prototype.mineable_properties and e.prototype.mineable_properties.minable then
      return e
    end
  end
  return nil
end

local function process_mining_jobs()
  if next(storage.mining_jobs) == nil then return end
  local to_remove = {}
  for char_unum, job in pairs(storage.mining_jobs) do
    local c = game.get_entity_by_unit_number(char_unum)
    local t = find_mineable_at(c and c.surface, job.target_x, job.target_y)

    local cancel = nil
    if not (c and c.valid) then
      cancel = 'character gone'
    elseif not t then
      cancel = 'target gone or not mineable'
    else
      local dx = t.position.x - c.position.x
      local dy = t.position.y - c.position.y
      if dx*dx + dy*dy > MINING_REACH * MINING_REACH then
        cancel = 'character out of reach'
      end
    end

    if cancel then
      job.error = cancel
      to_remove[#to_remove + 1] = char_unum
    else
      job.ticks_left = job.ticks_left - 1
      if job.ticks_left <= 0 then
        local inv = c.get_main_inventory()
        local gained = {}
        local mp = t.prototype.mineable_properties
        for _, p in ipairs(mp.products or {}) do
          if p.type == 'item' then
            local amt = p.amount
            if not amt and p.amount_min and p.amount_max then
              amt = math.random(p.amount_min, p.amount_max)
            end
            amt = amt or 1
            if (not p.probability) or math.random() < p.probability then
              if inv then inv.insert{name = p.name, count = amt} end
              table.insert(gained, {name = p.name, count = amt})
            end
          end
        end
        job.completed = true
        job.gained = gained
        -- Resource entities (coal, iron-ore, etc.) carry an `amount` field
        -- and should be DECREMENTED, not destroyed — destroying wipes the
        -- whole patch tile. Trees / rocks (no amount) are one-shot, destroy.
        if t.type == 'resource' and t.amount and t.amount > 1 then
          t.amount = t.amount - 1
        else
          t.destroy{}
        end
        to_remove[#to_remove + 1] = char_unum
      end
    end
  end
  for _, k in ipairs(to_remove) do storage.mining_jobs[k] = nil end
end

local function process_walks()
  if next(storage.walks) == nil then return end
  for char_unum, walk in pairs(storage.walks) do
    if not walk.completed then
      local c = game.get_entity_by_unit_number(char_unum)
      if not (c and c.valid) then
        walk.completed = true
        walk.error = 'character gone'
      else
        local gdx = walk.goal_x - c.position.x
        local gdy = walk.goal_y - c.position.y
        if gdx*gdx + gdy*gdy <= (walk.radius or 1) * (walk.radius or 1) then
          walk.completed = true
          walk.final_distance = math.sqrt(gdx*gdx + gdy*gdy)
          c.walking_state = { walking = false, direction = 0 }
        else
          while walk.current_index <= #walk.path do
            local wp = walk.path[walk.current_index]
            local dx = wp.position.x - c.position.x
            local dy = wp.position.y - c.position.y
            if dx*dx + dy*dy <= WAYPOINT_REACHED_DIST * WAYPOINT_REACHED_DIST then
              walk.current_index = walk.current_index + 1
            else
              break
            end
          end
          local wp = walk.path[walk.current_index]
          if not wp then
            walk.completed = true
            walk.error = 'path exhausted before reaching goal'
            walk.final_distance = math.sqrt(gdx*gdx + gdy*gdy)
            c.walking_state = { walking = false, direction = 0 }
          else
            local dir = direction_toward(wp.position.x - c.position.x, wp.position.y - c.position.y)
            if dir then
              c.walking_state = { walking = true, direction = dir }
            end
          end
        end
      end
    end
  end
  -- IMPORTANT: do NOT auto-remove completed walks here. They stay in storage
  -- until get_walk_status reads them, so the caller can see the final status
  -- (success / error / waypoint count / final distance to goal).
end

-- Custom hand-crafting action loop. character.begin_crafting() is engine-gated
-- to player-controlled characters (like mining was), so we run our own:
-- one job per character, decrement ticks, complete one item at a time.
--
-- storage.craft_jobs[char_unum] = {
--   recipe, count, crafted_so_far, ticks_per_item, ticks_left_this_item,
--   completed, error, gained (list of {name, count}),
-- }
local function process_craft_jobs()
  if next(storage.craft_jobs) == nil then return end
  for char_unum, job in pairs(storage.craft_jobs) do
    if not job.completed then
      local c = game.get_entity_by_unit_number(char_unum)
      if not (c and c.valid) then
        job.completed = true; job.error = 'character gone'
      else
        job.ticks_left_this_item = job.ticks_left_this_item - 1
        if job.ticks_left_this_item <= 0 then
          local recipe = prototypes.recipe[job.recipe]
          local inv = c.get_main_inventory()
          -- Re-check ingredients (in case they were taken from inv mid-craft).
          local can_craft = true
          for _, ing in ipairs(recipe.ingredients) do
            if ing.type == 'item' and inv.get_item_count(ing.name) < ing.amount then
              can_craft = false
              job.error = 'ran out of ' .. ing.name
              job.completed = true
              break
            end
          end
          if can_craft then
            for _, ing in ipairs(recipe.ingredients) do
              if ing.type == 'item' then
                inv.remove{ name = ing.name, count = ing.amount }
              end
            end
            for _, prod in ipairs(recipe.products) do
              if prod.type == 'item' then
                local amt = prod.amount or 1
                if prod.amount_min and prod.amount_max then
                  amt = math.random(prod.amount_min, prod.amount_max)
                end
                if (not prod.probability) or math.random() < prod.probability then
                  inv.insert{ name = prod.name, count = amt }
                  if not job.gained then job.gained = {} end
                  -- merge gained entries by name
                  local merged = false
                  for _, g in ipairs(job.gained) do
                    if g.name == prod.name then
                      g.count = g.count + amt; merged = true; break
                    end
                  end
                  if not merged then
                    table.insert(job.gained, { name = prod.name, count = amt })
                  end
                end
              end
            end
            job.crafted_so_far = job.crafted_so_far + 1
            if job.crafted_so_far >= job.count then
              job.completed = true
            else
              job.ticks_left_this_item = job.ticks_per_item
            end
          end
        end
      end
    end
  end
end

-- Forward-needed helper (the full RL arena section is later in the file,
-- but process_arena_sim runs every tick and must see arena_find_chest in
-- scope. Lua locals are not forward-visible.)
local function _arena_find_chest_early(a, which_key)
  local s = a.surface_name and game.surfaces[a.surface_name]
  if not s then return nil end
  local c = a[which_key]
  if not c then return nil end
  local ents = s.find_entities_filtered{
    position = { c.x, c.y }, type = 'container', radius = 0.6,
  }
  return ents[1]
end

-- Helper: maintain a stack of display-panel entities 10 tiles above the
-- grid, one per line. Stored in storage.arena.display_panels for reuse.
--
-- The 2.0 display-panel API: text on a panel is set via the
-- combinator_description property (the chat-bubble "this signal means X"
-- text). `entity.text` does NOT exist — that was the source of multiple
-- silent failures in 0.8.10+. always_show_in_chart toggles whether the
-- description renders in the world without a circuit signal.
local function update_arena_panel(a, surface, lines, _title_color)
  if a.panel_ids then
    for _, id in ipairs(a.panel_ids) do
      pcall(function() rendering.destroy(id) end)
    end
    a.panel_ids = nil
  end
  if not surface then return end
  local panel_x = (a.bounds.x_min + a.bounds.x_max) / 2
  local panel_y_top = a.bounds.y_min - 10
  a.display_panels = a.display_panels or {}
  for i = 1, #lines do
    local dp = a.display_panels[i]
    if not (dp and dp.valid) then
      dp = surface.create_entity{
        name = 'display-panel',
        position = { panel_x, panel_y_top + (i - 1) * 1.0 },
        force = 'player',
      }
      a.display_panels[i] = dp
    end
    if dp and dp.valid then
      pcall(function() dp.combinator_description = lines[i] end)
      pcall(function() dp.always_show_in_chart = true end)
    end
  end
  for i = #lines + 1, #a.display_panels do
    local dp = a.display_panels[i]
    if dp and dp.valid then dp.destroy() end
    a.display_panels[i] = nil
  end
end

-- Arena (RL) simulation tick handler. When storage.arena.simulating is
-- true, we count the output chest's gear count every tick. When it hits
-- target_output OR sim_max_ticks elapsed, we stop the simulation and
-- pause the world. Bridge polls arena_get_sim_status to learn this.
local function process_arena_sim()
  local a = storage.arena
  if not a or not a.simulating then return end
  a.sim_calls_count = (a.sim_calls_count or 0) + 1
  a.last_tick_processed = game.tick
  -- Re-assert speed/pause every tick. auto_pause in server-settings keeps
  -- trying to bring the world back to speed=1 (and possibly pause it) when
  -- no players are connected; we override every tick during simulation.
  if game.tick_paused then game.tick_paused = false end
  if game.speed < 8 then game.speed = 64 end
  if not a.output_chest then
    a.simulating = false
    a.sim_error = 'no output_chest in storage'
    return
  end
  local out = _arena_find_chest_early(a, 'output_chest')
  if not out or not out.valid then
    a.simulating = false
    a.sim_error = 'output chest entity gone at (' .. a.output_chest.x .. ',' .. a.output_chest.y .. ')'
    return
  end
  local inv = out.get_inventory(defines.inventory.chest)
  if not inv then
    a.simulating = false
    a.sim_error = 'output chest has no inventory'
    return
  end
  local count = inv.get_item_count(a.output_item)
  local elapsed = game.tick - (a.sim_started_tick or game.tick)
  a.last_count_seen = count
  a.last_elapsed_seen = elapsed
  if count >= a.target_output then
    a.simulating = false
    a.sim_ticks_taken = elapsed
    a.sim_final_output = count
    game.speed = 1.0
  elseif elapsed >= (a.sim_max_ticks or 3600) then
    a.simulating = false
    a.sim_ticks_taken = elapsed
    a.sim_final_output = count
    a.sim_timed_out = true
    game.speed = 1.0
  end
  -- Live panel updates: every 30 sim ticks show current state. Cheap.
  if elapsed % 30 == 0 then
    local surface = game.surfaces[a.surface_name]
    local lines = {
      string.format("SIMULATING  tick %d/%d  gears=%d/%d",
        elapsed, a.sim_max_ticks or 3600, count, a.target_output),
      string.format("input chest plates: %s",
        (function()
          local in_c = _arena_find_chest_early(a, 'input_chest')
          if not in_c then return "?" end
          local inv = in_c.get_inventory(defines.inventory.chest)
          return tostring(inv and inv.get_item_count(a.input_item) or 0)
        end)()),
      "(panel auto-updates each ~0.5s sim time)",
    }
    update_arena_panel(a, surface, lines, {r=0.7, g=0.9, b=1})
  end
end

script.on_event(defines.events.on_tick, function(event)
  init_mining_jobs(); init_walks(); init_path_requests(); init_craft_jobs(); init_arena()
  process_mining_jobs()
  process_walks()
  process_craft_jobs()
  process_arena_sim()
end)


-- ---------- remote functions ----------

local function count_kv(t)
  local n = 0; for _ in pairs(t) do n = n + 1 end; return n
end

local function ping()
  init_all()
  return {
    ok = true,
    pong = "from claude-companion 0.10.6",
    tick = game.tick,
    chat_buffer_size = #storage.chat_log,
    mining_jobs = count_kv(storage.mining_jobs),
    walks = count_kv(storage.walks),
    pending_paths = count_kv(storage.path_requests),
  }
end

local function get_chat(since_index)
  init_chat_log()
  since_index = since_index or 0
  local out = {}
  for i = since_index + 1, #storage.chat_log do
    table.insert(out, storage.chat_log[i])
  end
  return { messages = out, latest_index = #storage.chat_log }
end

local function drain_chat()
  init_chat_log()
  local log = storage.chat_log
  storage.chat_log = {}
  return { messages = log, count = #log }
end

local function set_walking(unit_number, direction, walking)
  local ent = game.get_entity_by_unit_number(unit_number)
  if not ent or not ent.valid then
    return { ok = false, error = "no entity with unit_number " .. tostring(unit_number) }
  end
  if ent.name ~= "character" then
    return { ok = false, error = "entity is a " .. ent.name .. ", not a character" }
  end
  if walking == nil then walking = false end
  ent.walking_state = {
    walking = walking,
    direction = direction or defines.direction.north,
  }
  return { ok = true, unit_number = ent.unit_number,
           position = { x = ent.position.x, y = ent.position.y } }
end

local function walk_to(character_unum, goal_x, goal_y, radius)
  init_walks(); init_path_requests()
  radius = radius or 1.0
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  if c.type ~= 'character' then
    return { ok = false, error = 'entity ' .. character_unum .. ' is a ' .. c.type .. ', not a character' }
  end
  -- Cancel any existing walk for this character.
  storage.walks[character_unum] = nil
  for id, req in pairs(storage.path_requests) do
    if req.character_unum == character_unum then storage.path_requests[id] = nil end
  end
  -- If already within radius, succeed immediately.
  local dx = goal_x - c.position.x
  local dy = goal_y - c.position.y
  if dx*dx + dy*dy <= radius * radius then
    return { ok = true, status = 'already_at_goal', position = { x = c.position.x, y = c.position.y } }
  end
  local id = c.surface.request_path{
    bounding_box = c.prototype.collision_box,
    collision_mask = c.prototype.collision_mask,
    start = c.position,
    goal = { goal_x, goal_y },
    force = c.force,
    radius = radius,
    can_open_gates = true,
    entity_to_ignore = c,
  }
  if not id then
    return { ok = false, error = 'request_path returned no id' }
  end
  storage.path_requests[id] = {
    character_unum = character_unum,
    goal_x = goal_x,
    goal_y = goal_y,
    radius = radius,
  }
  return { ok = true, status = 'pathfinding', request_id = id }
end

local function get_walk_status(character_unum)
  init_walks(); init_path_requests()
  local walk = storage.walks[character_unum]
  if walk then
    if walk.completed then
      -- Consume: caller has now seen the final state. Subsequent calls
      -- return 'idle' until a new walk_to / pathfind starts.
      storage.walks[character_unum] = nil
      return {
        status = walk.error and 'error' or 'completed',
        error = walk.error,
        current_index = walk.current_index,
        total_waypoints = walk.waypoint_count or (walk.path and #walk.path) or 0,
        final_distance = walk.final_distance,
      }
    end
    return {
      status = 'walking',
      current_index = walk.current_index,
      total_waypoints = walk.waypoint_count or (walk.path and #walk.path) or 0,
    }
  end
  for _, req in pairs(storage.path_requests) do
    if req.character_unum == character_unum then
      return { status = 'pathfinding' }
    end
  end
  return { status = 'idle' }
end

local function cancel_walk(character_unum)
  init_walks(); init_path_requests()
  storage.walks[character_unum] = nil
  for id, req in pairs(storage.path_requests) do
    if req.character_unum == character_unum then storage.path_requests[id] = nil end
  end
  local c = game.get_entity_by_unit_number(character_unum)
  if c and c.valid then
    c.walking_state = { walking = false, direction = defines.direction.north }
  end
  return { ok = true }
end

local function start_mining(character_unum, target_x, target_y)
  init_mining_jobs()
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  if c.type ~= 'character' then
    return { ok = false, error = 'entity ' .. character_unum .. ' is a ' .. c.type .. ', not a character' }
  end
  local t = find_mineable_at(c.surface, target_x, target_y)
  if not t then return { ok = false, error = 'no mineable entity at ('..target_x..','..target_y..')' } end
  local dx = t.position.x - c.position.x
  local dy = t.position.y - c.position.y
  local dist = math.sqrt(dx*dx + dy*dy)
  if dist > MINING_REACH then
    return { ok = false, error = 'out of reach', distance = dist, reach = MINING_REACH }
  end
  local mp = t.prototype.mineable_properties
  local mining_time = mp.mining_time or 0.5
  local ticks = math.ceil(mining_time * 60)
  storage.mining_jobs[character_unum] = {
    target_x = t.position.x,
    target_y = t.position.y,
    target_name = t.name,
    ticks_left = ticks,
    started_tick = game.tick,
  }
  return { ok = true, target = t.name, eta_ticks = ticks, distance = dist }
end

local function stop_mining(character_unum)
  init_mining_jobs()
  local was = storage.mining_jobs[character_unum] ~= nil
  storage.mining_jobs[character_unum] = nil
  return { ok = true, was_mining = was }
end

local function get_mining_status(character_unum)
  init_mining_jobs()
  local job = storage.mining_jobs[character_unum]
  if not job then return { mining = false } end
  return {
    mining = true,
    target_name = job.target_name,
    target_x = job.target_x,
    target_y = job.target_y,
    ticks_left = job.ticks_left,
    started_tick = job.started_tick,
  }
end

-- ---------- placing, transferring, combat (0.3.0 additions) ----------

-- Place an item from the character's inventory as an entity in the world.
-- direction is optional (only matters for directional entities like inserters).
local function place_entity(character_unum, item_name, x, y, direction)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local inv = c.get_main_inventory()
  if not inv then return { ok = false, error = 'no main inventory' } end
  if inv.get_item_count(item_name) < 1 then
    return { ok = false, error = 'no ' .. item_name .. ' in character inventory' }
  end
  local item_proto = prototypes.item[item_name]
  if not item_proto or not item_proto.place_result then
    return { ok = false, error = item_name .. ' is not placeable (no place_result)' }
  end
  local ent_name = item_proto.place_result.name
  if not c.surface.can_place_entity{
    name = ent_name, position = {x, y}, force = c.force, direction = direction,
  } then
    return { ok = false, error = 'cannot place ' .. ent_name .. ' at (' .. x .. ',' .. y .. ')' }
  end
  local e = c.surface.create_entity{
    name = ent_name, position = {x, y}, force = c.force, direction = direction,
    raise_built = true,
  }
  if not e then return { ok = false, error = 'create_entity returned nil' } end
  inv.remove{ name = item_name, count = 1 }
  return {
    ok = true,
    entity_name = e.name,
    unit_number = e.unit_number,
    position = { x = e.position.x, y = e.position.y },
  }
end

-- Move items between the character's main inventory and a chest at (x, y).
-- direction: 'to_chest' (character -> chest) or 'from_chest' (chest -> character).
local function transfer_items(character_unum, x, y, item_name, count, direction)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local chest = nil
  for _, ent in ipairs(c.surface.find_entities_filtered{position={x,y}, radius=0.5}) do
    if ent.valid and (ent.type == 'container' or ent.type == 'logistic-container') then
      chest = ent; break
    end
  end
  if not chest then return { ok = false, error = 'no chest at (' .. x .. ',' .. y .. ')' } end
  local char_inv = c.get_main_inventory()
  local chest_inv = chest.get_inventory(defines.inventory.chest)
  if not char_inv or not chest_inv then
    return { ok = false, error = 'missing inventory on either side' }
  end
  local src, dst
  if direction == 'to_chest' then src = char_inv; dst = chest_inv
  elseif direction == 'from_chest' then src = chest_inv; dst = char_inv
  else return { ok = false, error = "direction must be 'to_chest' or 'from_chest'" } end
  local available = src.get_item_count(item_name)
  if available <= 0 then
    return { ok = false, error = 'source has no ' .. item_name }
  end
  local want = math.min(count or available, available)
  local inserted = dst.insert{ name = item_name, count = want }
  if inserted > 0 then
    src.remove{ name = item_name, count = inserted }
  end
  return {
    ok = true,
    moved = inserted,
    direction = direction,
    item = item_name,
    chest = chest.name,
  }
end

-- Set the character's shooting_state toward a target position. The engine
-- ONLY processes shooting for player-controlled characters (same gate that
-- blocked mining), so this is best-effort: it will set the state and the
-- engine will run it if it can. If shots don't happen, we'll add a custom
-- combat loop in a later version (like we did for mining).
local function shoot_at(character_unum, target_x, target_y)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local guns = c.get_inventory(defines.inventory.character_guns)
  local ammo = c.get_inventory(defines.inventory.character_ammo)
  if not guns or guns.is_empty() then return { ok = false, error = 'no weapon in gun slot' } end
  if not ammo or ammo.is_empty() then return { ok = false, error = 'no ammo' } end
  c.shooting_state = {
    state = defines.shooting.shooting_selected,
    position = { target_x, target_y },
  }
  return {
    ok = true,
    note = 'shooting_state set; engine may not process for free characters',
    target = { x = target_x, y = target_y },
  }
end

local function stop_shooting(character_unum)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  c.shooting_state = { state = defines.shooting.not_shooting, position = c.position }
  return { ok = true }
end

-- Pick up an item-on-ground entity at (x,y) into the character's main inventory.
-- Items-on-ground get auto-picked-up by player characters when they walk over;
-- for free characters we do it explicitly.
local function pick_up_at(character_unum, x, y)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local inv = c.get_main_inventory()
  if not inv then return { ok = false, error = 'no main inventory' } end
  local items = c.surface.find_entities_filtered{
    name = 'item-on-ground', position = {x, y}, radius = 1.5,
  }
  if #items == 0 then return { ok = false, error = 'no item-on-ground near (' .. x .. ',' .. y .. ')' } end
  local picked = {}
  for _, e in ipairs(items) do
    if e.valid and e.stack and e.stack.valid_for_read then
      local n = e.stack.name
      local cnt = e.stack.count
      local inserted = inv.insert{ name = n, count = cnt }
      if inserted > 0 then
        if inserted >= cnt then
          e.destroy{}
        else
          e.stack.count = cnt - inserted
        end
        table.insert(picked, { name = n, count = inserted })
      end
    end
  end
  return { ok = true, picked = picked }
end


-- ---------- ghost revival / blueprint building (0.4.0) ----------

-- Build (revive) all ghost entities on the character's force within radius.
-- For each ghost: looks up the item that places it (items_to_place_this),
-- checks the character has enough, calls ghost.revive(), deducts from
-- inventory. Returns built/missing/errors lists.
--
-- ghost.revive() makes the ghost into a real entity but does NOT consume
-- player inventory automatically (that's only done when a bot or player
-- delivers items). So we deduct manually.
local function build_ghosts_in_range(character_unum, radius)
  radius = radius or 10
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local inv = c.get_main_inventory()
  if not inv then return { ok = false, error = 'no main inventory' } end

  local ghosts = c.surface.find_entities_filtered{
    type = 'entity-ghost',
    position = c.position,
    radius = radius,
    force = c.force,
  }

  local built, missing, errors = {}, {}, {}
  for _, ghost in ipairs(ghosts) do
    if not ghost.valid then
      -- could have been built by something else this tick
    else
      local ghost_name = ghost.ghost_name
      local proto = ghost.ghost_prototype
      local items = proto.items_to_place_this
      if not items or #items == 0 then
        table.insert(errors, { name = ghost_name, error = 'no items_to_place_this' })
      else
        local item_name = items[1].name
        local item_count = items[1].count or 1
        if inv.get_item_count(item_name) < item_count then
          table.insert(missing, {
            name = ghost_name,
            needs = item_name,
            count = item_count,
          })
        else
          local _, revived, _ = ghost.revive{ raise_revive = true }
          if revived then
            inv.remove{ name = item_name, count = item_count }
            table.insert(built, {
              name = revived.name,
              position = { x = revived.position.x, y = revived.position.y },
              cost = { name = item_name, count = item_count },
            })
          else
            table.insert(errors, {
              name = ghost_name,
              error = 'revive returned no entity (blocked?)',
              position = { x = ghost.position.x, y = ghost.position.y },
            })
          end
        end
      end
    end
  end

  return {
    ok = true,
    built = built,
    missing = missing,
    errors = errors,
    ghosts_seen = #ghosts,
  }
end


-- ---------- crafting (0.5.0 additions) ----------

local HAND_CRAFT_CATEGORIES = {
  ['crafting'] = true,
  ['advanced-crafting'] = true,
  ['basic-crafting'] = true,
}

local function craft(character_unum, recipe_name, count)
  init_craft_jobs()
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local recipe = prototypes.recipe[recipe_name]
  if not recipe then return { ok = false, error = 'no recipe ' .. recipe_name } end
  if not HAND_CRAFT_CATEGORIES[recipe.category] then
    return { ok = false, error = 'recipe category ' .. recipe.category .. ' is not hand-craftable (need a machine)' }
  end
  for _, ing in ipairs(recipe.ingredients) do
    if ing.type == 'fluid' then
      return { ok = false, error = 'cannot hand-craft recipes with fluid ingredients' }
    end
  end
  -- Up-front ingredient check; we re-check each item as it crafts in case
  -- inventory changes mid-run.
  local inv = c.get_main_inventory()
  if not inv then return { ok = false, error = 'no main inventory' } end
  for _, ing in ipairs(recipe.ingredients) do
    if ing.type == 'item' and inv.get_item_count(ing.name) < ing.amount * count then
      return {
        ok = false, error = 'insufficient ingredient',
        needs = ing.name, need = ing.amount * count,
        have = inv.get_item_count(ing.name),
      }
    end
  end
  local ticks_per_item = math.max(1, math.ceil(recipe.energy * 60))
  storage.craft_jobs[character_unum] = {
    recipe = recipe_name,
    count = count,
    crafted_so_far = 0,
    ticks_per_item = ticks_per_item,
    ticks_left_this_item = ticks_per_item,
    started_tick = game.tick,
  }
  return {
    ok = true, recipe = recipe_name, count = count,
    ticks_per_item = ticks_per_item,
    eta_ticks = ticks_per_item * count,
  }
end

local function get_craft_status(character_unum)
  init_craft_jobs()
  local job = storage.craft_jobs[character_unum]
  if not job then return { status = 'idle' } end
  if job.completed then
    storage.craft_jobs[character_unum] = nil
    return {
      status = job.error and 'error' or 'completed',
      error = job.error,
      recipe = job.recipe,
      crafted = job.crafted_so_far,
      requested = job.count,
      gained = job.gained or {},
    }
  end
  return {
    status = 'crafting',
    recipe = job.recipe,
    crafted = job.crafted_so_far,
    requested = job.count,
    ticks_left_this_item = job.ticks_left_this_item,
  }
end

local function cancel_craft(character_unum)
  init_craft_jobs()
  storage.craft_jobs[character_unum] = nil
  return { ok = true }
end


-- ---------- entity inventory I/O (0.5.0 additions) ----------

-- Find an entity at (x, y) that has any inventory. Returns the entity or nil.
local function find_entity_with_inventory_at(surface, x, y)
  local ents = surface.find_entities_filtered{position={x, y}, radius=0.6}
  for _, e in ipairs(ents) do
    if e.valid and e.get_inventory then return e end
  end
  return nil
end

-- Insert items from character into a specific slot of an entity at (x, y).
-- slot: defines.inventory.* integer (e.g. defines.inventory.fuel, .furnace_source)
local function insert_into_entity(character_unum, x, y, item_name, count, slot)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local ent = find_entity_with_inventory_at(c.surface, x, y)
  if not ent then return { ok = false, error = 'no entity with inventory at (' .. x .. ',' .. y .. ')' } end
  local target_inv = ent.get_inventory(slot)
  if not target_inv then
    return { ok = false, error = 'entity ' .. ent.name .. ' has no inventory slot ' .. tostring(slot) }
  end
  local char_inv = c.get_main_inventory()
  if not char_inv then return { ok = false, error = 'no character inventory' } end
  local have = char_inv.get_item_count(item_name)
  local want = math.min(count or have, have)
  if want <= 0 then return { ok = false, error = 'character has no ' .. item_name } end
  local moved = target_inv.insert{ name = item_name, count = want }
  if moved > 0 then char_inv.remove{ name = item_name, count = moved } end
  return { ok = true, moved = moved, entity = ent.name, target_slot = slot }
end

-- Take items from a specific slot of an entity at (x, y) into character.
local function take_from_entity(character_unum, x, y, item_name, count, slot)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local ent = find_entity_with_inventory_at(c.surface, x, y)
  if not ent then return { ok = false, error = 'no entity with inventory at (' .. x .. ',' .. y .. ')' } end
  local source_inv = ent.get_inventory(slot)
  if not source_inv then
    return { ok = false, error = 'entity ' .. ent.name .. ' has no inventory slot ' .. tostring(slot) }
  end
  local available = source_inv.get_item_count(item_name)
  local want = math.min(count or available, available)
  if want <= 0 then return { ok = false, error = 'entity has no ' .. item_name .. ' in slot ' .. tostring(slot) } end
  local char_inv = c.get_main_inventory()
  local moved = char_inv.insert{ name = item_name, count = want }
  if moved > 0 then source_inv.remove{ name = item_name, count = moved } end
  return { ok = true, moved = moved, entity = ent.name, source_slot = slot }
end


-- ---------- resource discovery (0.5.0 helper) ----------

-- Find the nearest tile of a given resource (iron-ore, copper-ore, coal, stone, ...)
-- to the character, plus how many tiles are in that "patch" (a contiguous-ish
-- region — we approximate by counting tiles of the same resource within 50 of nearest).
local function find_nearest_resource(character_unum, resource_name, max_distance)
  max_distance = max_distance or 500
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local tiles = c.surface.find_entities_filtered{
    name = resource_name, position = c.position, radius = max_distance,
  }
  if #tiles == 0 then
    return { ok = false, error = 'no ' .. resource_name .. ' within ' .. max_distance .. ' tiles' }
  end
  local nearest, nd = nil, math.huge
  for _, t in pairs(tiles) do
    local dx, dy = t.position.x - c.position.x, t.position.y - c.position.y
    local d = dx*dx + dy*dy
    if d < nd then nd = d; nearest = t end
  end
  local patch_count = 0
  for _, t in pairs(tiles) do
    local dx, dy = t.position.x - nearest.position.x, t.position.y - nearest.position.y
    if dx*dx + dy*dy <= 50*50 then patch_count = patch_count + 1 end
  end
  return {
    ok = true,
    position = { x = nearest.position.x, y = nearest.position.y },
    distance = math.sqrt(nd),
    patch_count = patch_count,
    amount = nearest.amount,
  }
end


-- ---------- introspection helpers (0.6.0 additions) ----------

local function get_recipe(recipe_name)
  local r = prototypes.recipe[recipe_name]
  if not r then return { ok = false, error = 'no recipe ' .. recipe_name } end
  local ingredients = {}
  for _, i in ipairs(r.ingredients) do
    table.insert(ingredients, { type = i.type, name = i.name, amount = i.amount })
  end
  local products = {}
  for _, p in ipairs(r.products) do
    table.insert(products, {
      type = p.type, name = p.name,
      amount = p.amount, amount_min = p.amount_min, amount_max = p.amount_max,
      probability = p.probability,
    })
  end
  return {
    ok = true, name = recipe_name,
    category = r.category,
    energy = r.energy,
    ingredients = ingredients,
    products = products,
    hand_craftable = HAND_CRAFT_CATEGORIES[r.category] or false,
  }
end

-- Returns total counts of every item needed to build the ghosts on the
-- character's surface and force. For each ghost we use the first entry of
-- ghost_prototype.items_to_place_this (the canonical placement item).
local function analyze_ghosts(character_unum)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local ghosts = c.surface.find_entities_filtered{ type = 'entity-ghost', force = c.force }
  local counts = {}
  for _, g in ipairs(ghosts) do
    if g.valid then
      local items = g.ghost_prototype.items_to_place_this
      if items and #items > 0 then
        local nm = items[1].name
        local cnt = items[1].count or 1
        counts[nm] = (counts[nm] or 0) + cnt
      end
    end
  end
  local out = {}
  for n, cnt in pairs(counts) do table.insert(out, { name = n, count = cnt }) end
  return { ok = true, items = out, ghost_count = #ghosts }
end

-- Find chests on player force within max_distance that contain item_name.
-- Returns sorted by distance (ascending).
local function find_chests_with_item(character_unum, item_name, max_distance)
  max_distance = max_distance or 500
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local chests = c.surface.find_entities_filtered{
    position = c.position, radius = max_distance,
    type = { 'container', 'logistic-container' }, force = c.force,
  }
  local out = {}
  for _, e in ipairs(chests) do
    if e.valid then
      local inv = e.get_inventory(defines.inventory.chest)
      if inv then
        local cnt = inv.get_item_count(item_name)
        if cnt > 0 then
          local dx, dy = e.position.x - c.position.x, e.position.y - c.position.y
          table.insert(out, {
            position = { x = e.position.x, y = e.position.y },
            count = cnt,
            distance = math.sqrt(dx*dx + dy*dy),
            name = e.name,
          })
        end
      end
    end
  end
  table.sort(out, function(a, b) return a.distance < b.distance end)
  return { ok = true, chests = out }
end

-- Returns the character's main inventory as a list of {name, count}.
local function get_character_inventory(character_unum)
  local c = game.get_entity_by_unit_number(character_unum)
  if not c or not c.valid then return { ok = false, error = 'no character' } end
  local inv = c.get_main_inventory()
  if not inv then return { ok = true, items = {} } end
  local agg = {}
  for _, stack in ipairs(inv.get_contents()) do
    agg[stack.name] = (agg[stack.name] or 0) + stack.count
  end
  local out = {}
  for n, cnt in pairs(agg) do table.insert(out, { name = n, count = cnt }) end
  return { ok = true, items = out }
end


-- ---------- multi-character management (0.10.6) ----------

-- Accept a position as {x=, y=}, {x, y}, or nil (defaults to spawn 0,0).
local function coerce_position(position)
  if type(position) ~= 'table' then return 0, 0 end
  local px = position.x or position[1] or 0
  local py = position.y or position[2] or 0
  return px, py
end

-- Spawn a free-standing character and record it under `name` in the
-- storage.claude_chars map. Returns the new character's unit_number.
local function spawn_named_char(name, position)
  if type(name) ~= 'string' or name == '' then
    return { ok = false, error = 'name must be a non-empty string' }
  end
  init_claude_chars()
  local s = game.surfaces['nauvis'] or game.surfaces[1]
  if not s then return { ok = false, error = 'no surface' } end
  local force = game.forces.player
  local px, py = coerce_position(position)
  local pos = s.find_non_colliding_position('character', { px, py }, 30, 0.5)
  if not pos then
    return { ok = false, error = 'no non-colliding position near (' .. px .. ',' .. py .. ')' }
  end
  local c = s.create_entity{ name = 'character', position = pos, force = force }
  if not (c and c.valid) then
    return { ok = false, error = 'create_entity returned nil' }
  end
  storage.claude_chars[name] = c.unit_number
  return {
    ok = true,
    name = name,
    unit_number = c.unit_number,
    position = { x = c.position.x, y = c.position.y },
  }
end

-- Return the name -> unit_number map (a fresh copy).
local function list_chars()
  init_claude_chars()
  local out = {}
  for k, v in pairs(storage.claude_chars) do out[k] = v end
  return out
end

-- Remove a named character: destroy the entity if it still exists and clear
-- the mapping. Idempotent (removing an unknown name is a no-op).
local function remove_char(name)
  init_claude_chars()
  local unum = storage.claude_chars[name]
  local destroyed = false
  if unum then
    local e = game.get_entity_by_unit_number(unum)
    if e and e.valid then e.destroy(); destroyed = true end
  end
  storage.claude_chars[name] = nil
  return { ok = true, name = name, existed = unum ~= nil, destroyed = destroyed }
end


-- ---------- remote interface registration ----------

remote.add_interface("claude", {
  ping = ping,
  get_chat = get_chat,
  drain_chat = drain_chat,
  set_walking = set_walking,
  walk_to = walk_to,
  get_walk_status = get_walk_status,
  cancel_walk = cancel_walk,
  start_mining = start_mining,
  stop_mining = stop_mining,
  get_mining_status = get_mining_status,
  -- 0.3.0 additions
  place_entity = place_entity,
  transfer_items = transfer_items,
  shoot_at = shoot_at,
  stop_shooting = stop_shooting,
  pick_up_at = pick_up_at,
  -- 0.4.0 additions
  build_ghosts_in_range = build_ghosts_in_range,
  -- 0.5.0 additions
  craft = craft,
  get_craft_status = get_craft_status,
  cancel_craft = cancel_craft,
  insert_into_entity = insert_into_entity,
  take_from_entity = take_from_entity,
  find_nearest_resource = find_nearest_resource,
  -- 0.6.0 additions
  get_recipe = get_recipe,
  analyze_ghosts = analyze_ghosts,
  find_chests_with_item = find_chests_with_item,
  get_character_inventory = get_character_inventory,
  -- 0.10.6 additions: multi-character management
  spawn_named_char = spawn_named_char,
  list_chars = list_chars,
  remove_char = remove_char,
})


-- ============================================================
-- RL ARENA (0.7.0)
-- ============================================================
-- Separate remote interface 'claude_rl' so RL concerns are isolated.
-- An "arena" is a walled rectangle on a surface containing two chests
-- (input and output). The agent (PPO etc.) places entities inside
-- the arena, the world runs forward, we score the result.
--
-- Coordinate convention used here:
--   bounds = { x_min, y_min, x_max, y_max }  -- inclusive, tile-CENTERS
--   tile_idx = (row * width) + col, where col = x - x_min, row = y - y_min
-- Entity ids (for arena_place):
--   0 = transport-belt   (direction matters)
--   1 = inserter         (direction matters: direction the arm RECEIVES from)
--   2 = assembling-machine-1 (3x3, recipe auto-set to iron-gear-wheel)
--   3 = no-op (ends build phase)
-- Direction ids:
--   0 = north (=defines.direction.north = 0)
--   1 = east  (=4)
--   2 = south (=8)
--   3 = west  (=12)

local ENTITY_NAMES = {
  [0] = 'transport-belt',
  [1] = 'inserter',
  [2] = 'assembling-machine-1',
  -- 3 = no-op (handled specially)
}
local DIR_VALUES = { [0] = 0, [1] = 4, [2] = 8, [3] = 12 }

local function arena_chest_unums(a)
  return a.input_chest and a.input_chest.unit_number,
         a.output_chest and a.output_chest.unit_number
end

-- Look up a chest by its STORED POSITION (not unit_number).
-- Factorio 2.0's game.get_entity_by_unit_number only works on entities
-- explicitly registered via script.register_on_entity_destroyed; chests
-- that pre-existed in the save (like JJ's hand-placed arena chests)
-- aren't registered, so get_entity_by_unit_number returns nil for them.
-- find_entities_filtered by position works regardless.
local function arena_find_chest(a, which_key)
  local s = game.surfaces[a.surface_name]
  if not s then return nil end
  local c = a[which_key]
  if not c then return nil end
  local ents = s.find_entities_filtered{
    position = { c.x, c.y }, type = 'container', radius = 0.6,
  }
  return ents[1]
end

local function arena_width(a)  return a.bounds.x_max - a.bounds.x_min + 1 end
local function arena_height(a) return a.bounds.y_max - a.bounds.y_min + 1 end

local function tile_to_position(a, tile_idx)
  local w = arena_width(a)
  local col = tile_idx % w
  local row = math.floor(tile_idx / w)
  return a.bounds.x_min + col, a.bounds.y_min + row
end

-- New arena_setup for 0.8.0: uses two "top-up-valve" entities to mark the
-- grid corners, two "loader" entities for input/output flow, and two
-- containers for plate input + gear output.
--
-- JJ's editor placement convention:
--   2 valves (any type 'valve', any prototype like 'top-up-valve') at the
--     top-left and bottom-right corners of the buildable grid
--   2 loaders just OUTSIDE the grid (one west, one east)
--   2 containers next to the loaders (left = input/iron-plate, right = output/gears)
local function arena_setup(player_name)
  init_arena()
  -- player_name is optional; if no player or nil, use nauvis surface
  -- directly so the function can be called headlessly via RCON.
  local s
  if player_name then
    local p = game.players[player_name]
    if p then s = p.surface end
  end
  if not s then s = game.surfaces.nauvis end
  if not s then return { ok = false, error = 'no surface' } end
  local valves = s.find_entities_filtered{ type = 'valve' }
  if #valves < 2 then
    return { ok = false, error = 'expected 2 valves marking grid corners, found ' .. #valves }
  end
  -- Bounds = bounding box of the valves (inclusive of valve tiles).
  local vminx, vminy = math.huge, math.huge
  local vmaxx, vmaxy = -math.huge, -math.huge
  for _, v in ipairs(valves) do
    if v.position.x < vminx then vminx = v.position.x end
    if v.position.x > vmaxx then vmaxx = v.position.x end
    if v.position.y < vminy then vminy = v.position.y end
    if v.position.y > vmaxy then vmaxy = v.position.y end
  end
  local bounds = {
    x_min = math.floor(vminx),
    y_min = math.floor(vminy),
    x_max = math.floor(vmaxx),
    y_max = math.floor(vmaxy),
  }
  -- Loaders (entry/exit). Look anywhere near the grid.
  local loaders = s.find_entities_filtered{
    type = { 'loader', 'loader-1x1' },
    area = {{ bounds.x_min - 4, bounds.y_min - 4 }, { bounds.x_max + 4, bounds.y_max + 4 }},
  }
  if #loaders < 2 then
    return { ok = false, error = 'expected 2+ loaders near grid, found ' .. #loaders }
  end
  -- Classify: loaders on the WEST side (x < bounds.x_min) are inputs;
  -- loaders on the EAST side (x > bounds.x_max) are outputs.
  local input_loaders, output_loaders = {}, {}
  for _, ld in ipairs(loaders) do
    if ld.position.x < bounds.x_min then
      table.insert(input_loaders, ld)
    elseif ld.position.x > bounds.x_max then
      table.insert(output_loaders, ld)
    end
  end
  if #input_loaders < 1 or #output_loaders < 1 then
    return { ok = false, error = 'need at least 1 input + 1 output loader' }
  end
  -- Sort inputs by Y so chest[i] pairs with loader[i] predictably.
  table.sort(input_loaders, function(a, b) return a.position.y < b.position.y end)
  table.sort(output_loaders, function(a, b) return a.position.y < b.position.y end)
  -- Chests near the loaders.
  local chests = s.find_entities_filtered{
    type = 'container',
    area = {{ bounds.x_min - 5, bounds.y_min - 5 }, { bounds.x_max + 5, bounds.y_max + 5 }},
  }
  local input_chests, output_chests = {}, {}
  for _, c in ipairs(chests) do
    if c.position.x < bounds.x_min then
      table.insert(input_chests, c)
    elseif c.position.x > bounds.x_max then
      table.insert(output_chests, c)
    end
  end
  if #input_chests < 1 or #output_chests < 1 then
    return { ok = false, error = 'need at least 1 input + 1 output chest' }
  end
  table.sort(input_chests, function(a, b) return a.position.y < b.position.y end)
  table.sort(output_chests, function(a, b) return a.position.y < b.position.y end)
  -- Build list forms (new) plus single-form backward-compat fields.
  local function pos_struct(e)
    return { x = e.position.x, y = e.position.y, unit_number = e.unit_number }
  end
  local in_c = input_chests[1]
  local out_c = output_chests[1]
  local in_ld = input_loaders[1]
  local out_ld = output_loaders[1]
  local input_chest_list = {}
  for _, c in ipairs(input_chests) do table.insert(input_chest_list, pos_struct(c)) end
  local input_loader_list = {}
  for _, l in ipairs(input_loaders) do table.insert(input_loader_list, pos_struct(l)) end
  storage.arena = {
    surface_name = s.name,
    bounds = bounds,
    -- Backward-compat fields (used everywhere; first input/output entity)
    input_chest = pos_struct(in_c),
    output_chest = pos_struct(out_c),
    input_loader = { x = in_ld.position.x, y = in_ld.position.y },
    output_loader = { x = out_ld.position.x, y = out_ld.position.y },
    -- New: full lists for multi-input setups (e.g. circuits with 2 belts).
    input_chests = input_chest_list,
    input_loaders = input_loader_list,
    valves = { { x = vminx, y = vminy }, { x = vmaxx, y = vmaxy } },
    target_output = 10,
    refill_amount = 100,
    recipe_name = 'iron-gear-wheel',
    output_item = 'iron-gear-wheel',
    input_item = 'iron-plate',
    input_items = nil,  -- if set, distributes across input_chests by index
    sim_max_ticks = 900,
    simulating = false,
    invalid_actions = 0,
    episode_start_tick = nil,
  }
  return {
    ok = true,
    bounds = bounds,
    width = arena_width(storage.arena),
    height = arena_height(storage.arena),
    input_chest = storage.arena.input_chest,
    output_chest = storage.arena.output_chest,
    input_loader = storage.arena.input_loader,
    output_loader = storage.arena.output_loader,
    valves = storage.arena.valves,
    surface = s.name,
  }
end

local function arena_get_constants()
  init_arena()
  if not storage.arena.bounds then return { ok = false, error = 'arena not set up' } end
  return {
    ok = true,
    width = arena_width(storage.arena),
    height = arena_height(storage.arena),
    bounds = storage.arena.bounds,
    n_entities = 4,             -- 0..2 + no-op
    n_directions = 4,           -- N/E/S/W
    target_output = storage.arena.target_output,
    refill_amount = storage.arena.refill_amount,
    input_item = storage.arena.input_item,
    input_items = storage.arena.input_items,
    output_item = storage.arena.output_item,
    recipe_name = storage.arena.recipe_name,
    sim_max_ticks = storage.arena.sim_max_ticks,
  }
end

-- Wipe everything inside bounds except the two chests; refill input;
-- empty output. Returns a tiny status struct.
local function arena_reset()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  local s = game.surfaces[a.surface_name]
  if not s then return { ok = false, error = 'arena surface gone' } end
  local in_un, out_un = arena_chest_unums(a)
  -- Skip pausing the world during reset — game.speed = 0 is illegal
  -- (minimum 0.01) and reset is a one-tick atomic op anyway.
  a.simulating = false
  a.sim_started_tick = nil
  a.sim_ticks_taken = nil
  a.sim_final_output = nil
  a.sim_timed_out = nil
  a.invalid_actions = 0
  local removed = 0
  -- Tighter reset area: only entities WHOSE POSITION is strictly inside
  -- the bounds, so we don't destroy walls/valves/loaders at the boundary.
  local ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
  }
  -- Build a skip-set of fixed entity types we never destroy.
  local SKIP_TYPES = {
    ['wall'] = true, ['valve'] = true, ['loader'] = true,
    ['loader-1x1'] = true, ['container'] = true,
    ['logistic-container'] = true, ['character'] = true,
    ['electric-energy-interface'] = true, ['electric-pole'] = true,
    ['pipe'] = true, ['pipe-to-ground'] = true,
  }
  for _, e in ipairs(ents) do
    if e.valid
       and e.unit_number ~= in_un and e.unit_number ~= out_un
       and not SKIP_TYPES[e.type] then
      e.destroy{}
      removed = removed + 1
    end
  end
  -- Refill input chest(s), empty output chest.
  -- Multi-input case: distribute a.input_items across a.input_chests by index.
  -- Single-input case: all items go into the single input chest.
  local out_c = arena_find_chest(a, 'output_chest')
  if a.input_chests and #a.input_chests > 1 and a.input_items and #a.input_items >= 1 then
    for i, chest_info in ipairs(a.input_chests) do
      -- Tight radius (0.4) so 1-tile-apart chests don't alias to the same entity.
      local c = s.find_entities_filtered{
        position = { chest_info.x, chest_info.y }, type = 'container', radius = 0.4,
      }[1]
      if c and c.valid then
        local inv = c.get_inventory(defines.inventory.chest)
        if inv then
          inv.clear()
          local it = a.input_items[i]  -- nil if more chests than items
          if it then inv.insert{ name = it.name, count = it.count } end
        end
      end
    end
  else
    local in_c = arena_find_chest(a, 'input_chest')
    if in_c and in_c.valid then
      local inv = in_c.get_inventory(defines.inventory.chest)
      if inv then
        inv.clear()
        if a.input_items and #a.input_items > 0 then
          for _, it in ipairs(a.input_items) do
            inv.insert{ name = it.name, count = it.count }
          end
        else
          inv.insert{ name = a.input_item, count = a.refill_amount }
        end
      end
    end
  end
  if out_c and out_c.valid then
    local inv = out_c.get_inventory(defines.inventory.chest)
    if inv then inv.clear() end
  end
  -- Clear items sitting on BOTH loaders so each episode starts fresh.
  -- Also DISABLE the loaders (.active = false) so they don't pull items
  -- from the input chest during the build phase. arena_start_simulate
  -- re-enables them. Without this, the input loader pulls 1 plate the
  -- instant we refill, and the chest shows 9 instead of 10 (the
  -- 10th plate is on the loader belt).
  local function clear_and_disable_loader(pos)
    if not pos then return end
    local loaders = s.find_entities_filtered{
      position = { pos.x, pos.y },
      type = { 'loader', 'loader-1x1' }, radius = 1.0,
    }
    for _, ld in ipairs(loaders) do
      if ld.valid then
        if ld.get_max_transport_line_index then
          local n = ld.get_max_transport_line_index()
          for i = 1, n do
            local tl = ld.get_transport_line(i)
            if tl then tl.clear() end
          end
        end
        ld.active = false
      end
    end
  end
  clear_and_disable_loader(a.input_loader)
  clear_and_disable_loader(a.output_loader)
  -- Also disable any additional input loaders from the multi-input list.
  if a.input_loaders then
    for _, ld_pos in ipairs(a.input_loaders) do
      clear_and_disable_loader(ld_pos)
    end
  end
  -- Also clear any dropped items inside the arena (item-on-ground entities
  -- pile up when inserters drop on empty tiles).
  local stragglers = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'item-on-ground',
  }
  for _, e in ipairs(stragglers) do
    if e.valid then e.destroy(); removed = removed + 1 end
  end
  a.episode_start_tick = game.tick
  a.placements_count = 0
  -- Reset panel to show the new task ready.
  do
    local lines = {
      string.format("READY  %s -> %s  target=%d",
        a.recipe_name or '?', a.output_item or '?', a.target_output or 0),
      "(awaiting first placement)",
      "",
    }
    update_arena_panel(a, s, lines, {r=0.7, g=1, b=0.7})
  end
  return { ok = true, removed = removed, episode_start_tick = a.episode_start_tick }
end

-- Build the (height, width, 12) observation as a flat array (row-major),
-- plus a small globals vector. Returns serializable JSON.
local function arena_get_observation()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  local s = game.surfaces[a.surface_name]
  local w, h = arena_width(a), arena_height(a)
  -- 10 channels (was 12; dropped chest channels 10/11 which were never set
  -- because chests are OUTSIDE arena bounds and find_entities_filtered
  -- targets the arena interior). For 16x16: 16*16*10+3=2563 dims (was 3075).
  local n_channels = 10
  -- Channel layout:
  --   0: empty
  --   1..4: belt direction (N/E/S/W)
  --   5..8: inserter direction (N/E/S/W)
  --   9: assembler anchor
  local grid = {}
  for i = 1, w * h * n_channels do grid[i] = 0 end
  local function idx(col, row, ch) return ((row * w) + col) * n_channels + ch + 1 end
  for col = 0, w - 1 do
    for row = 0, h - 1 do
      grid[idx(col, row, 0)] = 1
    end
  end
  local ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min - 0.5, a.bounds.y_min - 0.5 },
            { a.bounds.x_max + 0.5, a.bounds.y_max + 0.5 }},
  }
  -- Chest unit_numbers (still needed for the globals' input/output counts).
  local in_un, out_un = arena_chest_unums(a)
  local function set_channel(col, row, ch)
    if col < 0 or col >= w or row < 0 or row >= h then return end
    grid[idx(col, row, 0)] = 0
    grid[idx(col, row, ch)] = 1
  end
  for _, e in ipairs(ents) do
    if e.valid then
      local col = math.floor(e.position.x - a.bounds.x_min + 0.0)
      local row = math.floor(e.position.y - a.bounds.y_min + 0.0)
      if e.name == 'transport-belt' then
        local d = e.direction or 0
        local ch = ({ [0] = 1, [4] = 2, [8] = 3, [12] = 4 })[d] or 1
        set_channel(col, row, ch)
      elseif e.name == 'inserter' then
        local d = e.direction or 0
        local ch = ({ [0] = 5, [4] = 6, [8] = 7, [12] = 8 })[d] or 5
        set_channel(col, row, ch)
      elseif e.name == 'assembling-machine-1' then
        local acol = math.floor(e.position.x - a.bounds.x_min - 1 + 0.0)
        local arow = math.floor(e.position.y - a.bounds.y_min - 1 + 0.0)
        set_channel(acol, arow, 9)
      end
    end
  end
  -- Globals
  local elapsed = a.episode_start_tick and (game.tick - a.episode_start_tick) or 0
  local in_c = game.get_entity_by_unit_number(in_un)
  local out_c = game.get_entity_by_unit_number(out_un)
  local in_count = (in_c and in_c.valid) and in_c.get_inventory(defines.inventory.chest).get_item_count(a.input_item) or 0
  local out_count = (out_c and out_c.valid) and out_c.get_inventory(defines.inventory.chest).get_item_count(a.output_item) or 0
  return {
    ok = true,
    grid = grid,
    width = w, height = h, channels = n_channels,
    globals = {
      tick_in_episode = math.min(1.0, elapsed / (a.sim_max_ticks * 2)),
      output_count = out_count,
      input_count = in_count,
    },
  }
end

-- Place an entity. Returns {ok, error, noop, penalty, placed_name}.
local function arena_place(entity_idx, tile_idx, dir_idx)
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  if entity_idx == 3 then return { ok = true, noop = true } end
  local name = ENTITY_NAMES[entity_idx]
  if not name then
    a.invalid_actions = a.invalid_actions + 1
    return { ok = false, error = 'bad entity_idx ' .. tostring(entity_idx), penalty = 1 }
  end
  local direction = DIR_VALUES[dir_idx] or 0
  local x, y = tile_to_position(a, tile_idx)
  -- For assembler (3x3), the position must offset by +1, +1 from anchor
  -- so the 3x3 is fully inside bounds. We do bounds check accordingly.
  if name == 'assembling-machine-1' then
    if x < a.bounds.x_min + 1 or x > a.bounds.x_max - 1 or
       y < a.bounds.y_min + 1 or y > a.bounds.y_max - 1 then
      a.invalid_actions = a.invalid_actions + 1
      return { ok = false, error = 'assembler would extend outside arena', penalty = 1 }
    end
  end
  local s = game.surfaces[a.surface_name]
  local position = { x + 0.5, y + 0.5 }  -- tile-centered
  if not s.can_place_entity{ name = name, position = position, force = 'player', direction = direction } then
    a.invalid_actions = a.invalid_actions + 1
    return { ok = false, error = 'cannot place ' .. name .. ' at (' .. position[1] .. ',' .. position[2] .. ')', penalty = 1 }
  end
  local e = s.create_entity{
    name = name, position = position, force = 'player', direction = direction, raise_built = true,
  }
  if not e then
    a.invalid_actions = a.invalid_actions + 1
    return { ok = false, error = 'create_entity returned nil', penalty = 1 }
  end
  if name == 'assembling-machine-1' then
    -- Multi-product chains (0.10.0): if `a.recipe_options` is set, use
    -- direction-as-recipe-index. dir_idx 0/1/2/3 -> recipe_options[1..4].
    -- Falls back to a.recipe_name when no options are configured (single-
    -- recipe tasks like gears, cables, circuits-initial).
    local recipe_for_this_asm = a.recipe_name or 'iron-gear-wheel'
    if a.recipe_options and a.recipe_options[dir_idx + 1] then
      recipe_for_this_asm = a.recipe_options[dir_idx + 1]
    end
    pcall(function() e.set_recipe(recipe_for_this_asm) end)
  end
  -- Compute incremental chain bonus: how much this placement contributes to
  -- a working chain RIGHT NOW. Bonuses are SMALL (max ~3 per placement) so
  -- the agent can't farm them — actual production must dominate the reward.
  local chain_bonus = 0
  local belt_offsets = { [0]={0,-1}, [4]={1,0}, [8]={0,1}, [12]={-1,0} }
  if name == 'transport-belt' then
    local off = belt_offsets[direction]
    if off then
      -- Belt continuity bonus boosted from +1/+1 to +5/+5 (0.9.8) — explicit
      -- strong gradient for "extend the belt chain" so PPO can find belts
      -- that bridge from the asm output to the output loader (which has been
      -- the cable/belt 16x16 plateau).
      local front = s.find_entities_filtered{
        position = { e.position.x + off[1], e.position.y + off[2] },
        name = 'transport-belt', radius = 0.4,
      }[1]
      if front and front.valid then chain_bonus = chain_bonus + 5 end
      local back = s.find_entities_filtered{
        position = { e.position.x - off[1], e.position.y - off[2] },
        name = 'transport-belt', radius = 0.4,
      }[1]
      if back and back.valid and back.direction == direction then
        chain_bonus = chain_bonus + 5
      end
      -- Output-loader proximity bonus: ANY east-facing belt on the output
      -- loader's row gets a bonus that scales with closeness. 0.9.12: range
      -- extended from dx<=6 to dx<=12 so the entire row-7-east corridor
      -- between the asm and the loader rewards placement, not just the
      -- last 6 tiles. Strong gradient for "place belts to bridge to loader".
      if direction == 4 and a.output_loader then
        local dx = math.abs((e.position.x + 1) - a.output_loader.x)
        local dy = math.abs(e.position.y - a.output_loader.y)
        if dy < 1.0 and dx <= 12 then
          chain_bonus = chain_bonus + (13 - dx)  -- +12 next to loader, +1 12 tiles away
        end
      end
    end
  elseif name == 'inserter' then
    local recipe_name = a.recipe_name or 'iron-gear-wheel'
    -- 0.10.3: build set of "chain-relevant" recipes — primary + any recipe_options.
    -- Inserter feeding ANY of those asms gets the full +3 bonus, not just the primary.
    local chain_recipes = { [recipe_name] = true }
    if a.recipe_options then
      for _, rname in pairs(a.recipe_options) do chain_recipes[rname] = true end
    end
    local drop_asm = s.find_entities_filtered{
      position = e.drop_position, name = 'assembling-machine-1', radius = 1.0,
    }[1]
    if drop_asm and drop_asm.valid then
      local rec = drop_asm.get_recipe()
      if rec and chain_recipes[rec.name] then chain_bonus = chain_bonus + 3
      else chain_bonus = chain_bonus + 1 end
    end
    local drop_belt = s.find_entities_filtered{
      position = e.drop_position, name = 'transport-belt', radius = 0.4,
    }[1]
    if drop_belt and drop_belt.valid then chain_bonus = chain_bonus + 2 end
    local pickup_belt = s.find_entities_filtered{
      position = e.pickup_position, name = 'transport-belt', radius = 0.4,
    }[1]
    if pickup_belt and pickup_belt.valid then chain_bonus = chain_bonus + 2 end
    local pickup_asm = s.find_entities_filtered{
      position = e.pickup_position, name = 'assembling-machine-1', radius = 1.0,
    }[1]
    if pickup_asm and pickup_asm.valid then
      local rec = pickup_asm.get_recipe()
      if rec and chain_recipes[rec.name] then chain_bonus = chain_bonus + 2 end
    end
  elseif name == 'assembling-machine-1' then
    local nearby = s.find_entities_filtered{
      area = {{ e.position.x - 2.5, e.position.y - 2.5 },
              { e.position.x + 2.5, e.position.y + 2.5 }},
      name = 'inserter',
    }
    for _, ins in ipairs(nearby) do
      if ins.valid then
        local d = ins.drop_position
        if math.abs(d.x - e.position.x) < 1.5 and math.abs(d.y - e.position.y) < 1.5 then
          chain_bonus = chain_bonus + 3
        end
        local p = ins.pickup_position
        if math.abs(p.x - e.position.x) < 1.5 and math.abs(p.y - e.position.y) < 1.5 then
          chain_bonus = chain_bonus + 2
        end
      end
    end
  end
  -- Live build-phase panel update: show what's been placed so far so JJ
  -- can read progress in-game without waiting for the sim phase.
  do
    local n_placed = (a.placements_count or 0) + 1
    a.placements_count = n_placed
    local lines = {
      string.format("BUILDING  action #%d (chain_bonus=%+d)", n_placed, chain_bonus),
      string.format("recipe: %s -> %s  target=%d",
        a.recipe_name or '?', a.output_item or '?', a.target_output or 0),
      "(panel updates on each placement)",
    }
    update_arena_panel(a, s, lines, {r=1, g=0.9, b=0.4})
  end
  return {
    ok = true,
    placed_name = e.name,
    position = { x = e.position.x, y = e.position.y },
    chain_bonus = chain_bonus,
  }
end

local function arena_start_simulate(max_ticks)
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  a.sim_max_ticks = max_ticks or a.sim_max_ticks
  a.sim_started_tick = game.tick
  a.simulating = true
  -- Defensive: clear input-loader items + RE-ENABLE both loaders
  -- (arena_reset disables them so they don't drain plates during the
  -- build phase). Without re-enabling here, no plates flow into the
  -- chain when simulate starts.
  local s2 = game.surfaces[a.surface_name]
  local function clear_and_enable_loader(pos)
    if not pos or not s2 then return end
    local loaders = s2.find_entities_filtered{
      position = { pos.x, pos.y },
      type = { 'loader', 'loader-1x1' }, radius = 1.0,
    }
    for _, ld in ipairs(loaders) do
      if ld.valid then
        if ld.get_max_transport_line_index then
          local n = ld.get_max_transport_line_index()
          for i = 1, n do
            local tl = ld.get_transport_line(i)
            if tl then tl.clear() end
          end
        end
        ld.active = true
      end
    end
  end
  clear_and_enable_loader(a.input_loader)
  clear_and_enable_loader(a.output_loader)
  if a.input_loaders then
    for _, ld_pos in ipairs(a.input_loaders) do
      clear_and_enable_loader(ld_pos)
    end
  end
  a.sim_ticks_taken = nil
  a.sim_final_output = nil
  a.sim_timed_out = nil
  a.sim_error = nil
  a.sim_calls_count = 0
  a.last_tick_processed = nil
  a.last_count_seen = nil
  a.last_elapsed_seen = nil
  -- Force the world unpaused. auto_pause:true in server-settings keeps
  -- the world paused when no players are connected — that breaks RL
  -- training where we want headless episodes. Override here.
  game.tick_paused = false
  game.speed = 64
  return { ok = true, max_ticks = a.sim_max_ticks, tick_paused = game.tick_paused }
end

local function arena_get_sim_status()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  return {
    ok = true,
    simulating = a.simulating or false,
    ticks_taken = a.sim_ticks_taken,
    final_output = a.sim_final_output,
    timed_out = a.sim_timed_out or false,
    sim_error = a.sim_error,
    sim_calls_count = a.sim_calls_count,
    last_tick_processed = a.last_tick_processed,
    last_count_seen = a.last_count_seen,
    last_elapsed_seen = a.last_elapsed_seen,
    current_tick = game.tick,
    game_speed = game.speed,
    sim_started_tick = a.sim_started_tick,
    output_now = (function()
      local out_c = arena_find_chest(a, 'output_chest')
      if not out_c or not out_c.valid then return -1 end
      local inv = out_c.get_inventory(defines.inventory.chest)
      return inv and inv.get_item_count(a.output_item) or 0
    end)(),
  }
end

-- Compute the final reward based on world state after simulate. The
-- bridge calls this once at episode end.
local function arena_score()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  local s = game.surfaces[a.surface_name]
  local out_c = arena_find_chest(a, 'output_chest')
  local out_count = (out_c and out_c.valid) and out_c.get_inventory(defines.inventory.chest).get_item_count(a.output_item) or 0
  local reached = out_count >= a.target_output
  local ticks_taken = a.sim_ticks_taken or a.sim_max_ticks
  local components = {}
  local total = 0
  -- BIG: per-gear reward dominates. Counts gears ANYWHERE in the arena
  -- (chest + on belts + in inserter hands), so even partial progress
  -- ("first gear ever made") gets immediate signal.
  local gears_total = out_count
  local gears_belts = 0
  local gears_inserters = 0
  for _, b in ipairs(s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'transport-belt',
  }) do
    if b.valid then
      for i = 1, b.get_max_transport_line_index() do
        local tl = b.get_transport_line(i)
        if tl then
          for _, st in ipairs(tl.get_contents()) do
            if st.name == a.output_item then
              gears_belts = gears_belts + st.count
            end
          end
        end
      end
    end
  end
  for _, ins in ipairs(s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'inserter',
  }) do
    if ins.valid and ins.held_stack and ins.held_stack.valid_for_read
       and ins.held_stack.name == a.output_item then
      gears_inserters = gears_inserters + ins.held_stack.count
    end
  end
  -- Also count items currently being crafted / sitting in any asm's
  -- output buffer in the arena. Partial credit for "the asm is working,
  -- it just hasn't been picked up yet."
  local gears_in_asm = 0
  for _, asm in ipairs(s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'assembling-machine-1',
  }) do
    if asm.valid then
      local oi = asm.get_output_inventory()
      if oi then gears_in_asm = gears_in_asm + (oi.get_item_count(a.output_item) or 0) end
    end
  end
  gears_total = gears_total + gears_belts + gears_inserters + gears_in_asm
  components.gears_in_chest = out_count
  components.gears_on_belts = gears_belts
  components.gears_in_inserters = gears_inserters
  components.gears_in_asm = gears_in_asm
  components.gears_total = gears_total
  --   chest: 100 (FULL credit — JJ wants circuits BIG)
  --   asm output: 25  (just needs an output inserter to pick)
  --   inserter hand: 20 (item is being moved)
  --   belt: 12 (item is in transit on a belt)
  components.per_gear_reward =
      out_count * 100
    + gears_in_asm * 25
    + gears_inserters * 20
    + gears_belts * 12
  total = total + components.per_gear_reward

  -- 0.10.1: intermediate-product + inserter-bridging bonuses (multi-product
  -- chains). Tier per JJ: inserter holding cable/input is HIGHEST partial
  -- signal (= bridge between asms is built), circuits in chest is biggest
  -- absolute reward, cables in transit get smaller credit.
  local intermediate_items = {}
  if a.recipe_options then
    for _, rname in pairs(a.recipe_options) do
      local rproto = prototypes.recipe[rname]
      if rproto and rproto.products then
        for _, prod in pairs(rproto.products) do
          if prod.name and prod.name ~= a.output_item then
            intermediate_items[prod.name] = true
          end
        end
      end
    end
  end
  local input_items_set = {}
  if a.input_items then
    for _, it in ipairs(a.input_items) do
      if it.name then input_items_set[it.name] = true end
    end
  end
  local intermediate_count = 0       -- cables in transit
  local input_in_transit_count = 0   -- iron / copper plates on belts + asm input bufs
  local inserter_bridging_count = 0  -- inserter holding ANY component of the chain
  local arena_area = {{ a.bounds.x_min, a.bounds.y_min },
                     { a.bounds.x_max + 1, a.bounds.y_max + 1 }}
  -- Items on belts: intermediate (cable) OR input (plate) == "components of the chain"
  for _, b in ipairs(s.find_entities_filtered{ area = arena_area, name = 'transport-belt' }) do
    if b.valid then
      for i = 1, b.get_max_transport_line_index() do
        local tl = b.get_transport_line(i)
        if tl then
          for _, st in ipairs(tl.get_contents()) do
            if intermediate_items[st.name] then
              intermediate_count = intermediate_count + st.count
            elseif input_items_set[st.name] then
              input_in_transit_count = input_in_transit_count + st.count
            end
          end
        end
      end
    end
  end
  -- Asm inventories: cables in output, plates+cables in input
  for _, asm in ipairs(s.find_entities_filtered{ area = arena_area, name = 'assembling-machine-1' }) do
    if asm.valid then
      local oi = asm.get_output_inventory()
      if oi then
        for iname, _ in pairs(intermediate_items) do
          intermediate_count = intermediate_count + (oi.get_item_count(iname) or 0)
        end
      end
      local ii = asm.get_inventory(defines.inventory.assembling_machine_input)
      if ii then
        for iname, _ in pairs(input_items_set) do
          input_in_transit_count = input_in_transit_count + (ii.get_item_count(iname) or 0)
        end
        for iname, _ in pairs(intermediate_items) do
          intermediate_count = intermediate_count + (ii.get_item_count(iname) or 0)
        end
      end
    end
  end
  -- Inserter bridging: count inserters holding any chain-relevant item
  for _, ins in ipairs(s.find_entities_filtered{ area = arena_area, name = 'inserter' }) do
    if ins.valid and ins.held_stack and ins.held_stack.valid_for_read then
      local held = ins.held_stack.name
      if intermediate_items[held] or input_items_set[held] then
        inserter_bridging_count = inserter_bridging_count + 1
      end
    end
  end
  components.intermediate_in_transit = intermediate_count
  components.input_in_transit = input_in_transit_count
  components.inserter_bridging = inserter_bridging_count
  -- Tier (JJ): cables/inputs in transit (small) < circuits in chest (*100) < inserter bridging (per-action HIGH)
  components.intermediate_reward = intermediate_count * 6
  components.input_in_transit_reward = input_in_transit_count * 4
  components.inserter_bridging_reward = inserter_bridging_count * 35
  total = total
        + components.intermediate_reward
        + components.input_in_transit_reward
        + components.inserter_bridging_reward

  if reached then
    -- Speed bonus 3x stronger (0.1 -> 0.3) so reaching target FAST (= more
    -- parallel chains) wins big. Multi-machine bonus below piles on top.
    local base = (a.sim_max_ticks - ticks_taken) * 0.3
    components.speed_bonus = base
    total = total + base
    -- Massive reached bonus so achieving the goal dwarfs anything farmable.
    components.reached_bonus = 1000
    total = total + 1000
  elseif out_count == 0 then
    -- Heavy penalty for 0 production — placing entities without actually
    -- producing should be net-negative even with maxed chain bonuses.
    components.base = -200
    total = total - 200
  else
    components.partial_output = out_count
  end
  -- Count functional inserters and useless belts inside arena.
  local ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min - 0.5, a.bounds.y_min - 0.5 },
            { a.bounds.x_max + 0.5, a.bounds.y_max + 0.5 }},
  }
  local functional_inserters = 0
  local useless_belts = 0
  local belt_positions = {}
  for _, e in ipairs(ents) do
    if e.valid then
      if e.name == 'inserter' then
        local src = s.find_entity('transport-belt', e.pickup_position) or
                    s.find_entity('iron-chest', e.pickup_position) or
                    s.find_entity('steel-chest', e.pickup_position) or
                    s.find_entity('assembling-machine-1', e.pickup_position)
        local dst = s.find_entity('transport-belt', e.drop_position) or
                    s.find_entity('iron-chest', e.drop_position) or
                    s.find_entity('steel-chest', e.drop_position) or
                    s.find_entity('assembling-machine-1', e.drop_position)
        if src and dst then functional_inserters = functional_inserters + 1 end
      elseif e.name == 'transport-belt' then
        belt_positions[#belt_positions + 1] = { x = e.position.x, y = e.position.y, dir = e.direction }
      end
    end
  end
  -- Useless belt: no neighbor in either pickup or drop direction.
  for _, b in ipairs(belt_positions) do
    local has_neighbor = false
    for _, b2 in ipairs(belt_positions) do
      if b ~= b2 then
        local dx = math.abs(b.x - b2.x); local dy = math.abs(b.y - b2.y)
        if (dx <= 1 and dy < 0.1) or (dy <= 1 and dx < 0.1) then has_neighbor = true; break end
      end
    end
    if not has_neighbor then useless_belts = useless_belts + 1 end
  end
  components.functional_inserters = functional_inserters
  -- functional_inserter_bonus addition is DEFERRED to after chain_alive is
  -- computed below; we conditionally apply it then. Penalties always apply.
  components.useless_belts = useless_belts
  components.useless_belt_penalty = -5 * useless_belts
  total = total - 5 * useless_belts
  components.invalid_actions = a.invalid_actions
  components.invalid_action_penalty = -1 * a.invalid_actions
  total = total - a.invalid_actions

  -- ============================================================
  -- ACTIVITY REWARD (0.8.7): rewards what's ACTUALLY WORKING after
  -- the simulate phase, not just structural placement. Weighted so
  -- the agent can't farm reward by spamming belts:
  --   assembler crafting/producing: +30  (the heart of the chain)
  --   inserter holding an item:     +5
  --   belt carrying any item:       +0.5  (small — many belts != smart)
  -- ============================================================
  local active_belts = 0
  local active_inserters = 0
  local active_assemblers = 0
  local belt_ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'transport-belt',
  }
  for _, b in ipairs(belt_ents) do
    if b.valid then
      local has_item = false
      for i = 1, b.get_max_transport_line_index() do
        local tl = b.get_transport_line(i)
        if tl and #tl > 0 then has_item = true; break end
      end
      if has_item then active_belts = active_belts + 1 end
    end
  end
  local inserter_ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'inserter',
  }
  for _, ins in ipairs(inserter_ents) do
    if ins.valid and ins.held_stack and ins.held_stack.valid_for_read
       and ins.held_stack.count > 0 then
      active_inserters = active_inserters + 1
    end
  end
  local asm_ents = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min },
            { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'assembling-machine-1',
  }
  for _, asm in ipairs(asm_ents) do
    if asm.valid then
      if (asm.crafting_progress and asm.crafting_progress > 0)
         or (asm.products_finished and asm.products_finished > 0) then
        active_assemblers = active_assemblers + 1
      end
    end
  end
  components.active_belts = active_belts
  components.active_inserters = active_inserters
  components.active_assemblers = active_assemblers
  -- "Chain is doing something real" gate: an assembler is actively crafting
  -- OR an inserter is currently holding an item. If false, all the
  -- exploitable bonuses (activity, chain_pts, neighborhood, functional
  -- inserter) are ZEROED so the agent can't farm them by placing
  -- decorative-looking entities that don't produce.
  local chain_alive = (active_assemblers > 0) or (active_inserters > 0)
  components.chain_alive = chain_alive
  if chain_alive then
    components.activity_reward = active_belts * 0.5 + active_inserters * 5 + active_assemblers * 30
    components.functional_inserter_bonus = 10 * functional_inserters
    -- Multi-machine bonus (0.9.8): pay +80 per ACTIVE assembler beyond the first.
    -- Strongly incentivizes parallel chains in the 16x16 arena.
    if active_assemblers > 1 then
      components.multi_machine_bonus = (active_assemblers - 1) * 80
    else
      components.multi_machine_bonus = 0
    end
  else
    components.activity_reward = 0
    components.functional_inserter_bonus = 0
    components.multi_machine_bonus = 0
  end
  total = total + components.activity_reward + components.functional_inserter_bonus + components.multi_machine_bonus

  -- Graph-walk chain reward: trace from input loader east through belts ->
  -- inserter -> gear assembler -> inserter -> belts -> output loader. Each
  -- link found = points. Encourages partial chains too (so the agent gets
  -- gradient even before reaching full connectivity).
  local chain_pts = 0
  local chain = {}
  if a.input_loader and a.output_loader then
    -- Step 1: follow belt chain east from input loader.
    -- loader.x is the loader entity center (a half-tile offset from the first
    -- interior tile center). Step +1.5 lands on the first east tile's center
    -- so radius=0.4 finds the belt there.
    local cur_x = a.input_loader.x + 1.5
    local cur_y = a.input_loader.y
    local in_belts = 0
    while in_belts < 30 do
      local b = s.find_entities_filtered{
        position = { cur_x, cur_y }, name = 'transport-belt', radius = 0.4,
      }[1]
      if not b then break end
      if b.direction ~= 4 then break end  -- east-flowing only
      in_belts = in_belts + 1
      cur_x = cur_x + 1
    end
    chain.input_belts = in_belts
    chain_pts = chain_pts + 5 * in_belts
    -- The "source tile" for the input inserter to pick from is either the
    -- last belt in the chain OR the input loader itself (direct insert).
    local source_x = (in_belts > 0) and (cur_x - 1) or a.input_loader.x
    local source_y = a.input_loader.y

    -- Step 2: inserter whose pickup is on the source tile.
    local input_inserter = nil
    for _, ins in ipairs(s.find_entities_filtered{
      name = 'inserter',
      area = {{source_x - 2, source_y - 2}, {source_x + 2, source_y + 2}},
    }) do
      if math.abs(ins.pickup_position.x - source_x) < 0.5
         and math.abs(ins.pickup_position.y - source_y) < 0.5 then
        input_inserter = ins; break
      end
    end
    if input_inserter then
      chain.input_inserter = true
      chain_pts = chain_pts + 20

      -- Step 3: drop position should be an assembler with gear recipe.
      local d = input_inserter.drop_position
      local asm = s.find_entities_filtered{
        position = { d.x, d.y }, name = 'assembling-machine-1', radius = 1.5,
      }[1]
      if asm then
        local rec = asm.get_recipe()
        if rec and rec.name == (a.recipe_name or 'iron-gear-wheel') then
          chain.gear_assembler = true
          chain_pts = chain_pts + 30

          -- Step 4: output inserter near assembler, NOT the input one.
          local output_inserter = nil
          for _, ins2 in ipairs(s.find_entities_filtered{
            name = 'inserter',
            area = {
              { asm.position.x - 2.5, asm.position.y - 2.5 },
              { asm.position.x + 2.5, asm.position.y + 2.5 },
            },
          }) do
            if ins2.unit_number ~= input_inserter.unit_number then
              local px = ins2.pickup_position.x
              local py = ins2.pickup_position.y
              if math.abs(px - asm.position.x) <= 1.5
                 and math.abs(py - asm.position.y) <= 1.5 then
                output_inserter = ins2; break
              end
            end
          end
          if output_inserter then
            chain.output_inserter = true
            chain_pts = chain_pts + 20

            local d2 = output_inserter.drop_position
            -- Step 5a: drop directly onto output loader -> full chain.
            -- Boosted in 0.9.9 from +60 to +200 since this IS chain completion.
            if math.abs(d2.x - a.output_loader.x) < 1.5
               and math.abs(d2.y - a.output_loader.y) < 1.5 then
              chain.direct_output_loader = true
              chain_pts = chain_pts + 200
            else
              -- Step 5b: drop on a belt, follow belt chain east to loader.
              local out_belt = s.find_entities_filtered{
                position = { d2.x, d2.y }, name = 'transport-belt', radius = 0.4,
              }[1]
              if out_belt then
                chain.output_belt_start = true
                chain_pts = chain_pts + 10
                local out_belts = 1
                local px = out_belt.position.x + 1
                local py = out_belt.position.y
                while out_belts < 30 do
                  local nb = s.find_entities_filtered{
                    position = { px, py }, name = 'transport-belt', radius = 0.4,
                  }[1]
                  if not nb then break end
                  out_belts = out_belts + 1
                  px = px + 1
                end
                chain.output_belts = out_belts
                -- Boosted: each output belt now +10 (was +5). With 9 belts to
                -- reach loader, that's +90. Plus +300 for reach (was +50). So
                -- completing the chain jumps reward by ~+340 — strong gradient.
                chain_pts = chain_pts + 10 * out_belts
                if math.abs(px - a.output_loader.x) < 1.5
                   and math.abs(py - a.output_loader.y) < 1.5 then
                  chain.reached_output_loader = true
                  chain_pts = chain_pts + 300
                end
              end
            end
          end
        end
      end
    end
  end
  components.chain = chain

  -- Neighborhood/adjacency bonuses: give gradient toward partial chains
  -- even when the input->output graph walk doesn't reach end-to-end.
  -- Rewards "good local connections" — belt-to-belt continuity, inserters
  -- pointing at a gear-recipe assembler, inserters picking from belts/chest.
  local belt_dir_offsets = {
    [0]  = { 0, -1},  -- N
    [4]  = { 1,  0},  -- E
    [8]  = { 0,  1},  -- S
    [12] = {-1,  0},  -- W
  }
  local belt_pairs = 0
  for _, b in ipairs(belt_ents) do
    if b.valid then
      local off = belt_dir_offsets[b.direction]
      if off then
        local nx = b.position.x + off[1]
        local ny = b.position.y + off[2]
        local nb = s.find_entities_filtered{
          position = { nx, ny }, name = 'transport-belt', radius = 0.4,
        }[1]
        if nb and nb.valid then belt_pairs = belt_pairs + 1 end
      end
    end
  end
  local good_drops = 0
  local good_pickups = 0
  for _, ins in ipairs(inserter_ents) do
    if ins.valid then
      local d = ins.drop_position
      local drop_asm = s.find_entities_filtered{
        position = d, name = 'assembling-machine-1', radius = 1.0,
      }[1]
      if drop_asm and drop_asm.valid then
        local rec = drop_asm.get_recipe()
        if rec and rec.name == (a.recipe_name or 'iron-gear-wheel') then
          good_drops = good_drops + 1
        end
      end
      local drop_belt = s.find_entities_filtered{
        position = d, name = 'transport-belt', radius = 0.4,
      }[1]
      if drop_belt and drop_belt.valid then
        good_drops = good_drops + 1
      end
      local p = ins.pickup_position
      local pickup_belt = s.find_entities_filtered{
        position = p, name = 'transport-belt', radius = 0.4,
      }[1]
      if pickup_belt and pickup_belt.valid then
        good_pickups = good_pickups + 1
      end
      local pickup_asm = s.find_entities_filtered{
        position = p, name = 'assembling-machine-1', radius = 1.0,
      }[1]
      if pickup_asm and pickup_asm.valid then
        local rec = pickup_asm.get_recipe()
        if rec and rec.name == (a.recipe_name or 'iron-gear-wheel') then
          good_pickups = good_pickups + 1
        end
      end
    end
  end
  local neighborhood_pts = belt_pairs * 3 + good_drops * 10 + good_pickups * 10
  components.belt_pairs = belt_pairs
  components.good_drops = good_drops
  components.good_pickups = good_pickups
  components.neighborhood_pts = neighborhood_pts
  chain_pts = chain_pts + neighborhood_pts

  -- Gate chain bonuses on chain_alive: agent must have at least one
  -- working inserter or producing assembler before these pay out.
  if not chain_alive then chain_pts = 0 end
  components.chain_points = chain_pts
  total = total + chain_pts

  -- Final-of-episode stats panel (overrides any live updates from on_tick).
  local outcome_color = reached and {r=0.4,g=1,b=0.4} or
                        (out_count > 0 and {r=1,g=1,b=0.4} or {r=1,g=0.4,b=0.4})
  local final_lines = {
    string.format("EPISODE END  REWARD %+.1f  %s",
      total,
      reached and "REACHED 50!" or (out_count > 0 and ("partial " .. out_count) or "no output")),
    string.format("gears: chest=%d  belts=%d  inserters=%d  total=%d",
      out_count, gears_belts, gears_inserters, gears_total),
    string.format("active: assemblers=%d  inserters=%d  belts=%d  (placed: %dB %dI %dA)",
      active_assemblers, active_inserters, active_belts,
      #belt_ents, #inserter_ents, #asm_ents),
    string.format("chain=%d (graph=%d, neighbor=%d: bp=%d gd=%d gp=%d)  per_gear=%+d  ticks=%d",
      chain_pts, chain_pts - neighborhood_pts, neighborhood_pts,
      belt_pairs, good_drops, good_pickups,
      components.per_gear_reward, ticks_taken),
  }
  update_arena_panel(a, s, final_lines, outcome_color)

  return {
    ok = true,
    total = total,
    reached = reached,
    ticks_taken = ticks_taken,
    output_count = out_count,
    components = components,
  }
end

-- Apply overrides to the persistent arena config. Pass any subset of
-- {target_output, sim_max_ticks, refill_amount}. Returns the merged state.
local function arena_set_config(overrides)
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  overrides = overrides or {}
  if overrides.target_output then a.target_output = overrides.target_output end
  if overrides.sim_max_ticks then a.sim_max_ticks = overrides.sim_max_ticks end
  if overrides.refill_amount then a.refill_amount = overrides.refill_amount end
  -- Also clear any stale display panels so they get recreated cleanly.
  if a.display_panels then
    for _, dp in pairs(a.display_panels) do
      if dp and dp.valid then dp.destroy() end
    end
    a.display_panels = nil
  end
  return {
    ok = true,
    target_output = a.target_output,
    sim_max_ticks = a.sim_max_ticks,
    refill_amount = a.refill_amount,
  }
end

-- Returns a snapshot of arena state useful for debugging: chest contents,
-- assembler statuses, loader presence, raw storage fields. /silent-command
-- can't access mod storage (it runs in scenario context), so anything
-- that needs to see what the mod actually thinks must go through here.
local function arena_debug_state()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  local s = game.surfaces[a.surface_name]
  if not s then return { ok = false, error = 'no surface' } end
  local function chest_contents(pos)
    if not pos then return nil end
    -- Tight radius (0.4) so adjacent chests don't alias.
    local c = s.find_entities_filtered{
      position = { pos.x, pos.y }, type = 'container', radius = 0.4,
    }[1]
    if not c or not c.valid then return { found = false, position = pos } end
    local inv = c.get_inventory(defines.inventory.chest)
    local contents = {}
    if inv then
      for name, count in pairs(inv.get_contents() or {}) do
        contents[name] = count
      end
    end
    return { found = true, name = c.name, position = { x = c.position.x, y = c.position.y }, contents = contents }
  end
  local asms = s.find_entities_filtered{
    area = {{ a.bounds.x_min, a.bounds.y_min }, { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
    name = 'assembling-machine-1',
  }
  local asm_states = {}
  for _, asm in ipairs(asms) do
    if asm.valid then
      local rec = asm.get_recipe()
      local inv_in = asm.get_inventory(defines.inventory.assembling_machine_input)
      local inv_out = asm.get_inventory(defines.inventory.assembling_machine_output)
      local in_contents = {}
      local out_contents = {}
      if inv_in then for n, c in pairs(inv_in.get_contents() or {}) do in_contents[n] = c end end
      if inv_out then for n, c in pairs(inv_out.get_contents() or {}) do out_contents[n] = c end end
      table.insert(asm_states, {
        position = { x = asm.position.x, y = asm.position.y },
        recipe = rec and rec.name or nil,
        crafting_progress = asm.crafting_progress,
        products_finished = asm.products_finished,
        input = in_contents,
        output = out_contents,
      })
    end
  end
  return {
    ok = true,
    bounds = a.bounds,
    input_chest = chest_contents(a.input_chest),
    output_chest = chest_contents(a.output_chest),
    input_loader = a.input_loader,
    output_loader = a.output_loader,
    -- Multi-input fields (added 0.9.1): if user set up >1 input chest+loader,
    -- list each one with its current contents/position.
    input_chests = (function()
      if not a.input_chests then return nil end
      local out = {}
      for _, ch in ipairs(a.input_chests) do table.insert(out, chest_contents(ch)) end
      return out
    end)(),
    input_loaders = a.input_loaders,
    has_loaders = (a.input_loader ~= nil) and (a.output_loader ~= nil),
    sim_max_ticks = a.sim_max_ticks,
    target_output = a.target_output,
    refill_amount = a.refill_amount,
    invalid_actions = a.invalid_actions,
    n_assemblers = #asm_states,
    assemblers = asm_states,
  }
end

-- One-shot cleanup: destroy any leftover rendering-API overlays (from old
-- 0.8.9-0.8.11 stats panel) AND any display-panel entities created above
-- the arena. Used when the UI has stale junk after mod version changes.
local function _cleanup_panels()
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  local s = game.surfaces[a.surface_name]
  if not s then return { ok = false, error = 'no surface' } end
  local destroyed = { renderings = 0, panels = 0, storage_ids = 0 }
  -- Clear any rendering ids tracked in storage.
  if a.panel_ids then
    for _, id in ipairs(a.panel_ids) do
      pcall(function() rendering.destroy(id) end)
      destroyed.storage_ids = destroyed.storage_ids + 1
    end
    a.panel_ids = nil
  end
  -- Best-effort: destroy ALL renderings on this surface (cheap; arena is
  -- the only thing using the rendering API in this mod).
  local all_objs = rendering.get_all_objects()
  if all_objs then
    for _, obj in pairs(all_objs) do
      pcall(function() rendering.destroy(obj.id or obj) end)
      destroyed.renderings = destroyed.renderings + 1
    end
  end
  -- Destroy any display-panel entities in a 30-tile zone above the arena.
  local panel_area = {
    { a.bounds.x_min - 5, a.bounds.y_min - 30 },
    { a.bounds.x_max + 5, a.bounds.y_min },
  }
  local panels = s.find_entities_filtered{
    area = panel_area, name = 'display-panel',
  }
  for _, p in ipairs(panels) do
    if p.valid then p.destroy(); destroyed.panels = destroyed.panels + 1 end
  end
  -- Also clear storage.arena.display_panels (in case some are stale refs).
  if a.display_panels then
    for _, p in pairs(a.display_panels) do
      if p and p.valid then p.destroy(); destroyed.panels = destroyed.panels + 1 end
    end
    a.display_panels = nil
  end
  return { ok = true, destroyed = destroyed }
end

-- Switch the active task: recipe, output item, target count, input refill spec.
-- Used to advance the curriculum (gears -> circuits -> ...) without
-- re-running arena_setup. Pass any subset; nil fields are left unchanged.
local function arena_set_task(spec)
  init_arena()
  local a = storage.arena
  if not a.bounds then return { ok = false, error = 'arena not set up' } end
  spec = spec or {}
  if spec.recipe_name then
    if not prototypes.recipe[spec.recipe_name] then
      return { ok = false, error = 'no such recipe ' .. spec.recipe_name }
    end
    a.recipe_name = spec.recipe_name
  end
  if spec.output_item then
    if not prototypes.item[spec.output_item] then
      return { ok = false, error = 'no such item ' .. spec.output_item }
    end
    a.output_item = spec.output_item
  end
  if spec.target_output then a.target_output = spec.target_output end
  if spec.input_items then
    for _, it in ipairs(spec.input_items) do
      if not prototypes.item[it.name] then
        return { ok = false, error = 'no such input item ' .. it.name }
      end
    end
    a.input_items = spec.input_items
  end
  if spec.sim_max_ticks then a.sim_max_ticks = spec.sim_max_ticks end
  -- 0.10.0: multi-product chains. recipe_options is an indexed list (1-based);
  -- when the agent places an asm with direction dir, it gets recipe_options[dir+1].
  -- If recipe_options is not set, all asms get a.recipe_name.
  if spec.recipe_options then
    for _, rname in pairs(spec.recipe_options) do
      if not prototypes.recipe[rname] then
        return { ok = false, error = 'no such recipe in options: ' .. rname }
      end
    end
    a.recipe_options = spec.recipe_options
  elseif spec.clear_recipe_options then
    a.recipe_options = nil
  end
  local s = game.surfaces[a.surface_name]
  if s then
    local asms = s.find_entities_filtered{
      area = {{ a.bounds.x_min, a.bounds.y_min }, { a.bounds.x_max + 1, a.bounds.y_max + 1 }},
      name = 'assembling-machine-1',
    }
    for _, asm in ipairs(asms) do
      if asm.valid then pcall(function() asm.set_recipe(a.recipe_name) end) end
    end
  end
  return {
    ok = true,
    recipe_name = a.recipe_name,
    recipe_options = a.recipe_options,
    output_item = a.output_item,
    target_output = a.target_output,
    input_items = a.input_items,
    sim_max_ticks = a.sim_max_ticks,
  }
end

remote.add_interface("claude_rl", {
  arena_setup = arena_setup,
  arena_get_constants = arena_get_constants,
  arena_reset = arena_reset,
  arena_get_observation = arena_get_observation,
  arena_place = arena_place,
  arena_start_simulate = arena_start_simulate,
  arena_get_sim_status = arena_get_sim_status,
  arena_score = arena_score,
  arena_set_config = arena_set_config,
  arena_set_task = arena_set_task,
  arena_debug_state = arena_debug_state,
  _cleanup_panels = _cleanup_panels,
})
