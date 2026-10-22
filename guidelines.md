# Guidelines

Project-wide assumptions and decisions. Follow them in new code, and update this file when a decision changes.
The history behind each decision is in [doc/journal.md](doc/journal.md).

## Target

- **Minecraft 1.21.1 exactly**, Java Edition, with Fabric Loader and a Fabric API built for `+1.21.1`.
  The mod refuses to load on any other version.
- **Vanilla Minecraft only:** no other mods that add blocks or items. Several rules below rely on it.
- The mod runs on the **game client**. Changing the game mode needs a singleplayer world; nothing needs cheats.

## Units and conventions

### Time: ticks

- **Every duration in the game is given in ticks.** 20 ticks = 1 second (`TICKS_PER_SECOND` in Python).
  Parameters are named `ticks` (or `..._ticks`, e.g. `delay_ticks`), never `seconds`.
- **Exception:** waits that happen *outside* the game, where ticks don't exist, are in seconds: retrying the
  connection while Minecraft isn't running, waiting for a world to be loaded, network timeouts.
  Their parameters say so (`retry_seconds`, `poll_seconds`, `timeout`).

### Block and item names: no `minecraft:` prefix

- Names are Minecraft identifiers **without** the `minecraft:` namespace: `stone`, `oak_log`, and with states
  `oak_log[axis=y]`.
- Everything the mod returns uses this form (palettes, `held_item`, `block`, `item`). Inputs also accept the
  prefixed form (`minecraft:stone`) for convenience.
- **This only works with vanilla Minecraft.** With other mods, two blocks could share a name in different
  namespaces (`minecraft:x` and `othermod:x`). Names from other namespaces keep their prefix, but this setup is
  not supported.

### Space

- World coordinates, `y` up. A **position** (`pos`) is the player's feet, as floats.
- A **block** `(x, y, z)` is the cube from `(x, y, z)` to `(x+1, y+1, z+1)`. Methods taking a block round floats
  down.
- **Chunk coordinates** are `block // 16` (`cx`, `cz`).
- Boxes given by two corners include both corners.

### Angles

- Degrees. `yaw` > 0 turns **right**, `pitch` > 0 looks **down** (−90 straight up, 90 straight down).
- Absolute yaw follows Minecraft: 0 = facing south (+z), 90 = west (−x), 180 / −180 = north (−z), −90 = east (+x).

### Arrays

- **Images:** numpy `uint8`, shape `(height, width, 3)`, RGB, top row first.
- **Blocks:** numpy `uint16` palette indices, shape `(size_x, size_y, size_z)`, indexed **`[x, y, z]`** from the
  box origin (its lowest corner). Minecraft stores `[y, z, x]` internally; we don't follow that.

## Mod ↔ Python protocol

- TCP on `127.0.0.1` only (port 5555 by default), **one client at a time**, one request → one response, in order.
- Integers big-endian. Request: length + JSON. Response: length + JSON, then length + **one** binary block
  (possibly empty), whose content is named by the JSON field `payload` (`frame`, `blocks`).
- **Every response includes the player's state**, read at the tick the command finished.
- **Errors vs. results:**
  - an invalid request or an impossible situation (no world, unknown block, chunk not loaded…) is an **error**:
    `{"ok": false, "error": "..."}`, raised in Python as `McBotError`;
  - an action that can normally fail in the game (placing a block where something already is) is a **result**:
    a success flag (`placed`, `broken`) plus `reason` and `message`.
- The mod only touches the game **on the game thread**: the network thread queues requests and waits.
- Keys held by `step` **stay pressed** until the next command; disconnecting releases everything.

When adding a command: document it in the README protocol table and in [doc/python-api.md](doc/python-api.md),
and teach it to the fake mod in `python/tests/test_client.py`.

## Python

- Python **3.10+**. Dependencies are declared only in `python/pyproject.toml` and managed with **uv**
  (`uv sync`, `uv run ...`); `uv.lock` is committed.
- The library is the `mcbot` package; runnable examples go in `python/scripts/`; images they save go in
  `python/frames/` (not in Git).
- Tests run **without Minecraft**, against a fake mod. Every change to the client or protocol gets a test.

## Java (mod)

- Compiled for Java 21 (like Minecraft 1.21.1); building needs JDK 25 or newer.
- Official Mojang mappings.
- The jar name contains the mod version (`mcbot-<version>.jar`); the Mac's `mods` folder links to it.

## Writing

- **Everything is in English:** code comments, docstrings, messages (mod errors, Python output), file names created
  by scripts, the README, `doc/` and this file.

## Documentation

- After a meaningful change, add a dated entry to [doc/journal.md](doc/journal.md), and update
  [doc/architecture.md](doc/architecture.md), [doc/python-api.md](doc/python-api.md),
  [doc/roadmap.md](doc/roadmap.md) or [doc/troubleshooting.md](doc/troubleshooting.md) when they are affected.
- When a project-wide rule changes, update this file.
