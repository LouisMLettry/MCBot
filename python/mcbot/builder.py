"""Automatic building: places a list of blocks, phase by phase, flying within reach of each phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .client import MinecraftClient

HOTBAR_SIZE = 9


@dataclass(frozen=True)
class Placement:
    """One cell of a plan: the block it must hold.

    The block `"air"` means the cell must be emptied: the builder breaks whatever is there.

    Example:
        ```python
        Placement((0, -60, 3), "oak_log", face="east")   # a lying log
        Placement((0, -59, 3), "air")                    # empty this cell
        ```
    """

    pos: tuple[int, int, int]
    """Block coordinates `(x, y, z)`."""
    block: str
    """Block name, such as `"cobblestone"`, or `"air"` to empty the cell."""
    face: str = "up"
    """Clicked face, which orients some blocks (see [`place_block`][mcbot.MinecraftClient.place_block])."""

    @property
    def is_removal(self) -> bool:
        """Whether this placement empties the cell (block `"air"`)."""
        return self.block.removeprefix("minecraft:") == "air"


@dataclass
class Phase:
    """A group of blocks placed from the same spot.

    Every block must be within reach of the standpoint (about 5 blocks from the eyes, which are 1.62 blocks above
    the feet), and the standpoint must not be in a cell that will be filled.
    """

    name: str
    """Shown in the log."""
    standpoint: tuple[float, float, float]
    """Feet position the player flies to before placing the blocks."""
    blocks: list[Placement] = field(default_factory=list)
    """Placed in this order: put supporting blocks first."""


class Builder:
    """Builds a plan, phase by phase: flies to each phase's standpoint, then places its blocks one by one.

    A plan describes the result you want. For each cell, the builder compares it with what is there:

    | The cell holds… | Planned block | Planned `"air"` |
    |---|---|---|
    | nothing (or grass, water…) | placed → `placed` | nothing to do → `already_there` |
    | the planned block | nothing to do → `already_there` | broken → `removed` |
    | another block | left as it is → `occupied`; with `replace=True`: broken, then placed → `placed` and `replaced` | broken → `removed` |

    The builder flies with [`fly_to`][mcbot.MinecraftClient.fly_to]: switch to creative first
    (`mc.set_build_mode(True)`).

    Args:
        mc: A connected client.
        delay_ticks: Ticks waited after each block (0: as fast as possible).
        replace: Whether cells holding another block are broken and refilled.
        log: Called with a message for each phase and each problem.

    Example:
        ```python
        mc.set_build_mode(True)
        builder = Builder(mc, delay_ticks=0)
        builder.build([
            Phase("Wall", standpoint=(0.5, -58, 0.5),
                  blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
        ])
        print(builder.summary())
        ```

    Attributes:
        placed: Number of blocks placed.
        replaced: Among them, how many replaced another block.
        removed: Number of blocks broken for `"air"` placements.
        already_there: Cells that were already as planned.
        occupied: `(placement, block found)` for the cells left holding another block (only without `replace`).
        failures: `(placement, message)` for the cells that couldn't be changed (out of reach, refused…).
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
        """Builds all phases, in order.

        Raises:
            McBotError: A standpoint couldn't be reached (see [`fly_to`][mcbot.MinecraftClient.fly_to]).
        """
        for phase in phases:
            self.log(f"-- {phase.name}: {len(phase.blocks)} blocks")
            self.mc.fly_to(*phase.standpoint)
            for placement in phase.blocks:
                self.place(placement)

    def select(self, block: str) -> None:
        """Puts a block in hand, unless it is already held. Each new block name gets the next hotbar slot,
        cycling over the 9 slots."""
        if block == self._held:
            return
        slot = self._slots.setdefault(block, len(self._slots) % HOTBAR_SIZE)
        self.mc.select_block(block, slot=slot)
        self._held = block

    def place(self, placement: Placement) -> bool:
        """Places one block, or empties the cell for `"air"`, from where the player is now.

        Returns:
            Whether the cell was changed.
        """
        changed = self._remove(placement) if placement.is_removal else self._place(placement)
        if self.delay_ticks:
            self.mc.step(ticks=self.delay_ticks)
        return changed

    def summary(self) -> str:
        """A one-line report, such as `"198 blocks placed (3 replacing another block), 4 removed"`."""
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
