"""Démo : fait bouger le personnage Minecraft depuis Python via le mod McBot.

Usage :
    1. Lancer Minecraft avec le mod et entrer dans un monde solo (idéalement Superflat).
    2. uv run python scripts/demo_movements.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from mcbot import connect_with_retry

FRAMES_DIR = Path(__file__).resolve().parents[1] / "frames"


def report(label: str, info: dict, image=None) -> None:
    x, y, z = info["pos"]
    line = f"{label:<32} pos=({x:7.2f}, {y:6.2f}, {z:7.2f})  yaw={info['yaw']:7.1f}  pitch={info['pitch']:6.1f}"
    if image is not None:
        FRAMES_DIR.mkdir(exist_ok=True)
        path = FRAMES_DIR / f"{label.split()[0]}.png"
        Image.fromarray(image).save(path)
        line += f"  -> {path.name}"
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    with connect_with_retry(args.host, args.port) as mc:
        mc.wait_for_world()
        mc.config(width=320, height=180)
        print("Connecté ! Début de la démo (garde un œil sur la fenêtre Minecraft).\n")

        image, info = mc.look(pitch=-mc.ping()["pitch"], seconds=0.25, frame=True)  # regard à l'horizontale
        report("01_depart", info, image)

        image, info = mc.forward(seconds=2, frame=True)
        report("02_avancer_2s", info, image)

        image, info = mc.turn(90, seconds=0.5, frame=True)
        report("03_tourner_droite_90", info, image)

        image, info = mc.forward(seconds=2, jump=True, frame=True)
        report("04_avancer_en_sautant", info, image)

        _, info = mc.turn(360, seconds=2)
        report("05_tour_complet", info)

        image, info = mc.look(pitch=-60, seconds=0.75, frame=True)
        report("06_regarder_en_haut", info, image)

        image, info = mc.look(pitch=120, seconds=1, frame=True)
        report("07_regarder_en_bas", info, image)

        _, info = mc.look(pitch=-60, seconds=0.5)
        report("08_regard_horizontal", info)

        _, info = mc.step(ticks=40, left=True)
        report("09_pas_chasse_gauche", info)

        _, info = mc.step(ticks=40, back=True)
        report("10_reculer", info)

        image, info = mc.step(ticks=80, forward=True, yaw=360, frame=True)  # un cercle en 4 s
        report("11_marcher_en_rond", info, image)

        image, info = mc.forward(seconds=2, sprint=True, frame=True)
        report("12_sprint", info, image)

        _, info = mc.jump()
        report("13_saut_sur_place", info)

        image, info = mc.stop(frame=True)
        report("14_arret", info, image)

    print(f"\nDémo terminée. Images enregistrées dans {FRAMES_DIR}")


if __name__ == "__main__":
    try:
        main()
    except ConnectionError:
        print("\nConnexion perdue : Minecraft a été fermé (ou le monde quitté brutalement).")
    except KeyboardInterrupt:
        print("\nDémo interrompue.")
