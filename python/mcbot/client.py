"""TCP client for the McBot mod (Fabric): sends actions to the player and receives its state and images."""

from __future__ import annotations

import json
import math
import socket
import struct
import time
from typing import Any, Callable

import numpy as np

from .world import BlockVolume

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555
TICKS_PER_SECOND = 20

ACTION_KEYS = ("forward", "back", "left", "right", "jump", "sprint", "sneak", "attack", "use")
FACES = ("up", "down", "north", "south", "east", "west")

# Creative flight physics: every tick, horizontal speed is multiplied by 0.91 and vertical speed by 0.6.
# Distance travelled before stopping if everything is released = speed × 1 / (1 - friction).
HORIZONTAL_STOP_FACTOR = 1 / (1 - 0.91)
VERTICAL_STOP_FACTOR = 1 / (1 - 0.6)
MAX_TURN_PER_STEP = 45.0


class McBotError(RuntimeError):
    """Error returned by the mod (for example: no world loaded)."""


class MinecraftClient:
    """Drives the Minecraft player through the McBot mod.

    Each ``step`` holds the requested keys for ``ticks`` ticks (20 ticks = 1 s)
    then returns ``(image, info)``. Keys stay pressed until the next command:
    call ``stop()`` to release everything.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 130.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self.frame_width = 128
        self.frame_height = 128

    # --- Connection ----------------------------------------------------------------------------

    def connect(self) -> "MinecraftClient":
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return self

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "MinecraftClient":
        # Already connected (for example by connect_with_retry): keep that connection, the mod only accepts one.
        return self if self._sock is not None else self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- Protocol commands ---------------------------------------------------------------------

    def ping(self) -> dict[str, Any]:
        return self._request({"type": "ping"})[1]

    def wait_for_world(self, poll_seconds: float = 3.0, log: Callable[[str], None] = print) -> dict[str, Any]:
        """Waits until the player is in a world (so the script can be started from the main menu)."""
        info = self.ping()
        while not info["in_world"]:
            log("  Waiting: join a singleplayer world...")
            time.sleep(poll_seconds)
            info = self.ping()
        return info

    def config(self, width: int, height: int, hide_gui: bool | None = None) -> dict[str, Any]:
        """Sets the size of the returned images (and optionally hides the interface, like F1)."""
        request: dict[str, Any] = {"type": "config", "width": width, "height": height}
        if hide_gui is not None:
            request["hide_gui"] = hide_gui
        info = self._request(request)[1]
        self.frame_width = info["frame_width"]
        self.frame_height = info["frame_height"]
        return info

    def step(self, ticks: int = 1, frame: bool = False, yaw: float = 0.0, pitch: float = 0.0,
             **keys: bool) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Holds the ``keys`` for ``ticks`` ticks and turns the camera by ``yaw``/``pitch`` degrees.

        Possible keys: forward, back, left, right, jump, sprint, sneak, attack, use.
        ``yaw`` > 0 turns right, ``pitch`` > 0 looks down.
        """
        unknown = set(keys) - set(ACTION_KEYS)
        if unknown:
            raise ValueError(f"Unknown keys: {sorted(unknown)} (possible: {ACTION_KEYS})")
        action = {key: bool(keys.get(key, False)) for key in ACTION_KEYS}
        action["yaw"] = float(yaw)
        action["pitch"] = float(pitch)
        return self._request({"type": "step", "ticks": int(ticks), "frame": frame, "action": action})

    # --- Shortcuts -----------------------------------------------------------------------------

    def stop(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Releases all keys."""
        return self.step(ticks=1, frame=frame)

    def forward(self, ticks: int, sprint: bool = False, jump: bool = False,
                frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Walks forward for ``ticks`` ticks (20 ticks = 1 s)."""
        return self.step(ticks, frame=frame, forward=True, sprint=sprint, jump=jump)

    def turn(self, degrees: float, ticks: int = 10,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Turns on the spot (degrees > 0: to the right) over ``ticks`` ticks."""
        return self.step(ticks, frame=frame, yaw=degrees)

    def look(self, pitch: float, ticks: int = 10,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Looks up (pitch < 0) or down (pitch > 0) over ``ticks`` ticks."""
        return self.step(ticks, frame=frame, pitch=pitch)

    def jump(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        return self.step(ticks=10, frame=frame, jump=True)

    # --- Building ------------------------------------------------------------------------------

    def set_game_mode(self, mode: str) -> dict[str, Any]:
        """Changes the game mode (survival, creative, adventure, spectator); singleplayer only, no cheats needed."""
        return self._request({"type": "game_mode", "mode": mode})[1]

    def set_build_mode(self, enabled: bool = True) -> dict[str, Any]:
        """Build mode = creative: unlimited blocks, flying allowed, instant breaking."""
        return self.set_game_mode("creative" if enabled else "survival")

    def set_flying(self, enabled: bool = True) -> dict[str, Any]:
        """Starts/stops flying (build mode required). While flying: jump = up, sneak = down.

        As long as flying is enabled by the script, the mod turns it back on if it stops in mid-air.
        """
        return self._request({"type": "fly", "enabled": enabled})[1]

    def select_block(self, block: str, slot: int | None = None) -> dict[str, Any]:
        """Puts a block in hand, for example ``"oak_planks"`` (``"minecraft:oak_planks"`` is also accepted).

        In build mode, the block is created in hotbar slot ``slot`` (0-8, default: the current slot).
        In survival, it must already be in the hotbar.
        """
        request: dict[str, Any] = {"type": "select_block", "block": block}
        if slot is not None:
            request["slot"] = slot
        return self._request(request)[1]

    def place_block(self, x: float, y: float, z: float, face: str = "up", look: bool = True) -> dict[str, Any]:
        """Places the held block in cell (x, y, z), which must be within reach (5 blocks in creative).

        No neighbouring block needed: you can build in mid-air. ``face`` (the clicked face) orients some blocks:
        ``"up"`` = vertical log / bottom slab, ``"down"`` = top slab, ``"north"``… = lying log.
        Returns ``info`` with ``placed`` (bool) and, on failure, ``reason`` (occupied, out_of_reach,
        no_block_selected, player_in_the_way, rejected) and ``message``.
        """
        if face not in FACES:
            raise ValueError(f"Unknown face: {face!r} (possible: {FACES})")
        return self._request({"type": "place_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "face": face, "look": look})[1]

    def break_block(self, x: float, y: float, z: float, look: bool = True) -> dict[str, Any]:
        """Instantly breaks block (x, y, z) (build mode). Returns ``info`` with ``broken`` (bool)."""
        return self._request({"type": "break_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "look": look})[1]

    def fly_to(self, x: float, y: float, z: float, tolerance: float = 0.75, vertical_tolerance: float = 0.35,
               max_steps: int = 600, face_target: bool = True) -> dict[str, Any]:
        """Flies until the feet are at position (x, y, z), then stops and releases the keys.

        Steering: estimate where the player would stop if everything were released (momentum is kept), and press
        forward/back/left/right/up/down to bring that stopping point onto the target.
        """
        info = self.ping()
        if not info.get("flying"):
            info = self.set_flying(True)

        for _ in range(max_steps):
            px, py, pz = info["pos"]
            vx, vy, vz = info["motion"]
            dx, dy, dz = x - px, y - py, z - pz
            horizontal = math.hypot(dx, dz)
            if horizontal < tolerance and abs(dy) < vertical_tolerance and math.hypot(vx, vz) < 0.1:
                return self.stop()[1]

            turn = 0.0
            if face_target and horizontal > 1.5:
                turn = _wrap_degrees(math.degrees(math.atan2(-dx, dz)) - info["yaw"])
                turn = max(-MAX_TURN_PER_STEP, min(MAX_TURN_PER_STEP, turn))
            yaw = math.radians(info["yaw"] + turn)

            # Gap between the target and the predicted stopping point, in the player's frame of reference.
            ex = dx - vx * HORIZONTAL_STOP_FACTOR
            ez = dz - vz * HORIZONTAL_STOP_FACTOR
            ey = dy - vy * VERTICAL_STOP_FACTOR
            ahead = -ex * math.sin(yaw) + ez * math.cos(yaw)
            left = ex * math.cos(yaw) + ez * math.sin(yaw)
            push, push_y = tolerance / 2, vertical_tolerance / 2

            ticks = 2 if max(horizontal, abs(dy)) > 2 else 1
            _, info = self.step(ticks, yaw=turn,
                                forward=ahead > push, back=ahead < -push,
                                left=left > push, right=left < -push,
                                jump=ey > push_y, sneak=ey < -push_y)

        self.stop()
        raise McBotError(f"fly_to: target ({x:.1f}, {y:.1f}, {z:.1f}) not reached, position {info['pos']}")

    # --- World ---------------------------------------------------------------------------------

    def get_blocks(self, corner1: tuple[float, float, float], corner2: tuple[float, float, float],
                   states: bool = False) -> BlockVolume:
        """Blocks of the box between two corners (included), in world coordinates.

        The box is limited to the world height and to 1,048,576 blocks (3 × 3 full chunks); its chunks must be
        loaded (within render distance). With ``states=True``, the palette contains the full state of the
        blocks (``"oak_log[axis=y]"``) instead of their name only.
        """
        return self._blocks({"min": _block_pos(corner1), "max": _block_pos(corner2)}, states)

    def get_chunk(self, cx: int | None = None, cz: int | None = None, states: bool = False) -> BlockVolume:
        """Whole chunk (16 × world height × 16) at chunk coordinates (cx, cz); by default, the player's chunk."""
        if (cx is None) != (cz is None):
            raise ValueError("Give both cx and cz, or neither")
        if cx is None:
            x, _, z = self.ping()["pos"]
            cx, cz = math.floor(x) // 16, math.floor(z) // 16
        return self._blocks({"chunk": [cx, cz]}, states)

    def get_blocks_around(self, radius: int = 8, states: bool = False) -> BlockVolume:
        """Cube of side 2 × radius + 1 centred on the block of the player's feet (position read at the same tick)."""
        return self._blocks({"radius": radius}, states)

    def _blocks(self, box: dict[str, Any], states: bool) -> BlockVolume:
        ids, info = self._request({"type": "blocks", **box, "states": states})
        return BlockVolume(ids, info["palette"], tuple(info["origin"]))

    # --- Transport -----------------------------------------------------------------------------

    def _request(self, message: dict[str, Any]) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Sends a request; returns the decoded binary data (image or block indices) and the JSON."""
        if self._sock is None:
            raise RuntimeError("Not connected: call connect() first")

        payload = json.dumps(message).encode("utf-8")
        self._sock.sendall(struct.pack(">I", len(payload)) + payload)

        info = json.loads(self._recv_block().decode("utf-8"))
        raw_data = self._recv_block()
        if not info.get("ok", False):
            raise McBotError(info.get("error", "unknown error"))

        data = None
        if raw_data and info.get("payload") == "blocks":
            data = np.frombuffer(raw_data, dtype=">u2").astype(np.uint16).reshape(info["shape"])
        elif raw_data:
            height, width = info["frame_height"], info["frame_width"]
            data = np.frombuffer(raw_data, dtype=np.uint8).reshape(height, width, 3)
        return data, info

    def _recv_block(self) -> bytes:
        (length,) = struct.unpack(">I", self._recv_exact(4))
        return self._recv_exact(length)

    def _recv_exact(self, size: int) -> bytes:
        assert self._sock is not None
        buffer = bytearray()
        while len(buffer) < size:
            chunk = self._sock.recv(size - len(buffer))
            if not chunk:
                raise ConnectionError("Connection closed by Minecraft")
            buffer.extend(chunk)
        return bytes(buffer)


def connect_with_retry(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, retry_seconds: float = 3.0,
                       log: Callable[[str], None] = print) -> MinecraftClient:
    """Connects to the mod, retrying as long as Minecraft is not running."""
    log(f"Connecting to Minecraft on {host}:{port}...")
    while True:
        try:
            return MinecraftClient(host, port).connect()
        except OSError:
            log(f"  Minecraft (with the McBot mod) is not reachable, retrying in {retry_seconds:g} s...")
            time.sleep(retry_seconds)


def _block_pos(point: tuple[float, float, float]) -> list[int]:
    return [math.floor(c) for c in point]


def _wrap_degrees(angle: float) -> float:
    """Wraps an angle into [-180, 180)."""
    return (angle + 180.0) % 360.0 - 180.0
