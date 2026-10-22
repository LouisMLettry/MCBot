"""Exemple de construction automatique : une petite maison posée au sol, devant le joueur.

Le script passe en mode construction (créatif), s'envole, pose le sol, les murs (avec fenêtres, porte et
torche) puis un toit en pyramide, et enfin se recule pour prendre une photo de la maison (frames/maison.png).

Usage :
    1. Lancer Minecraft avec le mod, entrer dans un monde solo (idéalement Superflat) et se tenir au sol,
       face à un espace libre d'environ 10 × 10 blocs.
    2. uv run python scripts/build_house.py
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from mcbot import Builder, Phase, Placement, connect_with_retry

FRAMES_DIR = Path(__file__).resolve().parents[1] / "frames"

SIZE = 7  # côté de la maison, en blocs
WALL_HEIGHT = 3
DISTANCE = 3  # distance entre le joueur et la façade

FLOOR = "stone_bricks"
WALL = "oak_planks"
PILLAR = "oak_log"
WINDOW = "glass_pane"
DOOR = "oak_door"
LIGHT = "torch"
ROOF = "dark_oak_planks"

Local = tuple[int, int, int]


# --- Plan de la maison, en coordonnées locales --------------------------------------------------
# x : de gauche à droite (vu du joueur), z : de la façade vers le fond, y : 0 = sol de la maison.

def is_window(x: int, z: int) -> bool:
    n, mid = SIZE - 1, (SIZE - 1) // 2
    if z == 0:
        return x in (1, n - 1)  # façade : une fenêtre de chaque côté de la porte
    if z == n:
        return abs(x - mid) <= 1  # fond : baie de 3 blocs
    return x in (0, n) and abs(z - mid) <= 1  # côtés : baie de 3 blocs


def perimeter() -> list[tuple[int, int]]:
    """Cases du tour de la maison, dans l'ordre (le constructeur fait le tour du mur)."""
    n = SIZE - 1
    return ([(x, 0) for x in range(SIZE)] + [(n, z) for z in range(1, SIZE)]
            + [(x, n) for x in range(n - 1, -1, -1)] + [(0, z) for z in range(n - 1, 0, -1)])


def house_plan() -> list[tuple[str, tuple[int, float, int], list[tuple[Local, str]]]]:
    """Phases de construction : (nom, point de vol (case x, hauteur des pieds, case z), blocs)."""
    n, mid = SIZE - 1, (SIZE - 1) // 2
    inside = (mid, 2.0, mid)  # au centre, en vol au-dessus du sol : tout le rez-de-chaussée est à portée

    floor = [((x, 0, z), FLOOR) for z in range(SIZE) for x in range(SIZE)]

    walls = []
    for y in range(1, WALL_HEIGHT + 1):
        for x, z in perimeter():
            if (x, z) == (mid, 0) and y <= 2:
                continue  # ouverture de la porte
            if x in (0, n) and z in (0, n):
                block = PILLAR
            elif y == 2 and is_window(x, z):
                block = WINDOW
            else:
                block = WALL
            walls.append(((x, y, z), block))
    details = [((mid, 1, 0), DOOR), ((mid, 1, n - 1), LIGHT)]

    phases = [("Sol", inside, floor), ("Murs, porte et torche", inside, walls + details)]
    for i in range(mid + 1):  # toit en pyramide : 7×7, 5×5, 3×3, 1×1
        y = WALL_HEIGHT + 1 + i
        layer = [((x, y, z), ROOF) for z in range(i, SIZE - i) for x in range(i, SIZE - i)]
        phases.append((f"Toit, niveau {i + 1}", (mid, y + 1.5, mid), layer))
    return phases


# --- Passage des coordonnées locales aux coordonnées du monde ------------------------------------

