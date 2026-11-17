# Architecture

The system has two parts that run side by side on the same machine:

1. **The mod** (`mod/`, Java): a client-side Fabric mod loaded into Minecraft. It opens a local TCP server and
   executes the commands it receives on the player.
2. **The Python client** (`python/`): a small library (`mcbot`) that connects to that server, plus example scripts.

Python never touches the game directly: everything goes through the mod, one request → one response.

## Repository layout

```
.
├── README.md              Install & usage guide
├── guidelines.md          Project-wide conventions and decisions
├── doc/                   This documentation
├── mod/                   Fabric mod (Gradle project)
│   ├── build.gradle, gradle.properties   Versions of Minecraft, Fabric, Loom
│   └── src/
│       ├── main/resources/fabric.mod.json   Mod metadata and dependencies
│       └── client/java/com/mcbot/
│           ├── McBotClient.java     Entry point
│           ├── BotController.java   Executes commands on the game thread
│           ├── BotException.java    "Expected" error returned to Python
│           ├── net/                 BotServer (TCP), BotResponse
│           ├── build/               BuildActions (game mode, flying, blocks)
│           ├── capture/             FrameCapture (screenshots)
│           └── world/               BlockScan (reads a box of the world), BlockWriter (writes exact states),
│                                    EntityScan (lists the entities around the player)
└── python/
    ├── pyproject.toml     Python version, dependencies, and the `mcbot` package (managed with uv)
    ├── uv.lock            Exact versions installed by `uv sync`
    ├── mcbot/             The client library
    │   ├── client.py      MinecraftClient: protocol, movement, building, fly_to
    │   ├── builder.py     Builder / Phase / Placement: builds a list of blocks
    │   ├── entities.py    Entity: mobs, dropped items, players
    │   └── world.py       BlockVolume: blocks read from the world
    ├── scripts/           Demo scripts, run with `uv run python scripts/<name>.py`
    │   ├── demo_movements.py  Walk, turn, jump, sprint… and save frames
    │   ├── build_house.py     Build a small house, then take a picture
    │   ├── scan_blocks.py     Top-down map of the blocks around the player
    │   ├── watch_entities.py  Stand still and list the entities every second
    │   └── check_set_blocks.py  Checks set_block / set_blocks in the game, then cleans up
    ├── docs/              User documentation (MkDocs site): guides, concepts, API reference
    ├── mkdocs.yml         Configuration of the documentation site
    ├── frames/            Images saved by the scripts (not in Git)
    └── tests/             Tests with a fake mod (no Minecraft needed)
```

## The mod

| Class | Role |
|---|---|
| `fabric.mod.json` | Mod metadata. Requires Minecraft **exactly 1.21.1**, so Fabric refuses to start on any other version instead of crashing later. |
| `McBotClient` | Fabric entry point. Reads the port (`-Dmcbot.port`, default 5555), hooks `BotController` on every client tick and every rendered frame, starts `BotServer`. |
| `BotServer` | Background thread. Listens on `127.0.0.1` only, one client at a time. Reads a request, hands it to the controller, waits for the answer (120 s max), sends it back. On disconnect, asks the controller to release all keys. |
| `BotController` | Runs on the **game thread**, once per tick. Takes the next request from a queue and executes it. A `step` holds keys for N ticks (20 ticks = 1 s) and spreads the camera rotation over them. Also prevents the game from pausing while a script is connected, and keeps the player flying if the script asked for it. |
| `BuildActions` | Building helpers: switch game mode through the singleplayer server (works without cheats), fly, put a block in hand, place a block (no neighbour needed — you can build in the air; optionally replacing the block already there), break a block. |
| `FrameCapture` | Takes a screenshot of what the game rendered and shrinks it to the requested size (e.g. 160×90), as raw RGB bytes. |
| `BlockWriter` | Writes exact block states through the singleplayer server (like `/setblock`, without cheats), without updating neighbouring blocks, in chunks the client has loaded only. The controller answers once the client shows them, or 10 ticks after the server wrote them (blocks the game changes on its own, like falling sand, never show as written); `changed` lists those cells. |
| `BlockScan` | Reads the blocks of a box (two corners, a whole chunk, or a cube around the player) from the game client's copy of the world. Only loaded chunks can be read. Returns a palette of block names plus one number per block. Limited to 1,048,576 blocks per request. |
| `EntityScan` | Lists the entities the client knows (within a radius or a box), nearest first, as JSON. Optionally tells for each one whether it is in the camera's field of view (frustum test on its hitbox) and in line of sight (up to 3 rays through the blocks' visual shapes). Works from a *view*: either the camera of a rendered frame, or the player's eyes at the current tick. |

