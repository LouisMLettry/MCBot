# The player's state

[](){#info-dictionary}
## The info dictionary

Every command returns the player's state as a plain dictionary, usually called `info`. It is read at the tick the
command finished.

```python
info = mc.ping()
info["pos"]          # [8.5, -60.0, 8.5]
```

| Key | Type | Meaning |
|---|---|---|
| `pos` | `[x, y, z]` | Feet position. |
| `motion` | `[vx, vy, vz]` | Velocity, in blocks per tick. |
| `yaw`, `pitch` | `float` | Where the player looks, in degrees (see [Coordinates and angles](space.md#yaw-and-pitch)). |
| `on_ground` | `bool` | Standing on a block. |
| `flying` | `bool` | Flying now. |
| `may_fly` | `bool` | Allowed to fly (creative, spectator). |
| `health` | `float` | Health points, 20 = full. |
| `game_mode` | `str` | `"survival"`, `"creative"`, `"adventure"` or `"spectator"`. |
| `reach` | `float` | How far blocks can be reached, from the eyes. |
| `selected_slot` | `int` | Selected hotbar slot, 0 to 8. |
| `held_item` | `str` | Item in hand, such as `"stone"`; `"air"` if empty. |
| `in_world` | `bool` | A world is loaded. When `False`, the player keys above are missing. |
| `paused` | `bool` | The game is paused. |
| `screen` | `str` or `None` | The menu open (a Java class name, which depends on how the game was started), `None` if none. |
| `tick` | `int` | Ticks counted since the game started: compare two to measure game time. |
| `frame_width`, `frame_height` | `int` | Size of the images. |

## Keys added by some commands

| Command | Adds |
|---|---|
| [`step`][mcbot.MinecraftClient.step] with `entities=...` | `entities`: a list of [`Entity`][mcbot.Entity] |
| [`place_block`][mcbot.MinecraftClient.place_block] | `placed`, `target`, `block`, `replaced`; on failure `reason`, `message` |
| [`break_block`][mcbot.MinecraftClient.break_block] | `broken`, `block`; on failure `reason`, `message` |
| [`select_block`][mcbot.MinecraftClient.select_block] | `slot`, `item`, `is_block` |
| [`set_block`][mcbot.MinecraftClient.set_block] | `block`: the full state written; `changed` |
| [`set_blocks`][mcbot.MinecraftClient.set_blocks] | `blocks`: the full state written for each entry; `changed`: `[x, y, z, state now]` for the cells the game changed on its own |

The image, blocks and entity lists returned by other methods come as their own values, not in `info`.
