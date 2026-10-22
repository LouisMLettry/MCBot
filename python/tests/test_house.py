"""Vérifie le plan de la maison : chaque bloc est à portée depuis son point de vol, sans gêner le joueur."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_house  # noqa: E402

REACH = 5.0  # portée en créatif
SAFETY = 0.5  # marge par rapport à la portée
EYE_HEIGHT = 1.62
PLAYER_HALF_WIDTH, PLAYER_HEIGHT = 0.3, 1.8
FLY_TOLERANCE, FLY_VERTICAL_TOLERANCE = 0.75, 0.35  # valeurs par défaut de fly_to


def distance_to_block(point, block):
    """Distance entre un point et le cube d'un bloc (comme Minecraft pour la portée)."""
    return math.sqrt(sum(max(b - p, 0, p - (b + 1)) ** 2 for p, b in zip(point, block)))


def player_box(feet, horizontal_margin=0.0, vertical_margin=0.0):
    x, y, z = feet
    w = PLAYER_HALF_WIDTH + horizontal_margin
    return (x - w, y - vertical_margin, z - w), (x + w, y + PLAYER_HEIGHT + vertical_margin, z + w)


def intersects(box, block):
    (x0, y0, z0), (x1, y1, z1) = box
    bx, by, bz = block
    return x0 < bx + 1 and x1 > bx and y0 < by + 1 and y1 > by and z0 < bz + 1 and z1 > bz


def local_phases():
    """Phases avec un point de vol au centre de la case, en coordonnées locales."""
    return [(name, (sx + 0.5, sy, sz + 0.5), blocks) for name, (sx, sy, sz), blocks in build_house.house_plan()]


def test_block_count_and_no_duplicates():
    positions = [pos for _, _, blocks in local_phases() for pos, _ in blocks]
    assert len(positions) == len(set(positions))
    assert len(positions) == 49 + (3 * 24 - 2) + 2 + (49 + 25 + 9 + 1)


def test_door_opening():
    blocks = {pos: block for _, _, phase_blocks in local_phases() for pos, block in phase_blocks}
    assert blocks[(3, 1, 0)] == build_house.DOOR
    assert (3, 2, 0) not in blocks  # moitié haute de la porte, posée automatiquement
    assert blocks[(3, 3, 0)] == build_house.WALL  # linteau


def test_every_block_is_within_reach_from_its_standpoint():
    for name, feet, blocks in local_phases():
        eye = (feet[0], feet[1] + EYE_HEIGHT, feet[2])
        for pos, block in blocks:
            assert distance_to_block(eye, pos) <= REACH - SAFETY, (name, pos, block)


def test_player_never_stands_in_a_block():
    placed = set()
    for name, feet, blocks in local_phases():
        box = player_box(feet, FLY_TOLERANCE, FLY_VERTICAL_TOLERANCE)
        for pos, _ in blocks:
            assert not intersects(box, pos), (name, pos)
        for pos in placed:
            assert not intersects(box, pos), (name, "déjà posé", pos)
        placed.update(pos for pos, _ in blocks)


@pytest.mark.parametrize("yaw", [0, 90, 180, -90, 30, -150])
def test_house_is_built_in_front_of_the_player(yaw):
    player = (10.4, -60.0, -3.7)
    frame = build_house.frame_in_front_of(player, yaw)
    forward = build_house.cardinal_direction(yaw)

    px, pz = math.floor(player[0]), math.floor(player[2])

    def ahead(block):  # en blocs, depuis le bloc du joueur, dans la direction du regard
        return (block[0] - px) * forward[0] + (block[2] - pz) * forward[1]

    def sideways(block):
        return (block[0] - px) * forward[1] - (block[2] - pz) * forward[0]

    door = frame.block(3, 1, 0)
    back = frame.block(3, 1, 6)
    assert ahead(door) == build_house.DISTANCE
    assert sideways(door) == 0  # porte dans l'axe du regard
    assert ahead(back) == build_house.DISTANCE + 6
    assert frame.block(3, 0, 0)[1] == -60  # le sol de la maison est au niveau des pieds
    assert door[1] == -59
    look = math.radians(frame.yaw)
    assert (round(-math.sin(look)), round(math.cos(look))) == forward
