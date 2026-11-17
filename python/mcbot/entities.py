"""Entities returned by the mod: mobs, dropped items, other players..."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Entity:
    """One entity, as the game client knows it.

    Names are without ``minecraft:`` (see guidelines.md). Fields that don't apply are ``None``: ``health`` for a
    dropped item, ``item`` for a mob, ``line_of_sight`` / ``in_view`` unless requested with ``visibility=True``.
    """

    id: int  # stays the same as long as the entity exists: follow an entity across requests with it
    type: str  # "zombie", "item", "player"...
    category: str  # "monster", "creature", "ambient", "water_creature", "misc"...
    pos: tuple[float, float, float]  # feet
    motion: tuple[float, float, float]  # movement during the last tick, in blocks
    yaw: float
    pitch: float
    size: tuple[float, float]  # hitbox width and height
    distance: float  # from the player's feet
    invisible: bool
    name: str | None = None  # custom name, or the name of a player
    health: float | None = None
    max_health: float | None = None
    baby: bool | None = None
    item: str | None = None  # dropped items only
    count: int | None = None
    line_of_sight: bool | None = None
    in_view: bool | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Entity":
        fields = {key: data.get(key) for key in cls.__dataclass_fields__}
        fields.update(pos=tuple(data["pos"]), motion=tuple(data["motion"]), size=tuple(data["size"]))
        return cls(**fields)

    @property
    def is_hostile(self) -> bool:
        return self.category == "monster"

    @property
    def box(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Hitbox, as its lowest and highest corners."""
        x, y, z = self.pos
        width, height = self.size
        return (x - width / 2, y, z - width / 2), (x + width / 2, y + height, z + width / 2)

    def distance_to(self, x: float, y: float, z: float) -> float:
        """Distance from the feet of the entity to a point."""
        return math.dist(self.pos, (x, y, z))
