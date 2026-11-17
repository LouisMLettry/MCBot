# MinecraftBot

Drive your Minecraft character from Python, with images of the game, with a view to plugging in ML later.

- `mod/`: **Fabric mod for Minecraft 1.21.1** (client side). It opens a local TCP server (`127.0.0.1:5555`) that receives actions (move forward, turn, jump…) and sends back the player's state and, on request, an image of the game.
- `python/`: Python client (`mcbot`) and, in `python/scripts/`, the demo scripts: `demo_movements.py`
  (movement), `build_house.py` (building), `scan_blocks.py` (reading the blocks around the player) and
  `scan_entities.py` (listing the mobs and items around the player).
- `doc/`: system documentation (architecture, journal, roadmap).
- `guidelines.md`: conventions and decisions that apply to the whole project (units, block names, protocol…).

## 1. Requirements

- **JDK 25** to build the mod (the Fabric Gradle plugin "Loom" requires it; the mod itself targets Java 21, like Minecraft 1.21.1):
  ```powershell
  winget install EclipseAdoptium.Temurin.25.JDK
  ```
  Then reopen the terminal (`java -version` must show 25 or higher; JDK 26 works too).
- **Python 3.10+** and **[uv](https://docs.astral.sh/uv/)** to manage the Python environment
  (dependencies are declared in `python/pyproject.toml`):
  ```powershell
  winget install astral-sh.uv
  ```

## 2. Putting the mod into Minecraft

### Option A — development mode (the simplest)
Starts a Minecraft that already has the mod, without going through the launcher (offline account "Player…"):
```powershell
cd mod
.\gradlew.bat runClient
```
(`./gradlew runClient` on macOS / Linux.) The first launch downloads Minecraft and the dependencies (a few minutes). In the logs, you should see:
```
[McBot-Server/INFO] (mcbot) McBot listening on 127.0.0.1:5555
```

### Option B — in your usual Minecraft (official launcher)
1. Build the mod:
   ```powershell
   cd mod
   .\gradlew.bat build
   ```
   (`./gradlew build` on macOS / Linux.)
   → the mod file is `mod\build\libs\mcbot-0.2.1.jar` (not the `-sources` one).
   When updating, remove the old `mcbot-*.jar` from the `mods` folder before copying the new one.
2. Install **Fabric Loader** for 1.21.1 with the official installer: <https://fabricmc.net/use/installer/> (*Client* tab, version 1.21.1).
   Be careful not to pick **1.21.11**: the mod requires exactly 1.21.1 and Fabric refuses to load it otherwise.
3. Download **Fabric API** for 1.21.1: <https://modrinth.com/mod/fabric-api> (version `…+1.21.1`).
4. Copy `mcbot-0.2.1.jar` **and** the Fabric API jar into `%APPDATA%\.minecraft\mods` (Windows) or
   `~/Library/Application Support/minecraft/mods` (macOS); create the folder if it doesn't exist.
5. In the launcher, pick the **fabric-loader-1.21.1** profile and play.

Tip (macOS / Linux): instead of copying the jar after every build, put a symbolic link to the built jar in `mods`;
then restarting Minecraft after a `./gradlew build` is enough:
```bash
ln -s "$PWD/build/libs/mcbot-0.2.1.jar" ~/Library/Application\ Support/minecraft/mods/mcbot-0.2.1.jar   # from mod/
```
Link the jar, not the whole `build/libs` folder (Fabric would also load the `-sources` jar). The link has to be
recreated if the mod version changes, since it is part of the file name.

## 3. Moving the character from Python

1. In Minecraft, create/enter a **singleplayer world** (ideally *Superflat*, to have room).
2. In another terminal:
   ```powershell
   cd python
   uv sync
   uv run python scripts/demo_movements.py
   ```
   `uv sync` creates the `.venv` environment and installs the dependencies (run it again after `pyproject.toml`
   changes); `uv run` runs the command in that environment.
   The character moves forward, turns, jumps, looks up and down, walks in a circle, sprints…
   Screenshots are saved in `python/frames/`.

You can click on the terminal: the mod disables automatic pausing while a script is connected (and closes the Pause menu if it is open).

### Using the client in your own code
```python
from mcbot import MinecraftClient

with MinecraftClient() as mc:            # 127.0.0.1:5555
    mc.config(width=160, height=90)       # size of the returned images
    image, info = mc.forward(20, frame=True)   # move forward 20 ticks (1 s); image: np.ndarray (90, 160, 3) uint8
    print(info["pos"], info["yaw"])
    mc.turn(90)                           # turn 90° right in 10 ticks (0.5 s)
    mc.step(ticks=20, forward=True, jump=True, yaw=-45)   # free action for 1 s
    mc.stop()                             # release all keys
```
Keys available for `step`: `forward, back, left, right, jump, sprint, sneak, attack, use`, plus `yaw` (degrees, > 0 = right) and `pitch` (degrees, > 0 = down). All durations are in ticks: 20 ticks = 1 second
(`TICKS_PER_SECOND`, see [guidelines.md](guidelines.md)).
**Keys stay pressed until the next command** (useful to chain steps smoothly); `stop()` or disconnecting releases them.

The image is the last frame the game drew, part-way between two ticks: the player's state in `info` can be up to one
tick ahead of it. With `ticks=0`, the image comes from before the step and doesn't show its rotation. Details in
[doc/python-api.md](doc/python-api.md#moving-and-looking).

## 4. Automatic building

The mod can also:
1. switch to **build mode** (creative) — in a singleplayer world, even without cheats;
2. **fly** (while flying: `jump` = up, `sneak` = down);
3. **choose the block** in hand (any block in the game in build mode);
4. **place** a block at precise coordinates (within reach: 5 blocks in creative), and **break** one.

### Example: a small house
Stand **on the ground** in a singleplayer world (Superflat is ideal), facing a free area, then:
```powershell
cd python
uv run python scripts/build_house.py
```
The character switches to creative, takes off, lays the floor, goes around the walls (windows, door, torch), builds a
pyramid roof, then backs away to take a picture of the house (`python/frames/house.png`). About 200 blocks, ~1 minute.
Option `--delay N`: ticks to wait after each block (default 2; 0 = fastest).

### In your own code
```python
from mcbot import Builder, MinecraftClient, Phase, Placement

with MinecraftClient() as mc:
    mc.set_build_mode(True)              # creative; set_build_mode(False) = survival
    mc.set_flying(True)
    mc.fly_to(10.5, -57, 3.5)            # fly to this position (feet), then stop
    mc.select_block("oak_planks", slot=0)
    info = mc.place_block(10, -60, 6)    # info["placed"]: True / False (+ info["reason"])
    mc.place_block(11, -59, 6, face="north")   # clicked face: orients logs, slabs, stairs
    mc.place_block(11, -59, 6, replace=True)   # breaks the block already there, then places
    mc.break_block(10, -60, 6)

    # Or let the Builder fly within reach and switch blocks on its own:
    Builder(mc).build([
        Phase("Low wall", standpoint=(0.5, -58, 0.5),
              blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
        Phase("Opening", standpoint=(0.5, -58, 0.5),
              blocks=[Placement((0, -60, 3), "air")]),   # "air" = empty the cell
    ])
```
- `place_block` doesn't need a neighbouring block: you can build in mid-air. Possible failure reasons:
  `already_there` (the cell already holds this block), `occupied` (it holds another block; `block` says which),
  `out_of_reach`, `no_block_selected`, `player_in_the_way`, `rejected`.
- With `replace=True`, a cell holding another block is emptied first (creative only); `replaced` names the block
  that was broken.
- The `Builder` leaves cells holding another block as they are and lists them in `builder.occupied`, unless
  `Builder(mc, replace=True)`. A `Placement` with the block `"air"` empties the cell.
- Block identifiers are Minecraft's, without the `minecraft:` prefix (`stone`, `oak_log`, `glass_pane`,
  `red_wool`…); the prefix is accepted but never appears in responses (see [guidelines.md](guidelines.md)).
- The player looks at each block it places (can be disabled with `look=False`).

### Writing exact block states
`place_block` places the block in hand like a player would, so orientation depends on where the player looks.
To write an exact block state instead, at any distance and without flying:
```python
mc.set_block(12, -60, 4, "oak_stairs[facing=east,half=top]")
mc.set_blocks([((x, -60, 8), "oak_log[axis=x]") for x in range(5)])   # many blocks, sent in batches
```
This works in a singleplayer world, without cheats, in any game mode. Blocks are written exactly as given:
neighbouring blocks are not updated (a torch written before its wall stays in place, a fence doesn't connect to a
new neighbour on its own). Unspecified properties take their default value.

## 5. Reading the world's blocks

The mod reads blocks as the game knows them: only **loaded chunks** (within render distance) are
available. No cheats needed.

### Example: map of the surroundings
In a world, then:
```powershell
cd python
uv run python scripts/scan_blocks.py --radius 8
```
Shows a top-down map around the player (the highest block of each column) and the number of blocks of
each kind.

### In your own code
```python
from mcbot import MinecraftClient

with MinecraftClient() as mc:
    vol = mc.get_blocks_around(radius=8)       # 17 × 17 × 17 cube centred on the player's feet
    vol = mc.get_chunk()                       # the player's chunk (or get_chunk(cx, cz))
    vol = mc.get_blocks((0, -64, 0), (31, -50, 31))   # box between two corners (included)

    vol.ids            # np.ndarray uint16, indexed [x, y, z] from vol.origin
    vol.palette        # ["air", "stone", ...]: vol.ids contains indices into this list
    vol.origin         # world coordinates of vol.ids[0, 0, 0]
    vol.block_at(10, -60, 3)    # "grass_block" (world coordinates)
    vol.mask("water")           # boolean array: where there is water
```
- `states=True` (on all three methods) gives the full block state in the palette, for example
  `oak_log[axis=x]` or `oak_door[facing=north,half=lower,open=false,...]`.
- The box is limited to the world's height and to 1,048,576 blocks (3 × 3 full chunks) per request.
- Possible errors: chunk not loaded, box too large, box outside the world's height.

### Entities (mobs, dropped items, players)
```powershell
cd python
uv run python scripts/scan_entities.py --radius 32
```
Takes a picture (`frames/entities.png`) and lists the entities around the player, saying for each one whether it is
in the picture's field of view and in line of sight.

```python
with MinecraftClient() as mc:
    mobs = mc.get_entities(radius=32, types=["zombie", "skeleton"], visibility=True)
    for e in mobs:                     # nearest first
        print(e.type, e.pos, e.distance, e.health, e.in_view, e.line_of_sight)

    # Entities as the returned image shows them (same tick, same camera)
    image, info = mc.step(ticks=5, frame=True, forward=True, entities={"radius": 32, "visibility": True})
    info["entities"]                   # list of Entity
```
- Only the entities the server sends to the game are known: up to about 8 chunks away for mobs, never beyond the
  render distance.
- `in_view`: the hitbox is in the camera's field of view. `line_of_sight`: nothing but see-through blocks (glass…)
  between the camera and the entity. Both are needed for the entity to show in the image (unless it is
  `invisible`).

## 6. Protocol (for reference)
Big-endian integers, one request → one response:
- request: `uint32 length` + UTF-8 JSON;
- response: `uint32 length` + JSON, then `uint32 length` + binary data (length 0 if there is none).
  The JSON field `payload` says what it contains:
  - `frame`: raw RGB pixels (`height × width × 3`, row by row from the top);
  - `blocks`: one `uint16` per block (index into `palette`), ordered by x, then y, then z.

| `type` | Fields | Effect |
|---|---|---|
| `ping` | — | Returns the state. |
| `config` | `width`, `height`, `hide_gui` (optional) | Image size (16–1024 px); hide the interface like F1. |
| `step` | `ticks`, `frame`, `action` {boolean keys, `yaw`, `pitch`}, `entities` (optional, the options of `entities`) | Applies the action for `ticks` ticks, then responds. With `entities`: `entities` as for the `entities` command, as the frame shows them. |
| `game_mode` | `mode` (`survival`, `creative`, `adventure`, `spectator`) | Changes the game mode (singleplayer world); responds once applied. |
| `fly` | `enabled` | Starts/stops flying (creative). Flying is turned back on automatically if it stops in mid-air. |
| `select_block` | `block`, `slot` (0–8, optional) | Puts the block in hand (created in creative, looked up in the hotbar otherwise). |
| `place_block` | `x`, `y`, `z`, `face` (default `up`), `look` (default `true`), `replace` (default `false`) | Places the held block → `placed`, `reason`, `message`, `block`, `replaced`. |
| `break_block` | `x`, `y`, `z`, `look` | Breaks the block (creative) → `broken`, `reason`, `block`. |
| `set_blocks` | `blocks`: [[x, y, z, "state"], …] | Writes exact block states (singleplayer); answers once the client shows them → `blocks` (full states written). |
| `blocks` | `min` and `max` [x, y, z], **or** `chunk` [cx, cz], **or** `radius`; `states` (default `false`) | Blocks of the box → `origin` [x, y, z], `shape` [sx, sy, sz], `palette`, and the indices in binary. |
| `entities` | `radius` (default 32, max 256) **or** `min` and `max` [x, y, z]; `types` (list, default all); `limit` (default 256, max 4096); `visibility` (default `false`) | Entities around the player, nearest first → `entities`: [{`id`, `type`, `category`, `pos`, `motion`, `yaw`, `pitch`, `size` [w, h], `distance`, `invisible`, `name`, `health`, `max_health`, `baby`, `item`, `count`, `line_of_sight`, `in_view`}, …] (fields that don't apply are left out). |

Response: `ok`, `error`, `tick`, `paused`, `screen`, `in_world`, `pos` [x, y, z], `motion` [vx, vy, vz] (blocks/tick), `yaw`, `pitch`, `on_ground`, `health`, `flying`, `may_fly`, `game_mode`, `reach`, `selected_slot`, `held_item`, `frame_width`, `frame_height`.

The port can be changed by launching the game with `-Dmcbot.port=XXXX`.

## Tests
```powershell
cd python
uv run pytest tests
```
They check the Python client against a fake server (including a simulation of flight physics for `fly_to` and block decoding) and the house plan (everything is within reach, the player is never in the way), without launching Minecraft.
