"""Blocs du monde renvoyés par le mod : une palette de noms et, pour chaque bloc, son indice dans la palette."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BlockVolume:
    """Blocs d'une boîte du monde.

    ``ids[i, j, k]`` est l'indice dans ``palette`` du bloc en ``origin + (i, j, k)`` (coordonnées monde),
    par exemple ``palette[ids[0, 0, 0]] == "minecraft:stone"``.
    """

    ids: np.ndarray  # (taille x, taille y, taille z), uint16
    palette: list[str]
    origin: tuple[int, int, int]

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.ids.shape

    def contains(self, x: float, y: float, z: float) -> bool:
        return all(0 <= c < s for c, s in zip(self._local(x, y, z), self.shape))

    def block_at(self, x: float, y: float, z: float) -> str:
        """Nom du bloc aux coordonnées monde (x, y, z)."""
        if not self.contains(x, y, z):
            raise IndexError(f"({x}, {y}, {z}) est hors de la boîte (origine {self.origin}, taille {self.shape})")
        return self.palette[self.ids[self._local(x, y, z)]]

    def mask(self, block: str) -> np.ndarray:
        """Tableau de booléens de même forme que ``ids`` : vrai là où se trouve ``block`` (``"stone"`` ou
        ``"minecraft:stone"``). Si la palette contient les états (``states=True``), toutes les variantes comptent.
        """
        name = block if ":" in block else f"minecraft:{block}"
        matching = [i for i, entry in enumerate(self.palette) if entry.split("[", 1)[0] == name]
        return np.isin(self.ids, matching)

    def _local(self, x: float, y: float, z: float) -> tuple[int, int, int]:
        return tuple(math.floor(c) - o for c, o in zip((x, y, z), self.origin))
