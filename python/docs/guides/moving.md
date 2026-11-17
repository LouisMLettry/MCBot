# Moving and looking

## Hold keys with `step`

[`step`][mcbot.MinecraftClient.step] holds a set of keys for some ticks (20 ticks = 1 second) while turning the
camera, then returns `(image, info)`:

```python
mc.step(ticks=20, forward=True)                       # walk 1 second
mc.step(ticks=10, forward=True, jump=True)            # jump forward
mc.step(ticks=40, forward=True, sprint=True)          # sprint 2 seconds
mc.step(ticks=20, left=True, yaw=90)                  # strafe left while turning 90° right
mc.step(ticks=5, attack=True)                         # hit (or start breaking a block)
mc.step(ticks=1, use=True)                            # right click: use an item, open a door…
```

Available keys: `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`, `attack`, `use`. A step can last
from 0 to 1200 ticks (1 minute).

!!! warning "Keys stay pressed"
    After a step, its keys **stay pressed** until the next command changes them. This makes consecutive steps
    smooth (no stop between two `forward` steps), but it also means the player keeps walking while your script
    thinks. Call [`stop()`][mcbot.MinecraftClient.stop] to release everything. Closing the connection releases
    them too.

## Turn the camera

`yaw` and `pitch` are **relative** turns in degrees, spread evenly over the ticks of the step:

- `yaw > 0` turns right, `yaw < 0` turns left;
- `pitch > 0` looks down, `pitch < 0` looks up. The pitch stays between −90 (straight up) and 90 (straight down).

```python
mc.step(ticks=10, yaw=90)      # quarter turn right in half a second
mc.step(ticks=0, pitch=-30)    # look 30° up, at once
```

The **absolute** direction is in `info["yaw"]` and `info["pitch"]`. To face a given direction, turn by the
difference:

```python
target_yaw = 180                                   # north
delta = (target_yaw - info["yaw"] + 180) % 360 - 180   # shortest way round
mc.step(ticks=10, yaw=delta)
```

See [Coordinates and angles](../concepts/space.md) for which yaw is which direction.

## Shortcuts

| Call | Does |
|---|---|
| [`forward(ticks, sprint=False, jump=False)`][mcbot.MinecraftClient.forward] | walk forward |
| [`turn(degrees, ticks=10)`][mcbot.MinecraftClient.turn] | turn on the spot |
| [`look(pitch, ticks=10)`][mcbot.MinecraftClient.look] | look up or down |
| [`jump()`][mcbot.MinecraftClient.jump] | jump once |
| [`stop()`][mcbot.MinecraftClient.stop] | release every key |

They all accept `frame=True` and return `(image, info)`.

## Change the game mode

Works in a singleplayer world, without cheats:

```python
mc.set_game_mode("creative")     # or "survival", "adventure", "spectator"
mc.set_build_mode(True)          # same as creative; False goes back to survival
```

The call returns once the new mode is applied.

## Fly

In creative mode, the player can fly. While flying, `jump` goes up and `sneak` goes down:

```python
mc.set_build_mode(True)
mc.set_flying(True)
mc.step(ticks=20, jump=True)            # go up for 1 second
mc.step(ticks=20, forward=True)         # fly forward
mc.set_flying(False)                    # fall back to the ground
```

[`fly_to(x, y, z)`][mcbot.MinecraftClient.fly_to] flies to a position by itself (feet position), stops there and
releases the keys:

```python
info = mc.fly_to(10.5, -55, 3.5)
print(info["pos"])     # within 0.75 blocks horizontally, 0.35 vertically
```

It raises [`McBotError`][mcbot.McBotError] if the target is not reached (blocked by a wall, for example).

## Read where you are

```python
info = mc.ping()       # the state, without doing anything
x, y, z = info["pos"]  # feet position
vx, vy, vz = info["motion"]   # blocks per tick
info["on_ground"], info["flying"]
```

All fields: [The player's state](../concepts/state.md).
