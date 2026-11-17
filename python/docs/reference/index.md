# API reference

Every class, method and constant of the `mcbot` package, generated from the code. Everything can be imported from
the package itself:

```python
from mcbot import (MinecraftClient, connect_with_retry, McBotError, TICKS_PER_SECOND,
                   BlockVolume, Entity, Builder, Phase, Placement)
```

| Name | What it is |
|---|---|
| [`MinecraftClient`][mcbot.MinecraftClient] | The connection to the mod. Every command is one of its methods. |
| [`connect_with_retry`][mcbot.connect_with_retry] | Connects, waiting for Minecraft to start. |
| [`McBotError`][mcbot.McBotError] | Raised when the mod refuses a command. |
| [`TICKS_PER_SECOND`][mcbot.client.TICKS_PER_SECOND] | 20. |
| [`BlockVolume`][mcbot.BlockVolume] | The blocks of a box, returned by `get_blocks` and friends. |
| [`Entity`][mcbot.Entity] | A mob, dropped item or player, returned by `get_entities` and `step`. |
| [`Builder`][mcbot.Builder], [`Phase`][mcbot.Phase], [`Placement`][mcbot.Placement] | Build a plan of blocks automatically. |

The [Protocol](protocol.md) page describes the messages between the package and the mod, to talk to the mod from
another language.

## MinecraftClient methods by topic

| Topic | Methods |
|---|---|
| Connection | [`connect`][mcbot.MinecraftClient.connect], [`close`][mcbot.MinecraftClient.close], [`ping`][mcbot.MinecraftClient.ping], [`wait_for_world`][mcbot.MinecraftClient.wait_for_world], [`config`][mcbot.MinecraftClient.config] |
| Moving | [`step`][mcbot.MinecraftClient.step], [`stop`][mcbot.MinecraftClient.stop], [`forward`][mcbot.MinecraftClient.forward], [`turn`][mcbot.MinecraftClient.turn], [`look`][mcbot.MinecraftClient.look], [`jump`][mcbot.MinecraftClient.jump], [`fly_to`][mcbot.MinecraftClient.fly_to] |
| Game mode | [`set_game_mode`][mcbot.MinecraftClient.set_game_mode], [`set_build_mode`][mcbot.MinecraftClient.set_build_mode], [`set_flying`][mcbot.MinecraftClient.set_flying] |
| Building | [`select_block`][mcbot.MinecraftClient.select_block], [`place_block`][mcbot.MinecraftClient.place_block], [`break_block`][mcbot.MinecraftClient.break_block], [`set_block`][mcbot.MinecraftClient.set_block], [`set_blocks`][mcbot.MinecraftClient.set_blocks] |
| Reading blocks | [`get_blocks`][mcbot.MinecraftClient.get_blocks], [`get_chunk`][mcbot.MinecraftClient.get_chunk], [`get_blocks_around`][mcbot.MinecraftClient.get_blocks_around] |
| Entities | [`get_entities`][mcbot.MinecraftClient.get_entities], [`get_entities_in`][mcbot.MinecraftClient.get_entities_in] |
