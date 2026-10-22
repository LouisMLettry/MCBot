"""Fake McBot mod shared by the tests: speaks the protocol, simulates flight and remembers placed blocks."""

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

from mcbot import MinecraftClient  # noqa: E402


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError
        data += chunk
    return data


class FakeMod:
    """Answers requests like the mod and records what it received."""

    def __init__(self):
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.requests: list[dict] = []
        self.physics = FlightPhysics()
        self.world: dict[tuple[int, int, int], str] = {}  # non-empty cells
        self.held: str | None = None
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
        if request["type"] == "select_block":
            self.held = request["block"].removeprefix("minecraft:")
        if request["type"] == "place_block":
            info.update(self._place(request))
        if request["type"] == "break_block":
            info.update(self._break(request))
        if request["type"] == "set_blocks":
            states = [state.removeprefix("minecraft:") for *_, state in request["blocks"]]
            for (x, y, z, _), state in zip(request["blocks"], states):
                if state == "air":
                    self.world.pop((x, y, z), None)
                else:
                    self.world[(x, y, z)] = state
            info.update(blocks=states)
        if request["type"] == "blocks":
            # 2 × 3 × 2 box ordered by x, then y, then z: block no. i has palette index i % 3.
            info.update(payload="blocks", origin=request.get("min", [0, -64, 0]), shape=[2, 3, 2],
                        palette=["air", "stone", "oak_log[axis=y]"])
            return info, (np.arange(12) % 3).astype(">u2").tobytes()
        if request.get("frame"):
            return info, bytes(range(4 * 2 * 3))
        return info, b""

    def _place(self, request):
        """Same rules as the mod: same block -> already_there, other block -> occupied unless replace."""
        pos = (request["x"], request["y"], request["z"])
        result = {"placed": False, "target": list(pos)}
        existing = self.world.get(pos)
        if existing == self.held:
            return {**result, "reason": "already_there", "block": existing}
        if existing and not request.get("replace"):
            return {**result, "reason": "occupied", "block": existing, "message": f"Position already occupied by {existing}"}
        self.world[pos] = self.held
        return {**result, "placed": True, "block": self.held, **({"replaced": existing} if existing else {})}

    def _break(self, request):
        pos = (request["x"], request["y"], request["z"])
        existing = self.world.pop(pos, None)
        if existing is None:
            return {"broken": False, "target": list(pos), "reason": "empty", "message": "There is no block here"}
        return {"broken": True, "target": list(pos), "block": existing}


class FlightPhysics:
    """Simplified creative flight physics (acceleration 0.05/tick, friction 0.91 and 0.6)."""

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
