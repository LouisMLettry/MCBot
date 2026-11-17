# Building

There are two ways to change blocks:

| | [`place_block`][mcbot.MinecraftClient.place_block] / [`break_block`][mcbot.MinecraftClient.break_block] | [`set_block`][mcbot.MinecraftClient.set_block] / [`set_blocks`][mcbot.MinecraftClient.set_blocks] |
|---|---|---|
| Acts like | a player, with the block in hand | the `/setblock` command |
| Where | within reach (about 5 blocks) | in the loaded area around the player |
| Block | the one in hand, oriented like a player would | an exact state, such as `oak_stairs[facing=east]` |
| Neighbours | updated (a fence connects, a torch needs support) | not updated |
| Speed | one block per command | thousands per command |
| Game mode | creative is easiest (survival: blocks must be in the hotbar) | any, singleplayer world |

Use `place_block` when the *way* of building matters (an agent learning to build), and `set_blocks` to prepare a
scene quickly.

## Place blocks like a player

```python
mc.set_build_mode(True)                   # creative: unlimited blocks, instant breaking
mc.select_block("oak_planks", slot=0)     # put a block in hand
info = mc.place_block(10, -60, 6)         # the cell must be within reach
if not info["placed"]:
    print(info["reason"], info["message"])
```

- No neighbouring block is needed: you can build in mid-air.
- `face` is the side being "clicked", which orients some blocks: `"up"` gives a vertical log or a bottom slab,
  `"down"` a top slab, `"north"`, `"south"`, `"east"` or `"west"` a lying log.
- The player looks at the cell first (`look=True`), which orients stairs, doors and torches.
- A failure is not an exception: `placed` is `False` and `reason` says why: `already_there`, `occupied`,
  `out_of_reach`, `no_block_selected`, `player_in_the_way`, `rejected`.
- `replace=True` breaks the block in the cell first, if there is one (creative only).

```python
info = mc.break_block(10, -60, 6)         # creative only; info["broken"], info["block"]
```

## Write exact block states

```python
mc.set_block(0, -60, 0, "oak_stairs[facing=east,half=top]")

# Many blocks at once: a 10 × 10 glass floor
mc.set_blocks(((x, -61, z), "glass") for x in range(10) for z in range(10))

# Remove blocks by writing air
mc.set_blocks(((x, -61, z), "air") for x in range(10) for z in range(10))
```

- **Exact:** the block is written as given. Properties you leave out take their default value; the result tells
  you the full state (`info["block"]`, `info["blocks"]`).
- **No neighbour updates:** a torch written on air stays there, and a fence only connects where its state says
  (`oak_fence[east=true,west=true]`).
- **Loaded chunks only:** every cell must be in a chunk loaded around the player (the area `get_blocks` can
  read). Otherwise the call raises [`McBotError`][mcbot.McBotError] *Chunk (…) is not loaded*.
- **All or nothing per batch:** every state and position of a batch (4096 blocks) is checked first. One invalid
  entry raises [`McBotError`][mcbot.McBotError] and nothing of that batch is written.
- **Consistent:** the call returns once the game shows the new blocks, so a `get_blocks` right after sees them.
- **Blocks that change on their own:** some blocks react as soon as they are written, as in the game: sand over
  air falls, a redstone wire with nothing under it breaks, water spreads around its source. The call still
  succeeds (after half a second at most) and lists the cells that no longer hold what was written:

    ```python
    info = mc.set_block(0, -55, 0, "sand")
    info["changed"]     # [[0, -55, 0, "air"]]: the sand fell
    ```

## Build a whole plan

[`Builder`][mcbot.Builder] places a list of blocks the way a player would, flying from spot to spot. You describe
the result in **phases**: blocks that can all be reached from one standpoint.

```python
from mcbot import Builder, Phase, Placement

mc.set_build_mode(True)
builder = Builder(mc, delay_ticks=0)
builder.build([
    Phase("Wall", standpoint=(0.5, -58, 0.5),
          blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
    Phase("Logs", standpoint=(0.5, -58, 6.5),
          blocks=[Placement((x, -60, 8), "oak_log", face="east") for x in range(-2, 3)]),
    Phase("Door gap", standpoint=(0.5, -58, 0.5),
          blocks=[Placement((0, -60, 3), "air")]),     # "air" empties the cell
])
print(builder.summary())     # "10 blocks placed, 1 removed"
```

For each cell, the builder compares the plan with what is there:

| The cell holds… | Planned block | Planned `"air"` |
|---|---|---|
| nothing (or grass, water…) | placed | nothing to do |
| the planned block | nothing to do | broken |
| another block | left as it is, listed in `occupied`; with `replace=True`: broken, then placed | broken |

Tips:

- every block of a phase must be within reach of the standpoint (about 5 blocks from the eyes, 1.62 above the
  feet), and the standpoint must not be in a cell that will be filled;
- blocks are placed in list order: put supporting blocks first (before torches, doors);
- after the build, `builder.occupied` and `builder.failures` list what didn't go as planned.

`scripts/build_house.py` builds a 7 × 7 house (about 200 blocks in 6 phases): see [Examples](../examples.md).
