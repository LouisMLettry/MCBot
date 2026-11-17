"""Tests the Python client against a fake server imitating the McBot mod protocol (no Minecraft needed)."""

import math

import numpy as np
import pytest

from mcbot import Entity, McBotError


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


def test_set_block_and_batches(client, monkeypatch):
    info = client.set_block(1.5, -60, -2.2, "minecraft:oak_stairs[facing=east]")
    assert client.fake.requests[-1] == {"type": "set_blocks", "blocks": [[1, -60, -3, "minecraft:oak_stairs[facing=east]"]]}
    assert info["block"] == "oak_stairs[facing=east]" and "blocks" not in info
    monkeypatch.setattr("mcbot.client.SET_BLOCKS_BATCH", 2)
    info = client.set_blocks(((x, -60, 0), "stone") for x in range(5))
    assert [len(r["blocks"]) for r in client.fake.requests[-3:]] == [2, 2, 1]
    assert info["blocks"] == ["stone"] * 5 and client.fake.world[(4, -60, 0)] == "stone"
    with pytest.raises(ValueError):
        client.set_blocks([])


def test_set_blocks_reports_blocks_the_game_changed(client, monkeypatch):
    assert client.set_block(0, -60, 0, "stone")["changed"] == []
    assert client.set_block(0, -59, 0, "sand")["changed"] == [[0, -59, 0, "air"]]
    monkeypatch.setattr("mcbot.client.SET_BLOCKS_BATCH", 2)
    info = client.set_blocks([((0, -60, 1), "sand"), ((1, -60, 1), "stone"), ((2, -60, 1), "sand")])
    assert info["changed"] == [[0, -60, 1, "air"], [2, -60, 1, "air"]]  # gathered from both batches


def test_get_entities_request_and_decoding(client):
    zombie, item = client.get_entities(radius=16, types="zombie", visibility=True)
    assert client.fake.requests[-1] == {"type": "entities", "radius": 16, "types": ["zombie"], "limit": 256,
                                         "visibility": True}
    assert isinstance(zombie, Entity) and zombie.is_hostile and zombie.health == 20.0
    assert zombie.pos == (3.5, -60.0, 0.5) and zombie.line_of_sight is True and zombie.in_view is False
    assert zombie.box == ((3.2, -60.0, 0.2), (3.8, -58.05, 0.8))
    assert zombie.distance_to(0.5, -60, 0.5) == 3.0
    assert item.item == "oak_log" and item.count == 3
    assert item.health is None and item.line_of_sight is None and not item.is_hostile


def test_get_entities_in_box(client):
    client.get_entities_in((10.7, -60, 3), (-2, -55.5, 4.2), types=["minecraft:item", "cow"])
    assert client.fake.requests[-1] == {"type": "entities", "min": [10, -60, 3], "max": [-2, -56, 4],
                                         "types": ["minecraft:item", "cow"], "limit": 256, "visibility": False}


def test_step_with_entities(client):
    _, info = client.step(frame=True, entities=True)
    assert client.fake.requests[-1]["entities"] == {}
    assert [e.type for e in info["entities"]] == ["zombie", "item"]
    _, info = client.step(entities={"radius": 8, "visibility": True})
    assert client.fake.requests[-1]["entities"] == {"radius": 8, "visibility": True}
    _, info = client.step()
    assert "entities" not in client.fake.requests[-1] and "entities" not in info
    with pytest.raises(ValueError, match="Unknown entity options"):
        client.step(entities={"range": 8})
