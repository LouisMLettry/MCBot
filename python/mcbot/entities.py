"""Entities returned by the mod: mobs, dropped items, other players..."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Entity:
    """One entity (mob, dropped item, other player, arrow…), as the game knows it.

    Returned by [`get_entities`][mcbot.MinecraftClient.get_entities],
    [`get_entities_in`][mcbot.MinecraftClient.get_entities_in] and
    [`step(entities=...)`][mcbot.MinecraftClient.step]. Fields that don't apply to an entity are `None`.

    To show in an image, an entity must be `in_view`, in `line_of_sight` and not `invisible`.
    """

    id: int
    """Number of the entity in the game. Stays the same as long as the entity exists: use it to follow one entity
    across requests."""
    type: str
    """`"zombie"`, `"cow"`, `"item"` (dropped item), `"player"`, `"arrow"`…"""
    category: str
    """Minecraft's group: `"monster"`, `"creature"` (passive animals), `"ambient"` (bats), `"water_creature"`,
    `"water_ambient"`, `"underground_water_creature"`, `"axolotls"`, `"misc"` (items, arrows, players…)."""
    pos: tuple[float, float, float]
    """Feet position `(x, y, z)`, like the player's `pos`."""
    motion: tuple[float, float, float]
    """Movement during the last tick, in blocks."""
    yaw: float
    """Horizontal direction it faces, in degrees (same convention as the player)."""
    pitch: float
    """Vertical direction it faces, in degrees (positive: down)."""
    size: tuple[float, float]
    """Hitbox `(width, height)`, in blocks."""
    distance: float
    """Distance from the player's feet to the entity's feet."""
    invisible: bool
    """Under an invisibility effect: not drawn in images, even when in view."""
    name: str | None = None
    """Custom name (from a name tag), or a player's name."""
    health: float | None = None
    """Health points. Living entities only (mobs, players)."""
    max_health: float | None = None
    """Maximum health points. Living entities only."""
    baby: bool | None = None
    """Whether it is a baby. Living entities only."""
    item: str | None = None
    """Dropped items only: what the item is, such as `"oak_log"`."""
    count: int | None = None
    """Dropped items only: how many."""
    line_of_sight: bool | None = None
    """Only with `visibility=True`: a straight line from the camera reaches the bottom, middle or top of its
    hitbox without crossing a block. Blocks count by what you see: glass doesn't block, leaves do; water and lava
    don't block."""
    in_view: bool | None = None
    """Only with `visibility=True`: its hitbox is inside the camera's field of view. Slightly generous: a hitbox
    just outside a corner of the image can count as in view."""

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Entity":
        """Builds an entity from the mod's JSON. Used by the client; you don't normally need it."""
        fields = {key: data.get(key) for key in cls.__dataclass_fields__}
        fields.update(pos=tuple(data["pos"]), motion=tuple(data["motion"]), size=tuple(data["size"]))
        return cls(**fields)

    @property
    def is_hostile(self) -> bool:
        """Whether it is a monster (category `"monster"`)."""
        return self.category == "monster"

    @property
    def box(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Hitbox, as its lowest and highest corners `((x1, y1, z1), (x2, y2, z2))`."""
        x, y, z = self.pos
        width, height = self.size
        return (x - width / 2, y, z - width / 2), (x + width / 2, y + height, z + width / 2)

    def distance_to(self, x: float, y: float, z: float) -> float:
        """Distance from the entity's feet to a point."""
        return math.dist(self.pos, (x, y, z))
