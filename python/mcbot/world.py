"""World blocks returned by the mod: a palette of names and, for each block, its index in the palette."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BlockVolume:
    """The blocks of a box of the world, as returned by [`get_blocks`][mcbot.MinecraftClient.get_blocks],
    [`get_chunk`][mcbot.MinecraftClient.get_chunk] and
    [`get_blocks_around`][mcbot.MinecraftClient.get_blocks_around].

    Blocks are stored as a palette of names plus, for each cell, the index of its name in the palette:
    `palette[ids[i, j, k]]` is the block at world coordinates `origin + (i, j, k)`.

    The palette only lists the blocks present in this box, and its order changes from one request to the next:
    compare names, not ids, across requests. Empty space can be `air`, `cave_air` (underground) or `void_air`.

    Example:
        ```python
        import numpy as np

        volume = mc.get_blocks_around(radius=8)
        logs = np.argwhere(volume.mask("oak_log")) + volume.origin   # world positions of every log
        ```
    """

    ids: np.ndarray
    """Palette indices, numpy `uint16` array of shape `(size_x, size_y, size_z)`, indexed `[x, y, z]` from
    `origin`."""
    palette: list[str]
    """Block names (`"stone"`), or full states (`"oak_log[axis=y]"`) when read with `states=True`."""
    origin: tuple[int, int, int]
    """World coordinates of `ids[0, 0, 0]`, the lowest corner of the box."""

    @property
    def shape(self) -> tuple[int, int, int]:
        """Size of the box `(size_x, size_y, size_z)`, same as `ids.shape`."""
        return self.ids.shape

    def contains(self, x: float, y: float, z: float) -> bool:
        """Whether the world block `(x, y, z)` is inside the box. Floats are rounded down."""
        return all(0 <= c < s for c, s in zip(self._local(x, y, z), self.shape))

    def block_at(self, x: float, y: float, z: float) -> str:
        """Name (or state) of the block at world coordinates `(x, y, z)`. Floats are rounded down.

        Raises:
            IndexError: The position is outside the box.
        """
        if not self.contains(x, y, z):
            raise IndexError(f"({x}, {y}, {z}) is outside the box (origin {self.origin}, size {self.shape})")
        return self.palette[self.ids[self._local(x, y, z)]]

    def mask(self, block: str) -> np.ndarray:
        """Where a block is in the box.

        Args:
            block: Block name, such as `"stone"` (`"minecraft:stone"` is also accepted). With a palette of full
                states, every state of the block matches: `mask("oak_log")` finds logs of every orientation.

        Returns:
            A boolean array with the same shape as `ids`, true where the block is.
        """
        name = block.removeprefix("minecraft:")
        matching = [i for i, entry in enumerate(self.palette) if entry.split("[", 1)[0] == name]
        return np.isin(self.ids, matching)

    def _local(self, x: float, y: float, z: float) -> tuple[int, int, int]:
        return tuple(math.floor(c) - o for c, o in zip((x, y, z), self.origin))
