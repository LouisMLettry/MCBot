# Python API

Reference for the `mcbot` package (`python/mcbot/`). Everything below can be imported directly:

```python
from mcbot import (MinecraftClient, connect_with_retry, McBotError, TICKS_PER_SECOND,
                   Builder, Phase, Placement, BlockVolume)
```

| Class | File | Purpose |
|---|---|---|
| [`MinecraftClient`](#minecraftclient) | `client.py` | Connects to the mod and sends every command: move, look, build, read the world. |
| [`Builder`, `Phase`, `Placement`](#builder) | `builder.py` | Builds a list of blocks automatically, flying from spot to spot. |
| [`BlockVolume`](#blockvolume) | `world.py` | Blocks of a box of the world, as returned by `get_blocks` and friends. |

## Conventions

These follow the project-wide rules in [guidelines.md](../guidelines.md).

- **Time:** every duration in the game is in **ticks** (20 ticks = 1 second, `TICKS_PER_SECOND`). Only waits
  outside the game (connection retries, waiting for a world, network timeout) are in seconds.
- **Coordinates:** world coordinates, `y` is up. A position (`info["pos"]`) is the player's **feet**. A block
  `(x, y, z)` is the cube from `(x, y, z)` to `(x+1, y+1, z+1)`; methods that take a block accept floats and round
  them down.
- **Angles:** `yaw` > 0 turns right, `pitch` > 0 looks down (−90 = straight up, 90 = straight down).
- **Block names:** Minecraft identifiers **without** the `minecraft:` prefix (`"stone"`, `"oak_log"`). Everything
  returned uses this form; inputs also accept the prefix. Assumes Minecraft without other mods.
- **Errors:**
  - `McBotError`: the mod refused the command (no world loaded, unknown block, chunk not loaded…).
  - `ValueError`: invalid argument detected in Python before sending (unknown key, unknown face…).
  - `ConnectionError`: Minecraft closed the connection.

---

## MinecraftClient

```python
MinecraftClient(host="127.0.0.1", port=5555, timeout=130.0)
```

Talks to the mod over TCP. One request at a time, each answered with the player's state.

### Connecting

| Method | Description |
|---|---|
| `connect()` | Opens the connection. Returns the client itself. |
| `close()` | Closes the connection. The mod then releases all keys. |
| `with MinecraftClient() as mc:` | Connects (unless already connected), and closes at the end of the block. |
| `connect_with_retry(host, port, retry_seconds=3.0, log=print)` | *Function.* Keeps retrying until Minecraft is reachable, then returns a connected client. |
| `wait_for_world(poll_seconds=3.0, log=print)` | Waits until the player is in a world (so a script can be started from the main menu). Returns `info`. |
| `ping()` | Returns `info` without doing anything. |

### The `info` dictionary

Every command returns the player's state, read at the tick the command finished:

| Key | Meaning |
|---|---|
| `pos`, `motion` | Feet position `[x, y, z]`; velocity in blocks per tick. |
| `yaw`, `pitch` | Where the player looks, in degrees. |
| `on_ground`, `flying`, `may_fly` | Movement state. |
| `health`, `game_mode`, `reach` | Health points, `"survival"`/`"creative"`/…, how far blocks can be reached. |
| `selected_slot`, `held_item` | Hotbar slot (0–8) and item in hand, e.g. `"stone"`. |
| `in_world`, `paused`, `screen` | Whether a world is loaded, the game is paused, and which menu is open (`None` if none). |
| `tick` | Counter of game ticks since the game started, handy to measure time. |
| `frame_width`, `frame_height` | Size of the images returned. |

Commands add their own keys (for example `placed` for `place_block`).

### Moving and looking

```python
step(ticks=1, frame=False, yaw=0.0, pitch=0.0, **keys) -> (image, info)
```

Holds `keys` for `ticks` ticks (max 1200 = 1 minute) while turning the camera by `yaw` / `pitch` degrees, spread
evenly over the ticks. With `ticks=0` the rotation is instant.

- **Keys:** `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`, `attack`, `use` (all `False` by default).
- **Keys stay pressed after the step**, until the next command changes them. This makes consecutive steps smooth.
  Call `stop()` to release everything; closing the connection does too.
- **`image`:** with `frame=True`, a numpy array `(frame_height, frame_width, 3)` of `uint8` RGB, top row first,
  captured at the end of the step. Otherwise `None`.

Shortcuts, all returning `(image, info)` and accepting `frame=True`:

| Method | Does |
|---|---|
| `stop()` | Releases all keys (one tick). |
| `forward(ticks, sprint=False, jump=False)` | Walks forward for `ticks` ticks. |
| `turn(degrees, ticks=10)` | Turns on the spot, right if positive. |
| `look(pitch, ticks=10)` | Looks down (positive) or up (negative). |
| `jump()` | Jumps (holds jump for 10 ticks). |

```python
config(width, height, hide_gui=None) -> info
```

Sets the size of returned images (16 to 1024 pixels per side; the game window is shrunk by averaging pixels).
`hide_gui=True` hides the interface like F1, for clean pictures.

```python
with MinecraftClient() as mc:
    mc.config(width=160, height=90)
    image, info = mc.forward(20, frame=True)   # 1 second; image.shape == (90, 160, 3)
    mc.step(ticks=20, forward=True, jump=True, yaw=-45)
    mc.stop()
```

### Building

Changing the game mode works in singleplayer, without cheats. Building is easiest in creative ("build mode"):
unlimited blocks, flying, instant breaking.

| Method | Description |
|---|---|
| `set_game_mode(mode)` | `"survival"`, `"creative"`, `"adventure"` or `"spectator"`. Returns once applied (5 s max, else `McBotError`). |
| `set_build_mode(enabled=True)` | Shortcut: creative if `True`, survival if `False`. |
| `set_flying(enabled=True)` | Starts / stops flying (creative only). When flying, `jump` goes up and `sneak` goes down. Started on the ground, the player hops up about one block. While enabled by the script, the mod turns flying back on if the game turns it off. |
| `select_block(block, slot=None)` | Puts a block in hand. In creative, the block is created in hotbar `slot` (0–8, default: current slot). In survival, it must already be in the hotbar. Returns `info` with `slot`, `item`, `is_block`. |
| `place_block(x, y, z, face="up", look=True, replace=False)` | Places the held block in cell `(x, y, z)`. See below. |
| `break_block(x, y, z, look=True)` | Breaks the block instantly (creative only). Returns `info` with `broken` (bool), `block`, and on failure `reason` (`empty`, `out_of_reach`, `rejected`) and `message`. |
| `fly_to(x, y, z, tolerance=0.75, vertical_tolerance=0.35, max_steps=600, face_target=True)` | Flies until the feet are at `(x, y, z)`, then stops and releases the keys. See below. |
| `set_block(x, y, z, block)` | Writes an exact block state, e.g. `"oak_stairs[facing=east,half=top]"`. See below. Returns `info` with `block`: the full state now in the cell. |
| `set_blocks(blocks)` | Same for many blocks, given as `((x, y, z), state)` pairs, written in order. Sent in batches of `SET_BLOCKS_BATCH` (4096). Returns `info` with `blocks`: the full state written for each entry. |

**`place_block`:**
- No neighbouring block is needed: you can build in mid-air.
- The cell must be empty or replaceable (grass, water…) and within reach (about 5 blocks in creative, measured from
  the eyes).
- `face` is the side being "clicked". It orients some blocks: `"up"` gives a vertical log or a bottom slab,
  `"down"` a top slab, `"north"`/`"south"`/`"east"`/`"west"` a lying log.
- With `look=True` the player first looks at the cell, which also orients doors, stairs and torches.
- **If the cell already holds a block** (other than a replaceable one):
  - the same block as the one held → nothing happens, `reason` is `already_there`. Only the block type is
    compared, not its state: a log lying the wrong way counts as already there;
  - another block → `reason` is `occupied`, unless `replace=True`: then that block is broken first (creative only)
    and `replaced` gives its name.
- Returns `info` with `placed` (bool), `target`, `block` (the block now in the cell, or the one found there for
  `already_there` / `occupied`), `replaced` when a block was broken, and on failure `reason` and `message`.
  Possible reasons: `already_there`, `occupied`, `out_of_reach`, `no_block_selected`, `player_in_the_way`,
  `rejected`.

**`set_block` / `set_blocks`:** unlike `place_block`, which acts like a player placing the block in hand, these
write a block state directly, like the `/setblock` command:
- singleplayer world only, but no cheats needed, any game mode, any distance (within the world's height);
- blocks are written **exactly as given**: neighbouring blocks are not updated, so a torch written before its wall
  stays in place, and a fence doesn't connect to a new neighbour on its own; give connections in the state if
  needed (`oak_fence[east=true]`);
- properties left out take their default value (`"oak_stairs"` → `oak_stairs[facing=north,half=bottom,...]`);
- every state of a batch is checked first: one invalid state (`McBotError`) means nothing of that batch is written;
- the call returns once the game client shows the new blocks, so `get_blocks` right after sees them.

**`fly_to`:** enables flying if needed (so creative is required). At each step it predicts where the player would
stop if all keys were released (flight keeps momentum) and presses the keys that bring that point onto the target;
with `face_target` it also turns towards the target. Raises `McBotError` if the target isn't reached within
`max_steps` steps. Returns the final `info`.

```python
mc.set_build_mode(True)
mc.fly_to(10.5, -57, 3.5)
mc.select_block("oak_planks", slot=0)
info = mc.place_block(10, -60, 6)
if not info["placed"]:
    print(info["reason"], info["message"])
```

### Reading the world

All three methods return a [`BlockVolume`](#blockvolume). Only **loaded** chunks (within render distance) can be
read; a request covers at most 1,048,576 blocks (3 × 3 full chunks) and is cut to the world's height limits.

| Method | Box |
|---|---|
| `get_blocks(corner1, corner2, states=False)` | Between two opposite corners `(x, y, z)`, both included, in any order. |
| `get_chunk(cx=None, cz=None, states=False)` | A whole chunk, 16 × world height × 16. `cx, cz` are chunk coordinates (`block // 16`); default: the player's chunk. |
| `get_blocks_around(radius=8, states=False)` | A cube of side `2 × radius + 1` centred on the block of the player's feet, at the same tick as the request. |

With `states=True`, the palette contains full block states such as `"oak_log[axis=x]"` instead of `"oak_log"`.

Raises `McBotError` if a chunk isn't loaded, the box is too big, or it lies entirely above or below the world.

---

## Builder

```python
Builder(mc, delay_ticks=2, replace=False, log=print)
```

Builds a structure described as a list of **phases**. For each phase the builder flies to the phase's standpoint,
then places its blocks one by one, switching the block in hand when needed.

```python
Placement(pos, block, face="up")          # one block: (x, y, z), block name, clicked face
Placement(pos, "air")                     # empty this cell (the builder breaks whatever is there)
Phase(name, standpoint, blocks=[...])     # blocks all reachable from standpoint (a feet position)
```

A plan describes the **result** you want. For each cell, the builder compares it with what is there:

| The cell holds… | Planned block | Planned `"air"` |
|---|---|---|
| nothing (or grass, water…) | placed → `placed` | nothing to do → `already_there` |
| the planned block | nothing to do → `already_there` | broken → `removed` |
| another block | left as it is → `occupied`; with `replace=True`: broken, then placed → `placed` and `replaced` | broken → `removed` |

- **Before building:** switch to creative (`mc.set_build_mode(True)`). The builder flies with `fly_to`, which
  needs creative.
- **Choosing standpoints:** every block of a phase must be within reach (about 5 blocks from the eyes, which are
  1.62 above the feet), and the player must not stand in a cell that will be filled. `tests/test_house.py` shows
  how to check both automatically.
- **Order matters:** blocks are placed in list order. Put supporting blocks first for those that need support
  (torches, doors).

| Member | Description |
|---|---|
| `build(phases)` | Builds all phases in order. |
| `place(placement)` | Places one block, or empties the cell for `"air"` (from where the player is now). Returns `True` if the cell changed. |
| `select(block)` | Puts a block in hand, unless it is already held. Each new block name gets the next hotbar slot (cycling over the 9 slots). |
| `delay_ticks` | Ticks waited after each block (0 = as fast as possible). |
| `replace` | Whether cells holding another block are broken and refilled. |
| `placed` | Number of blocks placed. |
| `replaced` | Among them, how many replaced another block. |
| `removed` | Number of blocks broken for `"air"` placements. |
| `already_there` | Cells that were already as planned. |
| `occupied` | List of `(placement, block found)` for cells left holding another block (only without `replace`). |
| `failures` | List of `(placement, message)` for the cells that couldn't be changed (out of reach, refused…). |
| `summary()` | Text such as `"198 blocks placed (3 replacing another block), 4 removed, 2 cells already as planned"`. |

```python
mc.set_build_mode(True)
builder = Builder(mc, delay_ticks=0)
builder.build([
    Phase("Wall", standpoint=(0.5, -58, 0.5),
          blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
    Phase("Logs", standpoint=(0.5, -58, 6.5),
          blocks=[Placement((x, -60, 8), "oak_log", face="east") for x in range(-2, 3)]),
    Phase("Gap", standpoint=(0.5, -58, 0.5),
          blocks=[Placement((0, -60, 3), "air")]),
])
print(builder.summary())
for placement, found in builder.occupied:
    print(f"{placement.pos}: wanted {placement.block}, found {found}")
```

`scripts/build_house.py` is a complete example (a 7 × 7 house, about 200 blocks in 6 phases).

---

## BlockVolume

```python
BlockVolume(ids, palette, origin)    # frozen dataclass, normally created by MinecraftClient
```

| Attribute / method | Description |
|---|---|
| `ids` | numpy array of `uint16`, shape `(size_x, size_y, size_z)`, indexed **`[x, y, z]`** relative to `origin`. Each value is an index into `palette`. |
| `palette` | List of block names. `palette[ids[i, j, k]]` is the block at `origin + (i, j, k)`. |
| `origin` | World coordinates `(x, y, z)` of `ids[0, 0, 0]`, the lowest corner of the box. |
| `shape` | Same as `ids.shape`. |
| `contains(x, y, z)` | `True` if the world block `(x, y, z)` is inside the box. |
| `block_at(x, y, z)` | Name of the block at world coordinates. Raises `IndexError` outside the box. |
| `mask(block)` | Boolean array, same shape as `ids`: `True` where `block` is. With a `states=True` palette, every state of the block matches (`mask("oak_log")` finds logs of every orientation). |

Notes:
- Empty space can be `air`, `cave_air` (underground) or `void_air`.
- A palette only lists the blocks present in this box, and its order changes from one request to the next: compare
  names, not ids, across requests.
- A full chunk is 98,304 blocks, about 200 KB.

### Examples

```python
import numpy as np

vol = mc.get_blocks_around(radius=8)
x, y, z = (int(np.floor(c)) for c in mc.ping()["pos"])

vol.block_at(x, y - 1, z)                 # block under the feet

# World positions of every log in the box
logs = np.argwhere(vol.mask("oak_log")) + vol.origin

# Nearest water
water = np.argwhere(vol.mask("water")) + vol.origin
if len(water):
    nearest = water[np.argmin(np.linalg.norm(water - (x, y, z), axis=1))]

# How many blocks of each kind
counts = np.bincount(vol.ids.ravel(), minlength=len(vol.palette))
{vol.palette[i]: int(n) for i, n in enumerate(counts) if n}

# A whole chunk, one horizontal slice at y = -60
chunk = mc.get_chunk()
layer = chunk.ids[:, -60 - chunk.origin[1], :]   # shape (16, 16), indexed [x, z]
```

`scripts/scan_blocks.py` is a complete example (top-down map of the area around the player).
