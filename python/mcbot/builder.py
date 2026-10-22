"""Automatic building: places a list of blocks, phase by phase, flying within reach of each phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .client import MinecraftClient

HOTBAR_SIZE = 9


@dataclass(frozen=True)
class Placement:
    """A block to place: position (world coordinates), block identifier and clicked face.

    The block ``"air"`` means the cell must be emptied: the builder breaks whatever is there.
    """

    pos: tuple[int, int, int]
    block: str
    face: str = "up"

    @property
    def is_removal(self) -> bool:
        return self.block.removeprefix("minecraft:") == "air"


@dataclass
class Phase:
    """Group of blocks placed from the same spot (feet position), from which they are all within reach."""

    name: str
    standpoint: tuple[float, float, float]
    blocks: list[Placement] = field(default_factory=list)


class Builder:
    """Runs the phases one after the other: flies to each phase's spot, then places its blocks one by one.

    A cell holding another block than the planned one is left as it is and listed in ``occupied``, unless
    ``replace=True``: then the old block is broken and the planned one placed.
    """

    def __init__(self, mc: MinecraftClient, delay_ticks: int = 2, replace: bool = False,
                 log: Callable[[str], None] = print):
        self.mc = mc
        self.delay_ticks = delay_ticks
        self.replace = replace
        self.log = log
        self.placed = 0
        self.replaced = 0
        self.removed = 0
        self.already_there = 0
        self.occupied: list[tuple[Placement, str]] = []  # (placement, block found in the cell)
        self.failures: list[tuple[Placement, str]] = []
        self._slots: dict[str, int] = {}
        self._held: str | None = None

    def build(self, phases: list[Phase]) -> None:
        for phase in phases:
            self.log(f"-- {phase.name}: {len(phase.blocks)} blocks")
            self.mc.fly_to(*phase.standpoint)
            for placement in phase.blocks:
                self.place(placement)

    def select(self, block: str) -> None:
        """Puts the block in hand; each new block takes the next hotbar slot."""
        if block == self._held:
            return
        slot = self._slots.setdefault(block, len(self._slots) % HOTBAR_SIZE)
        self.mc.select_block(block, slot=slot)
        self._held = block

    def place(self, placement: Placement) -> bool:
        """Places the block (or empties the cell for ``"air"``) from where the player is now.

        Returns True if the cell was changed.
        """
        changed = self._remove(placement) if placement.is_removal else self._place(placement)
        if self.delay_ticks:
            self.mc.step(ticks=self.delay_ticks)
        return changed

    def summary(self) -> str:
        parts = [f"{self.placed} blocks placed"]
        if self.replaced:
            parts[0] += f" ({self.replaced} replacing another block)"
        if self.removed:
            parts.append(f"{self.removed} removed")
        if self.already_there:
            parts.append(f"{self.already_there} cells already as planned")
        if self.occupied:
            parts.append(f"{len(self.occupied)} cells occupied by another block")
        if self.failures:
            parts.append(f"{len(self.failures)} failures")
        return ", ".join(parts)

    def _place(self, placement: Placement) -> bool:
        self.select(placement.block)
        info = self.mc.place_block(*placement.pos, face=placement.face, replace=self.replace)
        if info["placed"]:
            self.placed += 1
            if info.get("replaced"):
                self.replaced += 1
        elif info.get("reason") == "already_there":
            self.already_there += 1
        elif info.get("reason") == "occupied":
            self.occupied.append((placement, info["block"]))
            self.log(f"   ~ {placement.block} at {placement.pos}: occupied by {info['block']}")
        else:
            self._fail(placement, info)
        return bool(info["placed"])

    def _remove(self, placement: Placement) -> bool:
        info = self.mc.break_block(*placement.pos)
        if info["broken"]:
            self.removed += 1
        elif info.get("reason") == "empty":
            self.already_there += 1
        else:
            self._fail(placement, info)
        return bool(info["broken"])

    def _fail(self, placement: Placement, info: dict[str, Any]) -> None:
        self.failures.append((placement, info.get("message", info.get("reason", "?"))))
        self.log(f"   ! {placement.block} at {placement.pos}: {info.get('message')}")
