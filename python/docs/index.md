---
hide:
  - navigation
---

# Craftilot

**Drive a Minecraft player from Python.** Move, look around, take pictures of the game, read the blocks and
entities around the player, and build, all from a Python script.

```python
from mcbot import MinecraftClient

with MinecraftClient() as mc:
    mc.config(width=160, height=90)             # size of the pictures
    image, info = mc.forward(20, frame=True)    # walk for 1 second, then take a picture
    print(info["pos"], image.shape)             # [12.3, -60.0, 4.5] (90, 160, 3)

    mobs = mc.get_entities(radius=16)           # what is around?
    blocks = mc.get_blocks_around(radius=8)     # and which blocks?
```

[Get started](getting-started/index.md){ .md-button .md-button--primary }
[API reference](reference/index.md){ .md-button }

## What you can do

<div class="grid cards" markdown>

-   :material-gamepad-variant-outline: **Control the player**

    ---

    Hold keys tick by tick, turn the camera, fly to a position.

    [:octicons-arrow-right-24: Moving and looking](guides/moving.md)

-   :material-camera-outline: **See the game**

    ---

    Get the image of the game as a numpy array, at the size you need.

    [:octicons-arrow-right-24: Images](guides/images.md)

-   :material-cube-outline: **Read the world**

    ---

    Read boxes of blocks, whole chunks, or the cube around the player.

    [:octicons-arrow-right-24: Reading blocks](guides/blocks.md)

-   :material-sheep: **Find entities**

    ---

    List mobs, dropped items and players, with what the camera can see.

    [:octicons-arrow-right-24: Entities](guides/entities.md)

-   :material-wall: **Build**

    ---

    Place blocks like a player, or write exact block states anywhere.

    [:octicons-arrow-right-24: Building](guides/building.md)

-   :material-sync: **Close the loop**

    ---

    Observe, decide, act: the pattern behind agents and learning.

    [:octicons-arrow-right-24: Writing a control loop](guides/control-loop.md)

</div>

## How it works

```
 your Python script ──  mcbot  ──TCP 127.0.0.1:5555──▶  McBot mod  ──▶  Minecraft 1.21.1
                         ◀── player state, image, blocks, entities ──
```

Three names, three parts:

- **Craftilot** is the whole project (this site, the [repository](https://github.com/LouisMLettry/Craftilot)).
- **McBot** is the Fabric mod that runs inside Minecraft. It opens a local TCP server and executes the commands it
  receives on the game's own thread, tick by tick.
- **mcbot** is the Python package you import. Each method sends one command and returns the player's state, plus
  an image, blocks or entities when you ask for them.

The game runs in real time (20 ticks per second) and the mod only acts on the game **client**: it sees what a player
would see, and nothing more. See [Limits](concepts/limits.md).
