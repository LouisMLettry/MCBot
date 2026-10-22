"""Construction automatique : pose une liste de blocs, phase par phase, en volant à portée de chaque phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .client import MinecraftClient

HOTBAR_SIZE = 9


@dataclass(frozen=True)
class Placement:
    """Un bloc à poser : position (coordonnées monde), identifiant du bloc et face cliquée."""

    pos: tuple[int, int, int]
    block: str
    face: str = "up"


@dataclass
class Phase:
    """Groupe de blocs posés depuis un même point (position des pieds) d'où ils sont tous à portée."""

    name: str
    standpoint: tuple[float, float, float]
    blocks: list[Placement] = field(default_factory=list)


class Builder:
    """Enchaîne les phases : vole jusqu'au point de chaque phase puis pose ses blocs un par un."""

    def __init__(self, mc: MinecraftClient, delay_ticks: int = 2, log: Callable[[str], None] = print):
        self.mc = mc
        self.delay_ticks = delay_ticks
        self.log = log
        self.placed = 0
        self.already_there = 0
        self.failures: list[tuple[Placement, str]] = []
        self._slots: dict[str, int] = {}
        self._held: str | None = None

    def build(self, phases: list[Phase]) -> None:
        for phase in phases:
            self.log(f"-- {phase.name} : {len(phase.blocks)} blocs")
            self.mc.fly_to(*phase.standpoint)
            for placement in phase.blocks:
                self.place(placement)

    def select(self, block: str) -> None:
        """Met le bloc en main ; chaque nouveau bloc prend l'emplacement suivant de la barre d'accès rapide."""
        if block == self._held:
            return
        slot = self._slots.setdefault(block, len(self._slots) % HOTBAR_SIZE)
        self.mc.select_block(block, slot=slot)
        self._held = block

    def place(self, placement: Placement) -> bool:
        self.select(placement.block)
        info = self.mc.place_block(*placement.pos, face=placement.face)
        if info["placed"]:
            self.placed += 1
        elif info.get("reason") == "occupied":
            self.already_there += 1
        else:
            self.failures.append((placement, info.get("message", info.get("reason", "?"))))
            self.log(f"   ! {placement.block} en {placement.pos} : {info.get('message')}")
        if self.delay_ticks:
            self.mc.step(ticks=self.delay_ticks)
        return bool(info["placed"])

    def summary(self) -> str:
        text = f"{self.placed} blocs posés"
        if self.already_there:
            text += f", {self.already_there} cases déjà occupées"
        if self.failures:
            text += f", {len(self.failures)} échecs"
        return text
