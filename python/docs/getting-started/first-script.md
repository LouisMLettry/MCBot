# Your first script

With Minecraft open and a world loaded, save this as `python/scripts/hello.py`:

```python
from PIL import Image

from mcbot import connect_with_retry

with connect_with_retry() as mc:                  # (1)!
    info = mc.wait_for_world()                    # (2)!
    print("Standing at", info["pos"], "looking at yaw", info["yaw"])

    mc.config(width=320, height=180)              # (3)!
    image, info = mc.forward(40, frame=True)      # (4)!
    print("Walked to", info["pos"])

    mc.turn(90)                                   # (5)!
    image, info = mc.stop(frame=True)             # (6)!
    Image.fromarray(image).save("hello.png")
```

1.  Connects to the mod on `127.0.0.1:5555`, and keeps retrying while Minecraft isn't running. The `with` block
    closes the connection at the end, which also releases every key.
2.  Waits until a world is loaded, so you can start the script from the main menu. Returns the player's state:
    the `info` dictionary.
3.  Images will be 320 × 180 pixels: the game window shrunk to that size.
4.  Walks forward for 40 ticks (2 seconds, at 20 ticks per second), then returns a picture and the new state.
5.  Turns 90° to the right, over 10 ticks.
6.  Releases all keys. **Keys stay pressed until the next command**, so always end with `stop()` (or close the
    connection).

Run it:

```bash
cd python
uv run python scripts/hello.py
```

```
Connecting to Minecraft on 127.0.0.1:5555...
Standing at [8.5, -60.0, 8.5] looking at yaw 0.0
Walked to [8.5, -60.0, 17.13]
```

`hello.png` shows what the player sees.

## What happened

Every method sends **one command** to the mod and waits for its answer. Each answer carries the player's state,
`info`, a plain dictionary:

```python
info["pos"]        # feet position [x, y, z]
info["yaw"]        # where the player looks, in degrees (0 = south)
info["on_ground"]  # True / False
info["health"]     # 20.0 = full health
```

The full list is in [The player's state](../concepts/state.md).

The image is a numpy array of shape `(height, width, 3)`, RGB, `uint8`: ready for Pillow, OpenCV or a neural
network.

## The one method to know: `step`

All the movement shortcuts (`forward`, `turn`, `look`, `jump`, `stop`) call
[`step`][mcbot.MinecraftClient.step], which holds any set of keys for some ticks while turning the camera:

```python
# For 1 second: walk forward, sprint, jump, and turn 45° left. Return a picture at the end.
image, info = mc.step(ticks=20, frame=True, forward=True, sprint=True, jump=True, yaw=-45)
```

Keys: `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`, `attack`, `use`.

## Next steps

- Move with precision, fly, change the game mode: [Moving and looking](../guides/moving.md).
- Read the world: [Reading blocks](../guides/blocks.md) and [Entities](../guides/entities.md).
- Write an agent that observes and acts: [Writing a control loop](../guides/control-loop.md).
- Browse the [Examples](../examples.md): complete scripts you can run and copy.
