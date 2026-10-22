# Architecture

The system has two parts that run side by side on the same machine:

1. **The mod** (`mod/`, Java): a client-side Fabric mod loaded into Minecraft. It opens a local TCP server and
   executes the commands it receives on the player.
2. **The Python client** (`python/`): a small library (`mcbot`) that connects to that server, plus example scripts.

Python never touches the game directly: everything goes through the mod, one request → one response.

## Repository layout

```
.
├── README.md              Install & usage guide (French)
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
│           └── world/               BlockScan (reads the blocks of a box of the world)
└── python/
    ├── pyproject.toml     Python version, dependencies, and the `mcbot` package (managed with uv)
    ├── uv.lock            Exact versions installed by `uv sync`
    ├── mcbot/             The client library
    │   ├── client.py      MinecraftClient: protocol, movement, building, fly_to
    │   ├── builder.py     Builder / Phase / Placement: builds a list of blocks
    │   └── world.py       BlockVolume: blocks read from the world
    ├── scripts/           Demo scripts, run with `uv run python scripts/<name>.py`
    │   ├── demo_movements.py  Walk, turn, jump, sprint… and save frames
    │   ├── build_house.py     Build a small house, then take a picture
    │   └── scan_blocks.py     Top-down map of the blocks around the player
    ├── frames/            Images saved by the scripts (not in Git)
    └── tests/             Tests with a fake mod (no Minecraft needed)
```

## The mod

| Class | Role |
|---|---|
| `fabric.mod.json` | Mod metadata. Requires Minecraft **exactly 1.21.1**, so Fabric refuses to start on any other version instead of crashing later. |
| `McBotClient` | Fabric entry point. Reads the port (`-Dmcbot.port`, default 5555), hooks `BotController` on every client tick, starts `BotServer`. |
| `BotServer` | Background thread. Listens on `127.0.0.1` only, one client at a time. Reads a request, hands it to the controller, waits for the answer (120 s max), sends it back. On disconnect, asks the controller to release all keys. |
| `BotController` | Runs on the **game thread**, once per tick. Takes the next request from a queue and executes it. A `step` holds keys for N ticks (20 ticks = 1 s) and spreads the camera rotation over them. Also prevents the game from pausing while a script is connected, and keeps the player flying if the script asked for it. |
| `BuildActions` | Building helpers: switch game mode through the singleplayer server (works without cheats), fly, put a block in hand, place a block (no neighbour needed — you can build in the air), break a block. |
| `FrameCapture` | Takes a screenshot of what the game rendered and shrinks it to the requested size (e.g. 160×90), as raw RGB bytes. |
| `BlockScan` | Reads the blocks of a box (two corners, a whole chunk, or a cube around the player) from the game client's copy of the world. Only loaded chunks can be read. Returns a palette of block names plus one number per block. Limited to 1,048,576 blocks per request. |

Why the queue and the game thread: Minecraft's state may only be changed from its own thread. The TCP thread
therefore never touches the game; it only puts requests in the queue and waits.

## The Python client

| Piece | Role |
|---|---|
| `MinecraftClient` | Connection + one method per command (`ping`, `config`, `step`, `set_game_mode`, `set_flying`, `select_block`, `place_block`, `break_block`) and shortcuts (`forward`, `turn`, `look`, `jump`, `stop`). Images come back as numpy arrays `(height, width, 3)`. |
| `fly_to` | Flies to a target position. It predicts where the player would stop if all keys were released (creative flight keeps momentum) and presses keys to move that stopping point onto the target. |
| `Builder`, `Phase`, `Placement` | A build is a list of phases; each phase has a spot to fly to and the blocks reachable from there. The builder flies, picks the right block and places them one by one. |
| `get_blocks`, `get_chunk`, `get_blocks_around` → `BlockVolume` | Read the world. A `BlockVolume` holds `ids` (numpy `uint16`, indexed `[x, y, z]` from `origin`) and `palette` (the block name of each id), with helpers `block_at(x, y, z)` and `mask("water")`. |
| `connect_with_retry`, `wait_for_world` | Let a script be started before Minecraft or before entering a world. |

## The protocol

Big-endian integers, over TCP:

- **request:** `uint32 length` + JSON (UTF-8), always with a `type` field;
- **response:** `uint32 length` + JSON, then `uint32 length` + binary data (length 0 when there is none).
  The JSON field `payload` says what the binary data is: `frame` (raw RGB pixels) or `blocks` (one `uint16`
  palette index per block, ordered by x, then y, then z).

Every response contains the player's state (position, motion, yaw/pitch, health, game mode, held item…) plus the
result of the command. Errors come back as `{"ok": false, "error": "..."}` and are raised in Python as `McBotError`.
The full list of commands and fields is in the [main README](../README.md#6-protocole-pour-info).

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

- `test_client.py` starts a fake mod speaking the same protocol, including a simple simulation of flight physics
  to check that `fly_to` reaches its target, and a small block volume to check how blocks are decoded;
- `test_house.py` checks the house plan: no duplicate blocks, every block within reach of its standpoint, the player
  never standing inside a block.

The Java side has no automated tests; it is checked by running the game.
