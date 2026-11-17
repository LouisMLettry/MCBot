# Journal

What has been done, newest at the bottom. Add an entry for each meaningful change: what, why, and any decision
worth remembering.

## Before October 2026 — initial version (mod 0.2.1)

The project was started by Florian Desmons on Windows.

- Fabric mod for Minecraft 1.21.1 exposing a local TCP server (`127.0.0.1:5555`).
- Movement control: keys held for a number of ticks, camera rotation, frame capture at a chosen size.
- Building: creative mode without cheats, flying, choosing the block in hand, placing / breaking blocks at given
  coordinates.
- Python library `mcbot` with `MinecraftClient`, `fly_to` and `Builder`.
- Two demo scripts: `demo_movements.py` and `build_house.py` (a ~200-block house built in about a minute).
- Python tests using a fake mod.

## 2026-10-21 — first install on macOS

- The project was copied to a Mac. The README is written for Windows; the macOS equivalents are:
  mods folder `~/Library/Application Support/minecraft/mods`, venv activated with `source .venv/bin/activate`.
- Used the already-built jar `mod/build/libs/mcbot-0.2.1.jar` instead of rebuilding.
- The `python/.venv` folder came from Windows and had to be recreated.
- Fabric was first installed for Minecraft **1.21.11** instead of **1.21.1**, which made the game crash as soon as
  a script connected. Reinstalled for 1.21.1 → works. Details in [troubleshooting.md](troubleshooting.md).
- A `uv init` scaffold was added in `python/` (`pyproject.toml`, `main.py`, `.python-version`, empty `README.md`).

## 2026-10-22 — repository and name

- Project name chosen: **Craftilot** (craft + pilot).
- Git repository created (`main` branch, initial commit).
  - The empty Git repository created by `uv init` inside `python/` was removed, so there is a single repository.
  - `mod/.gitignore` ignored every folder named `build/`, including the source folder
    `mod/src/.../build/` (`BuildActions.java`). The rules are now anchored (`/build/`, `/bin/`, `/run/`…).
  - Downloaded jars at the root (Fabric installer, Fabric API) are ignored.
- Remote `origin` set to `git@github.com:LouisMLettry/Craftilot.git`. Not pushed yet: SSH authentication to GitHub
  was refused (`Permission denied (publickey)`).
- This `doc/` folder was created.

## 2026-10-22 — Python packaging and Minecraft version check

- **Python dependencies now live only in `python/pyproject.toml`, managed with uv.** `requirements.txt` was removed.
  Reason: uv was already used on the Mac, and one file avoids the two lists drifting apart. `uv.lock` records the
  exact versions. Setup is now `uv sync`, scripts run with `uv run python …`, tests with `uv run pytest tests`.
- Minimum Python set to **3.10** (what the code needs), instead of the 3.13 written by `uv init`.
  `.python-version` (3.13) is kept: it only chooses which Python uv uses locally.
- `uv init` leftovers removed: `main.py`, the empty `python/README.md`; the project is named `craftilot`
  (the import name stays `mcbot`).
- `fabric.mod.json` now requires Minecraft `1.21.1` exactly instead of `~1.21.1` (any 1.21.x), so a wrong version
  is refused at startup with a clear message.
- First build of the mod on the Mac: `./gradlew build` works with JDK 26 (no need to install JDK 25).
  The rebuilt `mcbot-0.2.1.jar` was copied into the Minecraft `mods` folder.
- The copy in `mods` was then replaced by a **symbolic link** to `mod/build/libs/mcbot-0.2.1.jar`: after
  `./gradlew build`, restarting Minecraft is enough to load the new mod. Only the jar is linked, not the folder,
  so Fabric doesn't also load the `-sources` jar.

## 2026-10-22 — Reading the world's blocks

- New mod command `blocks` and Python methods `get_blocks`, `get_chunk`, `get_blocks_around`, returning a
  `BlockVolume`. New demo `scan_blocks.py` (top-down map around the player).
- Decisions:
  - Blocks are read from the **game client's copy** of the world (no cheats, would also work in multiplayer), not
    from the singleplayer server. Consequence: only loaded chunks are available.
  - **One command for any box**; a chunk and a cube around the player are just particular boxes. The cube is
    computed by the mod, so it is centred on the player's position at the same tick.
  - **Palette + one `uint16` per block** in the binary part of the response (~200 KB per chunk, numpy-ready),
    instead of a JSON list of names (~2 MB) or Minecraft's internal ids (which change between versions).
  - Indexing `[x, y, z]` in Python, the most natural to read (Minecraft itself stores `[y, z, x]`).
  - Option `states=True` for full block states (orientation, open/closed…).
  - Heightmap left out for now; can be added later.
- Protocol: the binary part of a response is no longer always an image; the JSON field `payload` (`frame` or
  `blocks`) says what it is. In Java, `BotResponse.frame` was renamed `data`.
- Checked: the mod compiles, Python tests pass (22), and `scan_blocks.py` works in the game.

## 2026-10-22 — Scripts folder

- The demo scripts moved to `python/scripts/`; run them with `uv run python scripts/<name>.py` from `python/`.
- So that they can still `import mcbot` from that folder, `pyproject.toml` now declares `mcbot` as a package
  (build backend: hatchling), and `uv sync` installs it in the environment (editable: code changes apply directly).
- Images are still saved in `python/frames/`.

## 2026-10-22 — Python API reference

