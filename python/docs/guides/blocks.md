# Reading blocks

## Three ways to read

All three return a [`BlockVolume`][mcbot.BlockVolume]:

```python
volume = mc.get_blocks((0, -61, 0), (15, -55, 15))   # a box between two corners (both included)
volume = mc.get_chunk()                               # the player's whole chunk (16 × height × 16)
volume = mc.get_blocks_around(radius=8)               # a 17 × 17 × 17 cube centred on the player's feet
```

Only **loaded** chunks can be read (those within render distance), and a request covers at most 1,048,576 blocks
(3 × 3 full chunks). See [Limits](../concepts/limits.md).

## Look up a block

```python
volume.block_at(3, -61, 4)      # "grass_block"
volume.contains(3, -61, 4)      # True if the position is inside the box
```

Positions are world coordinates; floats are rounded down, so you can pass the player's position:

```python
x, y, z = mc.ping()["pos"]
volume.block_at(x, y - 1, z)    # the block under the feet
```

## Work with the whole box in numpy

A volume is a palette of names plus an array of indices into it:

```python
volume.palette          # ["air", "grass_block", "dirt", "oak_log", ...]
volume.ids              # numpy uint16 array, shape (size_x, size_y, size_z), indexed [x, y, z]
volume.origin           # world position of ids[0, 0, 0], the lowest corner

volume.palette[volume.ids[i, j, k]]      # the block at origin + (i, j, k)
```

[`mask`][mcbot.BlockVolume.mask] gives a boolean array of where a block is, which makes most searches one line:

```python
import numpy as np

# World positions of every log in the box
logs = np.argwhere(volume.mask("oak_log")) + volume.origin

# The nearest water
water = np.argwhere(volume.mask("water")) + volume.origin
if len(water):
    nearest = water[np.argmin(np.linalg.norm(water - (x, y, z), axis=1))]

# How many blocks of each kind
counts = np.bincount(volume.ids.ravel(), minlength=len(volume.palette))
{volume.palette[i]: int(n) for i, n in enumerate(counts) if n}

# A horizontal slice of a chunk at y = -60, indexed [x, z]
chunk = mc.get_chunk()
layer = chunk.ids[:, -60 - chunk.origin[1], :]
```

!!! tip "Compare names, not ids"
    The palette only lists the blocks of this box, in no fixed order: the same id can mean another block in the
    next request. Compare names (`volume.palette[...]`) or masks across requests.

## Empty space

Empty cells can be `air`, `cave_air` (underground) or `void_air`. To test for any of them:

```python
empty = volume.mask("air") | volume.mask("cave_air") | volume.mask("void_air")
```

## Block states

By default the palette holds block **names**. With `states=True`, it holds full **states**, with their
properties:

```python
volume = mc.get_blocks((0, -60, 0), (3, -58, 3), states=True)
volume.block_at(1, -60, 2)      # "oak_log[axis=x]" instead of "oak_log"
```

`mask("oak_log")` still matches every state of the block.

Names have no `minecraft:` prefix. See [Coordinates and angles](../concepts/space.md#block-names).
