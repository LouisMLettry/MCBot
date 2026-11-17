# Limits

Know these before designing a project.

## Minecraft version and mods

- **Minecraft Java Edition 1.21.1 exactly**, with Fabric. The mod refuses to load on any other version (including
  1.21.11).
- **No other mods** that add blocks or items: block names are used without their `minecraft:` prefix, which only
  works for vanilla blocks.

## One script at a time, on the same computer

- The mod listens on `127.0.0.1:5555` only: your script must run on the computer that runs Minecraft.
- It serves **one connection at a time**. A second script waits until the first one disconnects.
- The port can be changed by starting the game with `-Dmcbot.port=XXXX`.

## Real time

The game runs at 20 ticks per second and doesn't wait for your script (see [Time and ticks](time.md)). You can't
speed it up or pause it from Python, and an experiment of one hour of game time takes one hour.

## What the player can know

The mod runs in the game **client**, the part that draws the world for the player. It knows what the server sends
to it, like a player would, and nothing more:

- **Blocks:** only the loaded chunks around the player (render distance, set in the game's video settings) can be
  read. Reading blocks further away raises an error.
- **Entities:** only those within the tracking range: about 8 chunks around for mobs, 6 for dropped items, never
  beyond render distance. A mob's internal state (its target, its path, its inventory) is not available.
- **Images:** the game window as drawn, shrunk to the size you set. Sizes from 16 to 1024 pixels per side.

## Sizes

| What | Limit |
|---|---|
| `step` | 0 to 1200 ticks (1 minute) |
| `get_blocks`, `get_chunk`, `get_blocks_around` | 1,048,576 blocks per request (3 × 3 full chunks) |
| `get_entities` | radius up to 256 blocks; up to 4096 entities |
| `set_blocks` | any number, sent in batches of 4096; loaded chunks only |
| Images | 16 to 1024 pixels per side |

## Singleplayer

Changing the game mode and writing blocks with `set_block` / `set_blocks` need a **singleplayer world** (they go
through the game's built-in server). Cheats don't need to be enabled.
