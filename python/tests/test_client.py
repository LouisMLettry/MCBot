"""Tests the Python client against a fake server imitating the McBot mod protocol (no Minecraft needed)."""

import math

import numpy as np
import pytest

from mcbot import McBotError


def test_ping(client):
    assert client.ping()["in_world"] is True


def test_step_sends_full_action_and_decodes_frame(client):
    image, info = client.step(ticks=10, frame=True, forward=True, yaw=15)
    request = client.fake.requests[-1]
    assert request["type"] == "step"
    assert request["ticks"] == 10
    assert request["action"]["forward"] is True
    assert request["action"]["jump"] is False
    assert request["action"]["yaw"] == 15.0
    assert image.shape == (2, 4, 3) and image.dtype == np.uint8
    assert image[0, 1].tolist() == [3, 4, 5]


def test_helpers_send_ticks(client):
    client.forward(40, sprint=True)
    assert client.fake.requests[-1]["ticks"] == 40
    assert client.fake.requests[-1]["action"]["sprint"] is True
    client.turn(90)
    assert client.fake.requests[-1]["ticks"] == 10 and client.fake.requests[-1]["action"]["yaw"] == 90.0
    client.look(-30, ticks=5)
    assert client.fake.requests[-1]["ticks"] == 5 and client.fake.requests[-1]["action"]["pitch"] == -30.0
    image, _ = client.stop()
    assert image is None
    assert not any(v for k, v in client.fake.requests[-1]["action"].items() if k not in ("yaw", "pitch"))


def test_unknown_key_is_rejected(client):
    with pytest.raises(ValueError):
        client.step(fly=True)


def test_mod_error_is_raised(client):
    with pytest.raises(McBotError, match="Unknown request type"):
        client._request({"type": "boom"})


def test_build_requests(client):
    client.set_build_mode(True)
    assert client.fake.requests[-1] == {"type": "game_mode", "mode": "creative"}
    client.select_block("oak_planks", slot=2)
    assert client.fake.requests[-1] == {"type": "select_block", "block": "oak_planks", "slot": 2}
    info = client.place_block(-3.2, 64, 7.9, face="down")
    assert client.fake.requests[-1] == {"type": "place_block", "x": -4, "y": 64, "z": 7, "face": "down", "look": True,
                                         "replace": False}
    assert info["placed"] is True
    with pytest.raises(ValueError):
        client.place_block(0, 0, 0, face="top")


@pytest.mark.parametrize("target", [(12.5, -55.0, -8.5), (-20.0, -62.0, 3.0), (1.0, -60.0, 0.5)])
def test_fly_to_reaches_target(client, target):
    info = client.fly_to(*target)
    assert client.fake.physics.flying
    x, y, z = info["pos"]
    assert math.hypot(x - target[0], z - target[2]) < 0.75
    assert abs(y - target[1]) < 0.35
    assert not any(client.fake.requests[-1]["action"][k] for k in ("forward", "back", "left", "right", "jump"))


def test_get_blocks_decodes_volume(client):
    volume = client.get_blocks((10.7, -60, 3), (11, -58, 4.2))
    assert client.fake.requests[-1] == {"type": "blocks", "min": [10, -60, 3], "max": [11, -58, 4], "states": False}
    assert volume.shape == (2, 3, 2) and volume.ids.dtype == np.uint16
    assert volume.origin == (10, -60, 3)
    # Block (i, j, k) relative to the origin: no. (i * 3 + j) * 2 + k, with palette index no. % 3.
    assert volume.block_at(10, -60, 4) == "stone"          # no. 1
    assert volume.block_at(11, -59, 3) == "oak_log[axis=y]"  # no. 8
    assert volume.block_at(10.4, -59, 4.9) == "air"        # no. 3
    with pytest.raises(IndexError):
        volume.block_at(12, -60, 3)


def test_block_mask(client):
    volume = client.get_blocks((0, 0, 0), (1, 2, 1))
    assert volume.mask("stone").sum() == 4
    assert volume.mask("minecraft:oak_log").sum() == 4  # prefix accepted, every state variant
    assert not volume.mask("dirt").any()


def test_chunk_and_around_requests(client):
    client.get_chunk(2, -3)
    assert client.fake.requests[-1] == {"type": "blocks", "chunk": [2, -3], "states": False}
    client.get_chunk()  # player's chunk, at (0.5, -60, 0.5) in the fake mod
    assert client.fake.requests[-1] == {"type": "blocks", "chunk": [0, 0], "states": False}
    client.get_blocks_around(radius=5, states=True)
    assert client.fake.requests[-1] == {"type": "blocks", "radius": 5, "states": True}
    with pytest.raises(ValueError):
        client.get_chunk(1)


def test_with_keeps_existing_connection(client):
    sock = client._sock
    with client as mc:  # like `with connect_with_retry(...) as mc:`
        assert mc is client and mc._sock is sock
        assert mc.ping()["in_world"] is True
    assert client._sock is None
