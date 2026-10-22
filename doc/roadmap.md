# Roadmap

## Next

### Read chunk / block information from Python

The game client already holds the chunks around the player (within render distance), so the mod can read them
without cheats. Proposed shape, not implemented yet:

```python
chunk = mc.get_chunk()              # chunk the player is in, or get_chunk(cx, cz)
chunk.blocks                        # numpy (384, 16, 16): one number per block
chunk.palette                       # names matching those numbers
chunk.heightmap                     # (16, 16)
mc.get_blocks((x1, y1, z1), (x2, y2, z2))   # a box, e.g. around the player
```

Block names would travel once as a list in the JSON, and the block numbers in the binary part of the response
(the slot used for images today).

Open questions:
- Which information is needed: block types only, or also block states, biome, light, entities?
- Whole chunks, a box around the player, or both?

Limitation: only loaded chunks can be read. This needs a rebuild of the mod (`./gradlew build`).

## Housekeeping

- Push the repository to GitHub (needs an SSH key registered on the GitHub account).
- Possibly rename the mod / package (`mcbot`) to match the project name.

## Ideas

- A Gym-style environment (`reset` / `step` / observation / reward) on top of `MinecraftClient`, for reinforcement
  learning.
