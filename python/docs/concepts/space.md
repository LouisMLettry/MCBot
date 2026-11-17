# Coordinates and angles

## World coordinates

Minecraft uses three axes, with **`y` up**:

| Axis | Positive direction |
|---|---|
| `x` | east |
| `y` | up |
| `z` | south |

Press ++f3++ in the game to see your coordinates and the direction you face.

## Positions and blocks

- A **position** is a point, given as floats. The player's position (`info["pos"]`) and an entity's `pos` are
  their **feet**. The player's eyes are 1.62 blocks above (1.27 when sneaking).
- A **block** `(x, y, z)` is the cube from `(x, y, z)` to `(x + 1, y + 1, z + 1)`, given as integers. Methods that
  take a block accept floats and round them down, so you can pass a position where a block is expected.
- The block **under** the feet is at `y - 1`.

```python
import math

x, y, z = info["pos"]                         # 3.7, -60.0, -1.2
block = (math.floor(x), math.floor(y), math.floor(z))   # (3, -60, -2)
```

A **box** given by two corners includes both corners: `get_blocks((0, 0, 0), (1, 1, 1))` reads 8 blocks.

## Chunks

The world is stored in **chunks** of 16 × 16 blocks, from the bottom to the top of the world. A block's chunk is
`(x // 16, z // 16)`. Only chunks around the player are loaded in the game (the render distance), and only those
can be read. In the overworld, the height goes from y = −64 to y = 319.

## Yaw and pitch

<figure markdown>
<svg viewBox="0 0 320 240" width="320" role="img" aria-label="Yaw seen from above: 0 faces south, 90 west, 180 north, -90 east" style="max-width: 100%; color: var(--md-default-fg-color)">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <circle cx="160" cy="120" r="70" fill="none" stroke="currentColor" stroke-opacity="0.25" stroke-dasharray="4 4"/>
  <circle cx="160" cy="120" r="9" fill="rgb(140, 198, 230)" stroke="currentColor"/>
  <line x1="160" y1="120" x2="160" y2="186" stroke="currentColor" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="160" y1="120" x2="94" y2="120" stroke="currentColor" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="160" y1="120" x2="160" y2="54" stroke="currentColor" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="160" y1="120" x2="226" y2="120" stroke="currentColor" stroke-width="2" marker-end="url(#arrow)"/>
  <g fill="currentColor" font-family="sans-serif" font-size="13" text-anchor="middle">
    <text x="160" y="210">yaw 0 · south (+z)</text>
    <text x="160" y="40">yaw 180 / −180 · north (−z)</text>
    <text x="52" y="116">yaw 90</text>
    <text x="52" y="132">west (−x)</text>
    <text x="268" y="116">yaw −90</text>
    <text x="268" y="132">east (+x)</text>
  </g>
</svg>
<figcaption>Seen from above, north up. Positive yaw turns right (clockwise seen from above).</figcaption>
</figure>

Angles are in degrees.

- **`yaw`** is the horizontal direction. As absolute values (`info["yaw"]`), 0 faces **south**, 90 west, 180 or
  −180 north, −90 east. As a turn (`step(yaw=...)`), **positive turns right**.
- **`pitch`** is the vertical direction: **positive looks down**. −90 is straight up, 0 is the horizon, 90 is
  straight down.

The direction the player faces, as a unit vector:

```python
import math

yaw, pitch = math.radians(info["yaw"]), math.radians(info["pitch"])
dx = -math.sin(yaw) * math.cos(pitch)
dy = -math.sin(pitch)
dz = math.cos(yaw) * math.cos(pitch)
```

And the yaw that faces a point `(tx, tz)` from the player:

```python
x, _, z = info["pos"]
target_yaw = math.degrees(math.atan2(-(tx - x), tz - z))
turn = (target_yaw - info["yaw"] + 180) % 360 - 180      # shortest turn, for step(yaw=turn)
```

## Block names

Blocks, items and entity types are named by their Minecraft identifier **without** the `minecraft:` prefix:
`"stone"`, `"oak_log"`, `"zombie"`. Everything the mod returns uses this form. Inputs also accept the prefixed form
(`"minecraft:stone"`).

A **block state** adds properties in brackets: `"oak_log[axis=x]"`, `"oak_stairs[facing=east,half=top]"`. The
[Minecraft wiki](https://minecraft.wiki/) lists the properties of each block. Read states with
`get_blocks(..., states=True)`; write them with [`set_block`][mcbot.MinecraftClient.set_block].

This only works with Minecraft **without other mods** that add blocks or items.

## Arrays

| Data | numpy type | Shape | Indexed |
|---|---|---|---|
| Images | `uint8` | `(height, width, 3)` | `[row, column, channel]`, RGB, top row first |
| Blocks (`BlockVolume.ids`) | `uint16` | `(size_x, size_y, size_z)` | `[x, y, z]` from the box's lowest corner |