Why the queue and the game thread: Minecraft's state may only be changed from its own thread. The TCP thread
therefore never touches the game; it only puts requests in the queue and waits.

### Images and entities

The game loop runs the ticks, then draws a frame. The controller answers at the end of a tick, so the image it
returns is the **last frame drawn**, which shows the world between the two previous ticks (Minecraft interpolates
positions and the camera with a "partial tick"). For a `step` returning an image and entities, the controller
therefore lists the entities **while that frame is drawn** (Fabric's `WorldRenderEvents.END`, during the step's last
tick), with the frame's camera, projection matrix and partial tick. The response carries the list of the last
frame drawn, so it matches the image exactly. If no frame was drawn during that tick (`ticks=0`, the game lagging),
the entities of the current tick are sent instead.

## The Python client

Full reference with parameters and examples: the [user documentation](https://louismlettry.github.io/Craftilot/), generated from the docstrings
and the pages in `python/docs/`.

| Piece | Role |
|---|---|
| `MinecraftClient` | Connection + one method per command (`ping`, `config`, `step`, `set_game_mode`, `set_flying`, `select_block`, `place_block`, `break_block`) and shortcuts (`forward`, `turn`, `look`, `jump`, `stop`). Images come back as numpy arrays `(height, width, 3)`. |
| `fly_to` | Flies to a target position. It predicts where the player would stop if all keys were released (creative flight keeps momentum) and presses keys to move that stopping point onto the target. |
| `Builder`, `Phase`, `Placement` | A build is a list of phases; each phase has a spot to fly to and the blocks reachable from there. The builder flies, picks the right block and places them one by one. A `"air"` placement empties a cell; with `replace=True`, cells holding another block are broken and refilled. |
| `get_blocks`, `get_chunk`, `get_blocks_around` → `BlockVolume` | Read the world. A `BlockVolume` holds `ids` (numpy `uint16`, indexed `[x, y, z]` from `origin`) and `palette` (the block name of each id), with helpers `block_at(x, y, z)` and `mask("water")`. |
| `get_entities`, `get_entities_in`, `step(entities=...)` → `Entity` | List the mobs, dropped items and players around the player, optionally with `in_view` / `line_of_sight`. |
| `connect_with_retry`, `wait_for_world` | Let a script be started before Minecraft or before entering a world. |

## The protocol

Big-endian integers, over TCP:

- **request:** `uint32 length` + JSON (UTF-8), always with a `type` field;
- **response:** `uint32 length` + JSON, then `uint32 length` + binary data (length 0 when there is none).
  The JSON field `payload` says what the binary data is: `frame` (raw RGB pixels) or `blocks` (one `uint16`
  palette index per block, ordered by x, then y, then z).

Every response contains the player's state (position, motion, yaw/pitch, health, game mode, held item…) plus the
result of the command. Errors come back as `{"ok": false, "error": "..."}` and are raised in Python as `McBotError`.
The full list of commands and fields is in the [main README](../README.md#6-protocol-for-reference).

A response carries at most one binary block, so a single request can't return an image *and* blocks.

## Versions

| Item | Version |
|---|---|
| Minecraft | 1.21.1 |
| Fabric Loader | 0.19.5 |
| Fabric API | 0.116.17+1.21.1 |
| Fabric Loom (Gradle plugin) | 1.18-SNAPSHOT |
| Gradle | 9.7.1 (wrapper) |
| Java | mod compiled for Java 21; building needs JDK 25 or newer (required by Loom; JDK 26 works) |
| Python | 3.10+; `numpy`, `pillow` (and `pytest` for development), declared in `python/pyproject.toml` |

## Tests

`python/tests/` checks the Python side without Minecraft:

- `conftest.py` holds the fake mod shared by the tests: it speaks the same protocol, simulates flight physics,
  remembers the blocks placed and broken (with the same `already_there` / `occupied` / `replace` rules as the mod),
  and returns a small block volume and two entities;
- `test_client.py` checks the client: requests sent, images, blocks and entities decoded, `fly_to` reaching its
  target;
- `test_builder.py` checks how the builder handles each cell (placed, already there, occupied, replaced, removed);
- `test_house.py` checks the house plan: no duplicate blocks, every block within reach of its standpoint, the player
  never standing inside a block.

The Java side has no automated tests; it is checked by running the game.
