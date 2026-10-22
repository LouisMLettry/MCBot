"""Démo : lit les blocs autour du joueur et affiche une carte vue de dessus.

Pour chaque colonne autour du joueur, la carte montre le bloc le plus haut de la boîte lue
(nord en haut, est à droite, le joueur est « @ »), puis le nombre de blocs de chaque sorte.

Usage :
    1. Lancer Minecraft avec le mod et entrer dans un monde solo.
    2. uv run python scan_blocks.py [--radius 8]
"""

from __future__ import annotations

import argparse
import math
from collections import Counter

import numpy as np

from mcbot import BlockVolume, connect_with_retry

AIR = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")
SYMBOLS = "#%=+*o~^x&$:;!?"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--radius", type=int, default=8, help="demi-côté du cube lu autour du joueur (défaut : 8)")
    args = parser.parse_args()

    with connect_with_retry(args.host, args.port) as mc:
        info = mc.wait_for_world()
        volume = mc.get_blocks_around(radius=args.radius)
    show(volume, *(math.floor(c) for c in info["pos"]))


def show(volume: BlockVolume, x: int, y: int, z: int) -> None:
    """Affiche la carte vue de dessus et le nombre de blocs ; (x, y, z) = bloc des pieds du joueur."""
    print(f"Joueur en ({x}, {y}, {z}), boîte de {volume.shape} blocs depuis {volume.origin}")
    print(f"Sous les pieds : {volume.block_at(x, y - 1, z)}\n")

    # Bloc le plus haut de chaque colonne (x, z) de la boîte ; None si la colonne est vide.
    solid = ~np.isin(volume.ids, [i for i, name in enumerate(volume.palette) if name in AIR])
    top = volume.ids.shape[1] - 1 - np.argmax(solid[:, ::-1, :], axis=1)
    columns = {(i, k): volume.palette[volume.ids[i, top[i, k], k]] if solid[i, :, k].any() else None
               for i in range(volume.shape[0]) for k in range(volume.shape[2])}

    names = [name for name, _ in Counter(n for n in columns.values() if n).most_common()]
    symbols = {name: SYMBOLS[i] if i < len(SYMBOLS) else "?" for i, name in enumerate(names)}
    player = (x - volume.origin[0], z - volume.origin[2])
    for k in range(volume.shape[2]):
        row = ("@" if (i, k) == player else symbols.get(columns[(i, k)], " ") for i in range(volume.shape[0]))
        print(" ".join(row))

    print("\nLégende (vue de dessus) :")
    for name in names:
        print(f"  {symbols[name]}  {name}")

    print("\nBlocs dans la boîte :")
    counts = np.bincount(volume.ids.ravel(), minlength=len(volume.palette))
    for i in np.argsort(-counts):
        if counts[i] and volume.palette[i] not in AIR:
            print(f"  {counts[i]:6}  {volume.palette[i]}")


if __name__ == "__main__":
    main()