@dataclass(frozen=True)
class Frame:
    """Repère de la maison : origine (coin avant gauche du sol), direction « devant » et « droite »."""

    origin: tuple[int, int, int]
    forward: tuple[int, int]
    right: tuple[int, int]

    def block(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        ox, oy, oz = self.origin
        return (ox + self.right[0] * x + self.forward[0] * z, oy + y,
                oz + self.right[1] * x + self.forward[1] * z)

    def point(self, x: int, feet_y: float, z: int) -> tuple[float, float, float]:
        """Centre de la case (x, z) à la hauteur de pieds feet_y."""
        bx, by, bz = self.block(x, 0, z)
        return bx + 0.5, by + feet_y, bz + 0.5

    @property
    def yaw(self) -> float:
        """Orientation (yaw Minecraft) pour regarder vers le fond de la maison."""
        return math.degrees(math.atan2(-self.forward[0], self.forward[1]))


def cardinal_direction(yaw: float) -> tuple[int, int]:
    """Direction (dx, dz) la plus proche du regard. Minecraft : yaw 0 = sud (+z), 90 = ouest (-x)."""
    angle = math.radians(round(yaw / 90.0) * 90.0)
    return round(-math.sin(angle)), round(math.cos(angle))


def frame_in_front_of(pos: tuple[float, float, float], yaw: float) -> Frame:
    forward = cardinal_direction(yaw)
    right = (-forward[1], forward[0])
    px, py, pz = (math.floor(c) for c in pos)
    half = SIZE // 2
    origin = (px + forward[0] * DISTANCE - right[0] * half, py,
              pz + forward[1] * DISTANCE - right[1] * half)
    return Frame(origin, forward, right)


def house_phases(frame: Frame) -> list[Phase]:
    return [Phase(name, frame.point(*standpoint), [Placement(frame.block(*local), block) for local, block in blocks])
            for name, standpoint, blocks in house_plan()]


# --- Script --------------------------------------------------------------------------------------

def land(mc, max_ticks: int = 200) -> dict:
    """Coupe le vol et attend d'être posé au sol."""
    info = mc.set_flying(False)
    for _ in range(max_ticks // 5):
        if info["on_ground"]:
            break
        _, info = mc.step(ticks=5)
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--delay", type=int, default=2, help="ticks d'attente après chaque bloc (défaut : 2)")
    args = parser.parse_args()

    with connect_with_retry(args.host, args.port) as mc:
        mc.wait_for_world()
        mc.config(width=640, height=360)

        info = mc.set_build_mode(True)
        print(f"Mode de jeu : {info['game_mode']}")
        info = land(mc)  # le sol de la maison est calé sur la hauteur des pieds du joueur
        if not info["on_ground"]:
            raise SystemExit("Le joueur doit être au sol pour placer la maison.")

        frame = frame_in_front_of(info["pos"], info["yaw"])
        phases = house_phases(frame)
        total = sum(len(phase.blocks) for phase in phases)
        print(f"Maison de {SIZE}×{SIZE} : {total} blocs, coin avant gauche en {frame.origin}\n")

        mc.set_flying(True)
        builder = Builder(mc, delay_ticks=args.delay)
        builder.build(phases)
        print(f"\nConstruction terminée : {builder.summary()}")

        # On sort par le haut, on se place devant la façade et on prend une photo.
        mid = SIZE // 2
        mc.fly_to(*frame.point(mid, WALL_HEIGHT + 6, -9))
        mc.fly_to(*frame.point(mid, 3, -9))
        info = land(mc)
        yaw_delta = (frame.yaw - info["yaw"] + 180) % 360 - 180
        mc.step(ticks=10, yaw=yaw_delta, pitch=-10 - info["pitch"])

        mc.config(width=640, height=360, hide_gui=True)
        image, _ = mc.step(ticks=2, frame=True)
        mc.config(width=640, height=360, hide_gui=False)
        FRAMES_DIR.mkdir(exist_ok=True)
        Image.fromarray(image).save(FRAMES_DIR / "maison.png")
        print(f"Photo enregistrée : {FRAMES_DIR / 'maison.png'}")


if __name__ == "__main__":
    try:
        main()
    except ConnectionError:
        print("\nConnexion perdue : Minecraft a été fermé (ou le monde quitté brutalement).")
    except KeyboardInterrupt:
        print("\nConstruction interrompue.")
