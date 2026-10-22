"""Teste le client Python contre un faux serveur qui imite le protocole du mod McBot (sans Minecraft)."""

import json
import math
import socket
import struct
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcbot import McBotError, MinecraftClient  # noqa: E402


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError
        data += chunk
    return data


class FakeMod:
    """Répond aux requêtes comme le mod et garde la trace de ce qu'il a reçu."""

    def __init__(self):
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.requests: list[dict] = []
        self.physics = FlightPhysics()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.server.accept()
        with conn:
            try:
                while True:
                    (length,) = struct.unpack(">I", _recv_exact(conn, 4))
                    request = json.loads(_recv_exact(conn, length))
                    self.requests.append(request)
                    info, frame = self._respond(request)
                    body = json.dumps(info).encode()
                    conn.sendall(struct.pack(">I", len(body)) + body + struct.pack(">I", len(frame)) + frame)
            except ConnectionError:
                pass

    def _respond(self, request):
        if request["type"] == "boom":
            return {"ok": False, "error": "Unknown request type: 'boom'"}, b""
        if request["type"] == "step":
            self.physics.run(request["ticks"], request["action"])
        elif request["type"] == "fly":
            self.physics.flying = request["enabled"]
        info = {"ok": True, "in_world": True, "frame_width": 4, "frame_height": 2, **self.physics.state()}
        if request["type"] == "place_block":
            info.update(placed=True, target=[request["x"], request["y"], request["z"]])
        if request["type"] == "blocks":
            # Boîte 2 × 3 × 2 rangée par x, puis y, puis z : le bloc n° i a l'indice de palette i % 3.
            info.update(payload="blocks", origin=request.get("min", [0, -64, 0]), shape=[2, 3, 2],
                        palette=["minecraft:air", "minecraft:stone", "minecraft:oak_log[axis=y]"])
            return info, (np.arange(12) % 3).astype(">u2").tobytes()
        if request.get("frame"):
            return info, bytes(range(4 * 2 * 3))
        return info, b""


class FlightPhysics:
    """Physique simplifiée du vol créatif (accélération 0,05/tick, frottements 0,91 et 0,6)."""

    def __init__(self):
        self.pos = [0.5, -60.0, 0.5]
        self.motion = [0.0, 0.0, 0.0]
        self.yaw = 0.0
        self.flying = False

    def run(self, ticks, action):
        for _ in range(ticks):
            self.yaw += action["yaw"] / ticks
            if not self.flying:
                continue
            ahead = action["forward"] - action["back"]
            left = action["left"] - action["right"]
            norm = max(1.0, math.hypot(ahead, left))
            ahead, left = 0.05 * 0.98 * ahead / norm, 0.05 * 0.98 * left / norm
            yaw = math.radians(self.yaw)
            self.motion[0] += left * math.cos(yaw) - ahead * math.sin(yaw)
            self.motion[2] += ahead * math.cos(yaw) + left * math.sin(yaw)
            self.motion[1] += 0.15 * (action["jump"] - action["sneak"])
            self.pos = [p + v for p, v in zip(self.pos, self.motion)]
            self.motion = [self.motion[0] * 0.91, self.motion[1] * 0.6, self.motion[2] * 0.91]

    def state(self):
        return {"pos": list(self.pos), "motion": list(self.motion), "yaw": (self.yaw + 180) % 360 - 180,
                "pitch": 0.0, "flying": self.flying, "on_ground": not self.flying}


@pytest.fixture
def client():
    fake = FakeMod()
    mc = MinecraftClient(port=fake.port).connect()
    mc.fake = fake
    yield mc
    mc.close()


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


def test_helpers_convert_seconds_to_ticks(client):
    client.forward(seconds=2, sprint=True)
    assert client.fake.requests[-1]["ticks"] == 40
    assert client.fake.requests[-1]["action"]["sprint"] is True
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
    assert client.fake.requests[-1] == {"type": "place_block", "x": -4, "y": 64, "z": 7, "face": "down", "look": True}
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
    # Bloc (i, j, k) relatif à l'origine : n° (i * 3 + j) * 2 + k, d'indice de palette n° % 3.
    assert volume.block_at(10, -60, 4) == "minecraft:stone"          # n° 1
    assert volume.block_at(11, -59, 3) == "minecraft:oak_log[axis=y]"  # n° 8
    assert volume.block_at(10.4, -59, 4.9) == "minecraft:air"        # n° 3
    with pytest.raises(IndexError):
        volume.block_at(12, -60, 3)


def test_block_mask(client):
    volume = client.get_blocks((0, 0, 0), (1, 2, 1))
    assert volume.mask("stone").sum() == 4
    assert volume.mask("minecraft:oak_log").sum() == 4  # toutes les variantes d'état
    assert not volume.mask("dirt").any()


def test_chunk_and_around_requests(client):
    client.get_chunk(2, -3)
    assert client.fake.requests[-1] == {"type": "blocks", "chunk": [2, -3], "states": False}
    client.get_chunk()  # chunk du joueur, en (0.5, -60, 0.5) dans le faux mod
    assert client.fake.requests[-1] == {"type": "blocks", "chunk": [0, 0], "states": False}
    client.get_blocks_around(radius=5, states=True)
    assert client.fake.requests[-1] == {"type": "blocks", "radius": 5, "states": True}
    with pytest.raises(ValueError):
        client.get_chunk(1)
