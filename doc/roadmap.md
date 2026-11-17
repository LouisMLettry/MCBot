# Roadmap

## Next

### More world information (when needed)

- **Heightmap:** for each column, the y of the highest block ("surface" or "motion-blocking" variant). Minecraft
  already keeps these per chunk, so they are cheap.
- **Biomes and light levels**, as options of the `blocks` command.
- **Blocks attached to each `step`** (e.g. radius 8 around the player) for reinforcement learning, without a
  separate request. Needs responses that can carry an image and blocks at the same time.
- **Notifications when blocks change**, to keep a world map up to date in Python. Needs the mod to push messages,
  not only answer requests.
- **Unloaded chunks**, read through the singleplayer server.

### Entities (follow-ups)

- **Screen boxes:** the rectangle of each entity's hitbox in the image (pixels), e.g. to train an object detector.
  The projection used for `in_view` already gives it.
- **Actions on an entity `id`:** `look_at_entity`, `attack_entity`.
- More fields if needed: held and worn items, head direction, whether a mob is aggressive.

## Housekeeping

- Push the repository to GitHub (needs an SSH key registered on the GitHub account).
- Possibly rename the mod / package (`mcbot`) to match the project name.

## Ideas

- A Gym-style environment (`reset` / `step` / observation / reward) on top of `MinecraftClient`, for reinforcement
  learning.
