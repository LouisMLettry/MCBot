"""World blocks returned by the mod: a palette of names and, for each block, its index in the palette."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BlockVolume:
    """Blocks of a box of the world.

    ``ids[i, j, k]`` is the index in ``palette`` of the block at ``origin + (i, j, k)`` (world coordinates),
    for example ``palette[ids[0, 0, 0]] == "stone"`` (names without ``minecraft:``, see guidelines.md).
    """

    ids: np.ndarray  # (size x, size y, size z), uint16
    palette: list[str]
    origin: tuple[int, int, int]

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.ids.shape

    def contains(self, x: float, y: float, z: float) -> bool:
        return all(0 <= c < s for c, s in zip(self._local(x, y, z), self.shape))

    def block_at(self, x: float, y: float, z: float) -> str:
        """Name of the block at world coordinates (x, y, z)."""
        if not self.contains(x, y, z):
            raise IndexError(f"({x}, {y}, {z}) is outside the box (origin {self.origin}, size {self.shape})")
        return self.palette[self.ids[self._local(x, y, z)]]

    def mask(self, block: str) -> np.ndarray:
        """Boolean array with the same shape as ``ids``: true where ``block`` is (``"stone"``, ``"minecraft:"``
        accepted). If the palette contains states (``states=True``), every variant counts.
        """
        name = block.removeprefix("minecraft:")
        matching = [i for i, entry in enumerate(self.palette) if entry.split("[", 1)[0] == name]
        return np.isin(self.ids, matching)

    def _local(self, x: float, y: float, z: float) -> tuple[int, int, int]:
        return tuple(math.floor(c) - o for c, o in zip((x, y, z), self.origin))
