# Errors

mcbot separates two kinds of problems.

## Exceptions: the command couldn't run

An **invalid request** or an **impossible situation** raises an exception:

| Exception | When | Examples |
|---|---|---|
| [`McBotError`][mcbot.McBotError] | the mod refused the command | no world loaded, unknown block, chunk not loaded (reading or writing blocks), box too large, `fly_to` target not reached, timeout while waiting for the game |
| `ValueError` | Python caught a bad argument before sending it | unknown key in `step`, unknown face, empty `set_blocks` |
| `OSError` / `ConnectionRefusedError` | can't connect | Minecraft not running, mod not loaded |
| `ConnectionError` | the connection was lost | Minecraft closed |
| `TimeoutError` | no answer within `timeout` seconds | another script holds the connection |

The message says what went wrong:

```python
from mcbot import McBotError

try:
    volume = mc.get_blocks((0, -64, 0), (1000, 100, 1000))
except McBotError as e:
    print(e)     # Box too large: 165330165 blocks (max 1048576)
```

## Results: the action was tried and didn't work

Some actions can normally fail in the game, like placing a block where another one already is. They **don't
raise**: the answer reports success with a flag, and why it failed with `reason` and `message`.

```python
info = mc.place_block(3, -60, 5)
if not info["placed"]:
    print(info["reason"])      # "occupied"
    print(info["message"])     # "Position already occupied by stone"
```

| Method | Flag | Reasons |
|---|---|---|
| [`place_block`][mcbot.MinecraftClient.place_block] | `placed` | `already_there`, `occupied`, `out_of_reach`, `no_block_selected`, `player_in_the_way`, `rejected` |
| [`break_block`][mcbot.MinecraftClient.break_block] | `broken` | `empty`, `out_of_reach`, `rejected` |

This lets an agent try something, see that it didn't work, and try something else, without `try`/`except` around
every action.
