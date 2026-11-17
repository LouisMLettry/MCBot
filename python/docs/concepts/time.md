# Time and ticks

## Ticks

Minecraft updates the world in **ticks**: 20 per second. Every duration in the game is given in ticks:

```python
from mcbot import TICKS_PER_SECOND     # 20

mc.forward(ticks=2 * TICKS_PER_SECOND) # walk 2 seconds
```

Only waits that happen **outside** the game are in seconds: retrying the connection (`retry_seconds`), waiting
for a world (`poll_seconds`), the network timeout (`timeout`).

## The game runs in real time

The game doesn't wait for your script. Between two commands, ticks go on and the world keeps changing: mobs move,
water flows, and **the keys of the last step stay pressed**. A step of `ticks=20` takes one second of real time,
plus the time to send the answer.

`info["tick"]` counts the ticks since the game started. The difference between two answers tells you how much game
time passed between them.

## Keys stay pressed

A [`step`][mcbot.MinecraftClient.step] holds its keys for `ticks` ticks, then **leaves them pressed** until the
next command. This makes a sequence of steps behave like continuous control:

```python
mc.step(ticks=10, forward=True)
mc.step(ticks=10, forward=True, yaw=30)    # no stop in between: a smooth curve
mc.stop()                                  # releases everything
```

Every command that is not a step (`ping`, `get_blocks`…) leaves the keys as they are. Closing the connection
releases them.

[](){#image-timing}
## When an image is taken

The game alternates between updating the world (a tick) and drawing it (a frame), and draws several frames per
tick. Frames show the world part-way between two ticks, so that movement looks smooth.

The mod answers at the end of a tick, and the image it returns is the **last frame drawn** before that. Two
consequences:

- **The image is slightly older than `info`.** The state in `info` (`pos`, `yaw`, `motion`…) is read at the end of
  the step, up to one tick after the image. At walking speed that is under 0.3 blocks; while turning, up to one
  tick of rotation.
- **With `ticks=0`, the image comes from before the step.** No frame is drawn during a step of 0 ticks, so the
  image doesn't show the rotation it applied. Use `ticks=1` or more when the image must show the result of an
  action.

Entities listed with an image (`step(frame=True, entities=...)`) are read **while that frame is drawn**, with its
camera: they match the image, not `info`. If no frame was drawn during the step (`ticks=0`, or the game is
lagging), they are read at the current tick instead.

## How long commands take

Commands are handled at the end of a tick, so each one first waits for the current tick to end (up to 50 ms).

| Command | Returns after |
|---|---|
| `step(ticks=n)` | `n` more ticks (n / 20 seconds); with `ticks=0`, right away |
| `ping`, `get_blocks`, `get_entities`… | right away |
| `set_game_mode` | the game shows the new mode (a few ticks); error after 5 seconds |
| `set_blocks` | the game shows the new blocks (a tick or two); half a second at most for blocks that change on their own |
| `fly_to` | arrival, or after `max_steps` steps |
