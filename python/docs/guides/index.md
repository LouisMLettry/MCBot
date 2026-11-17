# Guides

Each guide shows how to do one thing, with code you can copy. They assume you have done
[Getting started](../getting-started/index.md) and have a connected client `mc`:

```python
from mcbot import connect_with_retry

with connect_with_retry() as mc:
    mc.wait_for_world()
    ...  # the code of the guides goes here
```

| Guide | You will learn to… |
|---|---|
| [Moving and looking](moving.md) | hold keys, turn the camera, fly to a position, change the game mode |
| [Images](images.md) | get pictures of the game, choose their size, hide the interface, know when they are taken |
| [Reading blocks](blocks.md) | read a box of blocks, a chunk, the cube around the player, and search them with numpy |
| [Entities](entities.md) | list mobs, items and players, follow one, know which ones the camera sees |
| [Building](building.md) | place and break blocks like a player, write exact block states, build a whole plan |
| [Writing a control loop](control-loop.md) | observe, decide and act in a loop, the basis of agents and reinforcement learning |
