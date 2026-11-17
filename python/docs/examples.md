# Examples

Complete scripts in [`python/scripts/`](https://github.com/LouisMLettry/Craftilot/tree/main/python/scripts). Run
them from the `python` folder, with Minecraft open and a world loaded:

```bash
cd python
uv run python scripts/<name>.py
```

Every script accepts `--host` and `--port`, and starts even before the game: it waits for Minecraft and for a
world. Pictures are saved in `python/frames/`.

| Script | Shows | Options |
|---|---|---|
| [`demo_movements.py`](https://github.com/LouisMLettry/Craftilot/blob/main/python/scripts/demo_movements.py) | walking, turning, jumping, looking up and down, sprinting, with a picture after each move | |
| [`scan_blocks.py`](https://github.com/LouisMLettry/Craftilot/blob/main/python/scripts/scan_blocks.py) | reading the cube around the player; prints a top-down map and a count of each block | `--radius 8` |
| [`watch_entities.py`](https://github.com/LouisMLettry/Craftilot/blob/main/python/scripts/watch_entities.py) | standing still and listing the entities every second, with the ones that appear and leave | `--radius 32`, `--every 20`, `--scans 0` |
| [`build_house.py`](https://github.com/LouisMLettry/Craftilot/blob/main/python/scripts/build_house.py) | building a 7 × 7 house with `Builder`, in 6 phases, then taking a picture of it | `--delay 2` |
| [`check_set_blocks.py`](https://github.com/LouisMLettry/Craftilot/blob/main/python/scripts/check_set_blocks.py) | checks `set_block` / `set_blocks` in your game: exact states, validation, large writes; cleans up after itself | `--skip-far` |

!!! tip "Where to run them"
    A *Superflat* world in *Creative* mode is the easiest: `build_house.py` needs about 10 × 10 free blocks in front
    of the player, and the scans are easier to read on flat ground.
