# Writing a control loop

Most projects come down to a loop: **observe** the game, **decide** what to do, **act**, and repeat. With mcbot,
acting and observing are the same call: [`step`][mcbot.MinecraftClient.step] applies an action for some ticks and
returns what the player sees afterwards.

```python
image, info = mc.step(ticks=1, frame=True)          # first observation
while True:
    action = decide(image, info)                    # your code (rules, search, a network…)
    image, info = mc.step(ticks=4, frame=True, **action)
```

`action` is a dict of keys and turns, such as `{"forward": True, "yaw": 15}`.

## Choose the length of a step

`ticks` sets how long each action lasts, so how often your code decides:

| `ticks` | Decisions per second | Suits |
|---|---|---|
| 1 | 20 | precise control, but your code must keep up |
| 4 | 5 | a common choice for learning agents |
| 10–20 | 1–2 | high-level decisions (go there, turn around) |

## The game doesn't wait for you

Minecraft runs in **real time** at 20 ticks per second, whatever your script does. Between two commands, the world
goes on, and the keys of the last step **stay pressed**. If `decide` takes 200 ms, the player keeps walking for
4 more ticks.

- Keep `decide` fast, or call `mc.stop()` before a long computation.
- `info["tick"]` counts game ticks: compare two of them to see how much time really passed.

```python
_, before = mc.step(ticks=4, forward=True)
slow_decision()
_, after = mc.step(ticks=4, forward=True)
print(after["tick"] - before["tick"])     # 4 if decide was instant, more otherwise
```

## Reset between episodes

There is no "reset" command: build your own from the tools you have.

```python
def reset(mc):
    mc.set_build_mode(True)
    mc.fly_to(0.5, -60, 0.5)                     # back to the start (flying, creative)
    mc.set_flying(False)
    mc.set_blocks(((x, -61, z), "grass_block")   # rebuild the arena
                  for x in range(-10, 11) for z in range(-10, 11))
    mc.set_game_mode("survival")
    return mc.step(ticks=1, frame=True)
```

## An environment class

Wrapping the game in a class with `reset` and `step` keeps the rest of your code independent of Minecraft. This
one rewards getting close to a target:

```python
import math

import numpy as np

from mcbot import MinecraftClient

ACTIONS = [                       # a small discrete action space
    {"forward": True},
    {"yaw": -15},
    {"yaw": 15},
    {"forward": True, "jump": True},
]


class ReachTarget:
    def __init__(self, mc: MinecraftClient, target=(10.5, -60, 10.5), ticks=4, max_steps=200):
        self.mc, self.target, self.ticks, self.max_steps = mc, target, ticks, max_steps

    def reset(self):
        self.steps = 0
        self.mc.set_build_mode(True)           # fly_to needs creative
        self.mc.fly_to(0.5, -60, 0.5)
        self.mc.set_flying(False)
        image, info = self.mc.step(ticks=10, frame=True)
        self.distance = self._distance(info)
        return image, info

    def step(self, action: int):
        image, info = self.mc.step(ticks=self.ticks, frame=True, **ACTIONS[action])
        self.steps += 1
        distance = self._distance(info)
        reward, self.distance = self.distance - distance, distance   # reward getting closer
        terminated = distance < 1.0
        truncated = self.steps >= self.max_steps
        return image, reward, terminated, truncated, info

    def _distance(self, info):
        return math.dist(info["pos"], self.target)


with MinecraftClient() as mc:
    mc.config(width=84, height=84, hide_gui=True)
    env = ReachTarget(mc)
    image, info = env.reset()
    done = False
    while not done:
        image, reward, terminated, truncated, info = env.step(np.random.randint(len(ACTIONS)))
        done = terminated or truncated
    mc.stop()
```

The `reset` / `step` signatures follow [Gymnasium](https://gymnasium.farama.org/)'s; to use Gymnasium-compatible
libraries, subclass `gymnasium.Env` and declare an `action_space` and an `observation_space`.

## Observations beyond the image

Pixels are not the only input. Depending on your project, combine:

- the player's state: `info["pos"]`, `info["yaw"]`, `info["on_ground"]`, `info["health"]`…;
- the blocks around: `mc.get_blocks_around(radius=4).mask("stone")` is a small 3D boolean array. Use masks
  rather than `ids`, whose meaning changes from one request to the next (see [Reading blocks](blocks.md));
- the entities around: `step(..., entities={"radius": 16})` adds them to `info` at no extra request (see
  [Entities](entities.md)).

Each extra request takes time; ask only for what your agent uses.