- Added [python-api.md](python-api.md): conventions (ticks, coordinates, angles, errors) and a reference with
  examples for `MinecraftClient`, `Builder` / `Phase` / `Placement` and `BlockVolume`.
- Fixed: `with connect_with_retry(...) as mc:` opened a second connection, because `with` connected again.
  It only worked because Python closed the first one immediately. `with` now keeps an existing connection.

## 2026-10-22 — Guidelines: ticks and short block names

- New [guidelines.md](../guidelines.md) at the root, gathering the project-wide assumptions and decisions.
- **Durations are always in ticks.** `forward(seconds)`, `turn(degrees, seconds=0.5)` and
  `look(pitch, seconds=0.5)` became `forward(ticks)`, `turn(degrees, ticks=10)` and `look(pitch, ticks=10)`;
  `TICKS_PER_SECOND` is exported. Only waits outside the game (connection retry, waiting for a world, network
  timeout) stay in seconds.
- **Block and item names lose the `minecraft:` prefix** in everything the mod returns (`stone`,
  `oak_log[axis=y]`); inputs still accept it. New `Names` class in the mod. Reason: shorter, and consistent with
  how names are written in Python. Trade-off: this assumes vanilla Minecraft without other mods.

## 2026-10-22 — Everything in English

- The whole repository is now in English: code comments and docstrings (mod and Python), messages printed by
  Python, `Builder.summary()`, the mod description, and the main README.
- Names created by the scripts were translated too: the house picture is `frames/house.png` (was `maison.png`),
  the demo frames are `01_start.png`, `02_forward_2s.png`… and the house phases are `Floor`,
  `Walls, door and torch`, `Roof, level n`.
- The README also gained the macOS commands next to the Windows ones.

## 2026-10-22 — Removing and replacing blocks

- `place_block` gets a `replace` option: if the cell holds another block, the mod breaks it and places the new
  one in the same tick (creative only); `replaced` names the broken block. Done in the mod rather than in Python
  so nothing can change between the break and the placement.
- New result `already_there` when the cell already holds the held block (only the block type is compared, not
  its state). `occupied` now also says which block is there (`block`).
- Builder:
  - `Placement(pos, "air")` empties a cell (calls `break_block`), so a plan describes the final result,
    holes included;
  - `Builder(mc, replace=True)` replaces cells holding another block;
  - counters split: `already_there` (already as planned) vs. `occupied` (list of cells left holding another
    block — before, both were counted together, so wrong blocks went unnoticed), plus `replaced` and `removed`.
- Tests: the fake mod moved to `tests/conftest.py` and now remembers placed blocks; new `tests/test_builder.py`.
- Checked: the mod compiles, 27 Python tests pass. **Not yet tested in the game.**

## 2026-10-22 — Writing exact block states

- New mod command `set_blocks` and Python methods `set_block(x, y, z, state)` / `set_blocks([...])`: write exact
  block states such as `oak_stairs[facing=east,half=top]` through the singleplayer server, like `/setblock`.
- Why: `place_block` acts like a player, so orientations (stairs, logs, doors) depend on where the player looks and
  can't be reproduced exactly; and it needs the player within reach.
- Decisions:
  - a **list** of blocks per request (batches of 4096 in Python), so writing a whole structure isn't hundreds of
    round trips;
  - blocks are written **as given, without updating neighbours**, so the result doesn't depend on the order
    (a torch written before its wall stays);
  - all states of a batch are parsed before anything is written;
  - the response comes once the game client shows the blocks, so a `get_blocks` right after is consistent.
- The controller's waiting logic (used by `game_mode`) was generalised for this.
- Checked: the mod compiles, 28 Python tests pass. **Not yet tested in the game.**

## 2026-11-02 — Reading entities

- New mod command `entities` and Python methods `get_entities(radius, types, limit, visibility)` /
  `get_entities_in(corner1, corner2, ...)`, returning a list of `Entity` (new `mcbot/entities.py`): mobs, dropped
  items and other players, nearest first, with type, category, position, movement, rotation, hitbox size, health,
  item, name…
- `step(..., entities=True | {options})` returns them in `info["entities"]`, **synchronised with the image**: the
  image is the last frame drawn, between two ticks, so the entities are listed while that frame is drawn (Fabric
  `WorldRenderEvents.END`, during the step's last tick) with its camera, projection and partial tick. Recorded as a
  rule in guidelines.md.
- Decisions:
  - **Client side only.** The client knows what the server sends: entities within their tracking range (about 8
    chunks for mobs), not their AI target or saved data. Reading through the singleplayer server is left for later.
  - Two flags rather than one `visible`: `in_view` (hitbox inside the camera frustum) and `line_of_sight` (a ray from
    the camera to the bottom, middle or top of the hitbox, through the blocks' **visual** shapes, so glass doesn't
    block; fluids ignored). Opt-in with `visibility`; cheap (a few microseconds per entity).
  - JSON only, no binary payload: even hundreds of entities are small.
  - `motion` is the movement during the last tick: the client's own velocity of other entities is often stale.
- New demo `scripts/scan_entities.py` (picture + table of entities and flags).
- Documented when the image of a `step` is taken (README, python-api.md): it can be up to one tick older than the
  player's state in `info`, and with `ticks=0` it comes from before the step. Not changed: making the image match
  `info` exactly would need waiting for an extra frame at the end of each step.
- Checked: the mod compiles, 31 Python tests pass. **Not yet tested in the game.**
