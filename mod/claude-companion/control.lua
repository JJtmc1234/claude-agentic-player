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

local function init_all()
  init_chat_log(); init_mining_jobs(); init_walks(); init_path_requests(); init_craft_jobs(); init_arena()
end

script.on_init(init_all)
script.on_configuration_changed(init_all)


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
        t.destroy{}
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

-- Arena (RL) simulation tick handler. When storage.arena.simulating is
-- true, we count the output chest's gear count every tick. When it hits
-- target_output OR sim_max_ticks elapsed, we stop the simulation and
-- pause the world. Bridge polls arena_get_sim_status to learn this.
local function process_arena_sim()
  local a = storage.arena
  if not a or not a.simulating then return end
  if not a.output_chest or not a.output_chest.unit_number then
    a.simulating = false; return
  end
  local out = game.get_entity_by_unit_number(a.output_chest.unit_number)
  if not out or not out.valid then
    a.simulating = false; a.sim_error = 'output chest gone'; return
  end
  local inv = out.get_inventory(defines.inventory.chest)
  local count = inv and inv.get_item_count(a.output_item) or 0
  local elapsed = game.tick - (a.sim_started_tick or game.tick)
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
    pong = "from claude-companion 0.7.0",
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
})
