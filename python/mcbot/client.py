"""TCP client for the McBot mod (Fabric): sends actions to the player and receives its state and images."""

from __future__ import annotations

import json
import math
import socket
import struct
import time
from typing import Any, Callable, Iterable

import numpy as np

from .entities import Entity
from .world import BlockVolume

DEFAULT_HOST = "127.0.0.1"
"""Address of the mod. It only listens on the local machine."""
DEFAULT_PORT = 5555
"""Port of the mod. Can be changed by starting the game with `-Dmcbot.port=XXXX`."""
TICKS_PER_SECOND = 20
"""Game ticks per second. Every duration in the game is given in ticks."""

ACTION_KEYS = ("forward", "back", "left", "right", "jump", "sprint", "sneak", "attack", "use")
"""Keys that [`step`][mcbot.MinecraftClient.step] can hold."""
FACES = ("up", "down", "north", "south", "east", "west")
"""Faces accepted by [`place_block`][mcbot.MinecraftClient.place_block]."""
SET_BLOCKS_BATCH = 4096
"""Blocks per request sent by [`set_blocks`][mcbot.MinecraftClient.set_blocks] (the mod accepts up to 1 MB)."""
ENTITY_QUERY_KEYS = ("radius", "min", "max", "types", "limit", "visibility")
"""Options accepted in the `entities` argument of [`step`][mcbot.MinecraftClient.step]."""

# Creative flight physics: every tick, horizontal speed is multiplied by 0.91 and vertical speed by 0.6.
# Distance travelled before stopping if everything is released = speed × 1 / (1 - friction).
HORIZONTAL_STOP_FACTOR = 1 / (1 - 0.91)
VERTICAL_STOP_FACTOR = 1 / (1 - 0.6)
MAX_TURN_PER_STEP = 45.0


class McBotError(RuntimeError):
    """The mod refused a command.

    Raised for invalid requests and impossible situations: no world loaded (every command but
    [`ping`][mcbot.MinecraftClient.ping]), unknown block, chunk not loaded, box too large, timeout while waiting for
    the game… Actions that can normally fail in the game, such as placing
    a block where another one already is, are not errors: they return a result with a `reason` instead.
    """


class MinecraftClient:
    """Drives the Minecraft player through the McBot mod.

    The mod accepts one connection at a time. Each command is answered with the player's state, the `info`
    dictionary (see [The info dictionary][info-dictionary]), read at the tick the command finished.

    Keys held by [`step`][mcbot.MinecraftClient.step] stay pressed until the next command:
    call [`stop`][mcbot.MinecraftClient.stop] to release them. Closing the connection releases them too.

    Args:
        host: Address of the mod.
        port: Port of the mod.
        timeout: Network timeout in seconds, for connecting and for each answer. The longest command, a 1-minute
            step, fits in the default.

    Example:
        ```python
        from mcbot import MinecraftClient

        with MinecraftClient() as mc:
            image, info = mc.forward(20, frame=True)
            print(info["pos"])
        ```

    Attributes:
        frame_width: Width of the images returned, in pixels, as last set by [`config`][mcbot.MinecraftClient.config].
        frame_height: Height of the images returned, in pixels.
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
        """Opens the connection to the mod.

        Returns:
            The client itself, so that `mc = MinecraftClient().connect()` works.

        Raises:
            OSError: Minecraft is not running, or the mod is not loaded. See also
                [`connect_with_retry`][mcbot.connect_with_retry].
        """
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return self

    def close(self) -> None:
        """Closes the connection. The mod then releases all keys."""
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
        """Reads the player's state without doing anything.

        Returns:
            The `info` dictionary.
        """
        return self._request({"type": "ping"})[1]

    def wait_for_world(self, poll_seconds: float = 3.0, log: Callable[[str], None] = print) -> dict[str, Any]:
        """Waits until the player is in a world, so that a script can be started from the main menu.

        Args:
            poll_seconds: Time between two checks, in seconds.
            log: Called with a message at each check while waiting.

        Returns:
            The `info` dictionary, once a world is loaded.
        """
        info = self.ping()
        while not info["in_world"]:
            log("  Waiting: join a singleplayer world...")
            time.sleep(poll_seconds)
            info = self.ping()
        return info

    def config(self, width: int, height: int, hide_gui: bool | None = None) -> dict[str, Any]:
        """Sets the size of the images returned and, optionally, hides the interface.

        The whole game window is shrunk (or stretched) to this size by averaging pixels.

        Args:
            width: Image width in pixels, 16 to 1024.
            height: Image height in pixels, 16 to 1024. Keep the window's aspect ratio to avoid distorted images.
            hide_gui: `True` hides the interface (hotbar, crosshair, hand) like F1; `False` shows it again;
                `None` leaves it as it is.

        Returns:
            The `info` dictionary, with the new `frame_width` and `frame_height`.
        """
        request: dict[str, Any] = {"type": "config", "width": width, "height": height}
        if hide_gui is not None:
            request["hide_gui"] = hide_gui
        info = self._request(request)[1]
        self.frame_width = info["frame_width"]
        self.frame_height = info["frame_height"]
        return info

    def step(self, ticks: int = 1, frame: bool = False, yaw: float = 0.0, pitch: float = 0.0,
             entities: bool | dict[str, Any] = False, **keys: bool) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Holds keys for some ticks while turning the camera, then returns an image and the player's state.

        This is the basic command: everything that moves the player goes through it. Keys stay pressed after the
        step, until the next command changes them, so that consecutive steps are smooth.

        Args:
            ticks: How long to hold the keys, 0 to 1200 (1 minute). With 0, only the rotation is applied, at once.
            frame: Whether to return an image of the game, taken at the end of the step.
            yaw: Degrees to turn horizontally during the step, spread evenly over the ticks. Positive turns right.
            pitch: Degrees to turn vertically. Positive looks down. The pitch stays between -90 and 90.
            entities: `True`, or a dict of options as for [`get_entities`][mcbot.MinecraftClient.get_entities]
                (`radius`, `min`, `max`, `types`, `limit`, `visibility`), to list the entities around the player
                in `info["entities"]`. With `frame=True`, they are listed as the image shows them.
            **keys: Keys to hold, as `name=True`: `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`,
                `attack`, `use`. Keys not given are released.

        Returns:
            A pair `(image, info)`. `image` is a numpy array of shape `(frame_height, frame_width, 3)`, `uint8`
            RGB, top row first, or `None` without `frame=True`. `info` is the player's state, plus `entities`
            (a list of [`Entity`][mcbot.Entity]) if requested.

        Raises:
            ValueError: Unknown key name.

        Note:
            The image is the last frame the game drew, part-way between two ticks: the state in `info` can be up to
            one tick ahead of it. With `ticks=0`, no frame is drawn during the step, so the image comes from before
            it. See [When an image is taken][image-timing].

        Example:
            ```python
            # Walk forward and jump for one second, turning 45° left, with a picture at the end
            image, info = mc.step(ticks=20, frame=True, forward=True, jump=True, yaw=-45)
            ```
        """
        unknown = set(keys) - set(ACTION_KEYS)
        if unknown:
            raise ValueError(f"Unknown keys: {sorted(unknown)} (possible: {ACTION_KEYS})")
        action = {key: bool(keys.get(key, False)) for key in ACTION_KEYS}
        action["yaw"] = float(yaw)
        action["pitch"] = float(pitch)
        request: dict[str, Any] = {"type": "step", "ticks": int(ticks), "frame": frame, "action": action}
        if entities:
            request["entities"] = _entity_query({} if entities is True else entities)
        image, info = self._request(request)
        if "entities" in info:
            info["entities"] = [Entity.from_json(entity) for entity in info["entities"]]
        return image, info

    # --- Shortcuts -----------------------------------------------------------------------------

    def stop(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Releases all keys (takes one tick).

        Args:
            frame: Whether to return an image.

        Returns:
            `(image, info)`, as for [`step`][mcbot.MinecraftClient.step].
        """
        return self.step(ticks=1, frame=frame)

    def forward(self, ticks: int, sprint: bool = False, jump: bool = False,
                frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Walks forward.

        Args:
            ticks: How long to walk (20 ticks = 1 second).
            sprint: Whether to sprint.
            jump: Whether to hold jump at the same time.
            frame: Whether to return an image.

        Returns:
            `(image, info)`, as for [`step`][mcbot.MinecraftClient.step].
        """
        return self.step(ticks, frame=frame, forward=True, sprint=sprint, jump=jump)

    def turn(self, degrees: float, ticks: int = 10,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Turns on the spot.

        Args:
            degrees: How far to turn. Positive turns right.
            ticks: How long the turn takes.
            frame: Whether to return an image.

        Returns:
            `(image, info)`, as for [`step`][mcbot.MinecraftClient.step].
        """
        return self.step(ticks, frame=frame, yaw=degrees)

    def look(self, pitch: float, ticks: int = 10,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Looks up or down.

        Args:
            pitch: How far to tilt the view, in degrees. Positive looks down, negative looks up.
            ticks: How long the movement takes.
            frame: Whether to return an image.

        Returns:
            `(image, info)`, as for [`step`][mcbot.MinecraftClient.step].
        """
        return self.step(ticks, frame=frame, pitch=pitch)

    def jump(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Jumps once (holds jump for 10 ticks).

        Args:
            frame: Whether to return an image.

        Returns:
            `(image, info)`, as for [`step`][mcbot.MinecraftClient.step].
        """
        return self.step(ticks=10, frame=frame, jump=True)

    # --- Building ------------------------------------------------------------------------------

    def set_game_mode(self, mode: str) -> dict[str, Any]:
        """Changes the game mode. Works in a singleplayer world, without cheats.

        Args:
            mode: `"survival"`, `"creative"`, `"adventure"` or `"spectator"`.

        Returns:
            The `info` dictionary, once the new mode is applied.

        Raises:
            McBotError: Unknown mode, not in a singleplayer world, or not applied within 5 seconds.
        """
        return self._request({"type": "game_mode", "mode": mode})[1]

    def set_build_mode(self, enabled: bool = True) -> dict[str, Any]:
        """Switches to creative ("build mode": unlimited blocks, flying, instant breaking) or back to survival.

        Args:
            enabled: `True` for creative, `False` for survival.

        Returns:
            The `info` dictionary, once the new mode is applied.
        """
        return self.set_game_mode("creative" if enabled else "survival")

    def set_flying(self, enabled: bool = True) -> dict[str, Any]:
        """Starts or stops flying. Needs creative mode.

        While flying, `jump` goes up and `sneak` goes down. Started on the ground, the player hops up about one
        block. As long as flying is enabled by the script, the mod turns it back on if the game stops it.

        Args:
            enabled: Whether to fly.

        Returns:
            The `info` dictionary.

        Raises:
            McBotError: The player is not allowed to fly (not in creative).
        """
        return self._request({"type": "fly", "enabled": enabled})[1]

    def select_block(self, block: str, slot: int | None = None) -> dict[str, Any]:
        """Puts a block in the player's hand.

        Args:
            block: Block name, such as `"oak_planks"` (`"minecraft:oak_planks"` is also accepted).
            slot: Hotbar slot, 0 to 8. In creative, the block is created in this slot (default: the current one).
                In survival, the block must already be in the hotbar and this is ignored.

        Returns:
            The `info` dictionary, with `slot`, `item` and `is_block`.

        Raises:
            McBotError: Unknown block, or (in survival) not in the hotbar.
        """
        request: dict[str, Any] = {"type": "select_block", "block": block}
        if slot is not None:
            request["slot"] = slot
        return self._request(request)[1]

    def place_block(self, x: float, y: float, z: float, face: str = "up", look: bool = True,
                    replace: bool = False) -> dict[str, Any]:
        """Places the block in hand, like a player would.

        The cell must be within reach (about 5 blocks from the eyes in creative). No neighbouring block is needed:
        you can build in mid-air. To write blocks anywhere, in an exact state, use
        [`set_block`][mcbot.MinecraftClient.set_block] instead.

        Args:
            x: Block coordinate (floats are rounded down).
            y: Block coordinate.
            z: Block coordinate.
            face: The face being "clicked", which orients some blocks: `"up"` gives a vertical log or a bottom slab,
                `"down"` a top slab, `"north"`, `"south"`, `"east"` or `"west"` a lying log.
            look: Whether the player first looks at the cell. This also orients doors, stairs and torches.
            replace: If the cell holds another block, break it first (creative only). Otherwise the placement
                fails with reason `occupied`.

        Returns:
            The `info` dictionary, with:

            - `placed`: whether the block was placed;
            - `target`: the cell `[x, y, z]`;
            - `block`: the block now in the cell, or the one found there (`already_there`, `occupied`);
            - `replaced`: the block that was broken, if any;
            - on failure, `reason` and `message`.

            Possible reasons: `already_there` (the same block type is there), `occupied`, `out_of_reach`,
            `no_block_selected`, `player_in_the_way`, `rejected`.

        Raises:
            ValueError: Unknown face.
            McBotError: `replace=True` outside creative mode.

        Example:
            ```python
            mc.select_block("oak_planks", slot=0)
            info = mc.place_block(10, -60, 6)
            if not info["placed"]:
                print(info["reason"], info["message"])
            ```
        """
        if face not in FACES:
            raise ValueError(f"Unknown face: {face!r} (possible: {FACES})")
        return self._request({"type": "place_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "face": face, "look": look, "replace": replace})[1]

    def break_block(self, x: float, y: float, z: float, look: bool = True) -> dict[str, Any]:
        """Breaks a block instantly, like a player in creative. The block must be within reach.

        Args:
            x: Block coordinate (floats are rounded down).
            y: Block coordinate.
            z: Block coordinate.
            look: Whether the player first looks at the block.

        Returns:
            The `info` dictionary, with `broken` (bool), `block` and, on failure, `reason` (`empty`,
            `out_of_reach`, `rejected`) and `message`.

        Raises:
            McBotError: Not in creative mode.
        """
        return self._request({"type": "break_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "look": look})[1]

    def set_block(self, x: float, y: float, z: float, block: str) -> dict[str, Any]:
        """Writes an exact block state in a cell, like the `/setblock` command but without cheats.

        Works in a singleplayer world, in any game mode, in the chunks loaded around the player. The block is
        written exactly as given: neighbouring blocks are not updated (a torch written on air stays, a fence doesn't
        connect to its neighbours unless the state says so). Properties left out take their default value.

        Args:
            x: Block coordinate (floats are rounded down).
            y: Block coordinate.
            z: Block coordinate.
            block: Block state, such as `"stone"` or `"oak_stairs[facing=east,half=top]"`.

        Returns:
            The `info` dictionary, with `block`: the full state written, and `changed`: `[[x, y, z, state]]` if the
            game changed the block on its own right away (sand falling, for example), else `[]`.

        Raises:
            McBotError: Invalid state, position outside the world's height, chunk not loaded, not in a singleplayer
                world.

        Example:
            ```python
            mc.set_block(0, -60, 0, "oak_log[axis=x]")
            ```
        """
        info = self.set_blocks([((x, y, z), block)])
        info["block"] = info.pop("blocks")[0]
        return info

    def set_blocks(self, blocks: Iterable[tuple[tuple[float, float, float], str]]) -> dict[str, Any]:
        """Writes many exact block states, in order. Same rules as [`set_block`][mcbot.MinecraftClient.set_block].

        Blocks are sent in batches of [`SET_BLOCKS_BATCH`][mcbot.client.SET_BLOCKS_BATCH]. Every state and
        position of a batch is checked before anything is written: one invalid entry means nothing of that batch is
        written (earlier batches stay written). The call returns once the game shows the new blocks, so that
        [`get_blocks`][mcbot.MinecraftClient.get_blocks] right after sees them.

        Some blocks change on their own as soon as they are written, as in the game: sand over air falls, a
        redstone wire without a block under it breaks. The call then returns after half a second at most, and lists
        them in `changed`.

        Args:
            blocks: Pairs `((x, y, z), state)`. Write `"air"` to remove a block. Every cell must be in a chunk
                loaded around the player.

        Returns:
            The `info` dictionary of the last batch, with `blocks`: the full state written for every entry, and
            `changed`: `[x, y, z, state now]` for each cell the game changed on its own (usually empty).

        Raises:
            ValueError: `blocks` is empty.
            McBotError: Invalid state, position outside the world's height, chunk not loaded, not in a singleplayer
                world.

        Example:
            ```python
            # A 5 × 5 stone floor
            mc.set_blocks(((x, -61, z), "stone") for x in range(5) for z in range(5))
            ```
        """
        entries = [[*_block_pos(pos), block] for pos, block in blocks]
        if not entries:
            raise ValueError("No blocks to write")
        written: list[str] = []
        changed: list[list] = []
        for start in range(0, len(entries), SET_BLOCKS_BATCH):
            info = self._request({"type": "set_blocks", "blocks": entries[start:start + SET_BLOCKS_BATCH]})[1]
            written += info["blocks"]
            changed += info.get("changed", [])
        info["blocks"] = written
        info["changed"] = changed
        return info

    def fly_to(self, x: float, y: float, z: float, tolerance: float = 0.75, vertical_tolerance: float = 0.35,
               max_steps: int = 600, face_target: bool = True) -> dict[str, Any]:
        """Flies until the feet are at a position, then stops and releases the keys. Needs creative mode.

        Turns flying on if needed. At each step, predicts where the player would stop if every key were released
        (flight keeps momentum), and presses the keys that bring that point onto the target.

        Args:
            x: Target feet position.
            y: Target feet position.
            z: Target feet position.
            tolerance: Accepted horizontal distance to the target, in blocks.
            vertical_tolerance: Accepted vertical distance to the target, in blocks.
            max_steps: Steps (1 or 2 ticks each) before giving up.
            face_target: Whether to turn towards the target while flying.

        Returns:
            The `info` dictionary at arrival.

        Raises:
            McBotError: The target was not reached within `max_steps` steps, or the player can't fly.
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
        """Reads the blocks of a box, between two opposite corners.

        Only loaded chunks can be read (those within render distance). A request covers at most 1,048,576 blocks
        (3 × 3 full chunks) and is cut to the world's height.

        Args:
            corner1: A corner block `(x, y, z)`, included. Floats are rounded down.
            corner2: The opposite corner, included. The corners can be given in any order.
            states: Whether the palette holds full block states (`"oak_log[axis=y]"`) instead of names only
                (`"oak_log"`).

        Returns:
            The blocks of the box.

        Raises:
            McBotError: A chunk of the box is not loaded, the box is too large, or it is outside the world's height.

        Example:
            ```python
            volume = mc.get_blocks((0, -61, 0), (15, -55, 15))
            print(volume.block_at(3, -61, 4))
            ```
        """
        return self._blocks({"min": _block_pos(corner1), "max": _block_pos(corner2)}, states)

    def get_chunk(self, cx: int | None = None, cz: int | None = None, states: bool = False) -> BlockVolume:
        """Reads a whole chunk: 16 × world height × 16 blocks.

        Args:
            cx: Chunk coordinate, `x // 16`. By default, the player's chunk.
            cz: Chunk coordinate, `z // 16`. Give both `cx` and `cz`, or neither.
            states: Whether the palette holds full block states.

        Returns:
            The blocks of the chunk.

        Raises:
            ValueError: Only one of `cx` and `cz` given.
            McBotError: The chunk is not loaded.
        """
        if (cx is None) != (cz is None):
            raise ValueError("Give both cx and cz, or neither")
        if cx is None:
            x, _, z = self.ping()["pos"]
            cx, cz = math.floor(x) // 16, math.floor(z) // 16
        return self._blocks({"chunk": [cx, cz]}, states)

    def get_blocks_around(self, radius: int = 8, states: bool = False) -> BlockVolume:
        """Reads a cube centred on the block of the player's feet, at the same tick as the player's position.

        Args:
            radius: Half the side of the cube: the side is `2 × radius + 1`.
            states: Whether the palette holds full block states.

        Returns:
            The blocks of the cube.

        Raises:
            McBotError: A chunk of the cube is not loaded, or the cube is too large.
        """
        return self._blocks({"radius": radius}, states)

    def _blocks(self, box: dict[str, Any], states: bool) -> BlockVolume:
        ids, info = self._request({"type": "blocks", **box, "states": states})
        return BlockVolume(ids, info["palette"], tuple(info["origin"]))

    def get_entities(self, radius: float = 32.0, types: Iterable[str] | None = None, limit: int = 256,
                     visibility: bool = False) -> list[Entity]:
        """Lists the entities (mobs, dropped items, other players…) around the player, nearest first.

        Only the entities the server sends to the game are known: about 8 chunks around for mobs, 6 for dropped
        items, never beyond render distance. The player itself is not listed. An empty list is not an error.

        Args:
            radius: Distance from the player's feet, in blocks, 0 to 256.
            types: Only these types, such as `["zombie", "skeleton"]` (a single name works too). Default: all.
            limit: At most this many entities (the nearest ones), 1 to 4096.
            visibility: Whether to add `in_view` and `line_of_sight` to each entity, seen from the player's eyes.

        Returns:
            The entities, nearest first.

        Raises:
            McBotError: Invalid radius or limit, unknown entity type.

        Example:
            ```python
            mobs = mc.get_entities(radius=24, types=["zombie", "creeper"], visibility=True)
            seen = [e for e in mobs if e.in_view and e.line_of_sight]
            ```
        """
        return self._entities(_entity_query({"radius": radius, "types": types, "limit": limit,
                                              "visibility": visibility}))

    def get_entities_in(self, corner1: tuple[float, float, float], corner2: tuple[float, float, float],
                        types: Iterable[str] | None = None, limit: int = 256,
                        visibility: bool = False) -> list[Entity]:
        """Lists the entities whose hitbox touches a box, nearest first.

        Args:
            corner1: A corner block `(x, y, z)`, included.
            corner2: The opposite corner block, included.
            types: Only these types. Default: all.
            limit: At most this many entities, 1 to 4096.
            visibility: Whether to add `in_view` and `line_of_sight` to each entity.

        Returns:
            The entities, nearest first.

        Raises:
            McBotError: Invalid limit, unknown entity type.
        """
        return self._entities(_entity_query({"min": corner1, "max": corner2, "types": types, "limit": limit,
                                              "visibility": visibility}))

    def _entities(self, query: dict[str, Any]) -> list[Entity]:
        info = self._request({"type": "entities", **query})[1]
        return [Entity.from_json(entity) for entity in info["entities"]]

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
    """Connects to the mod, retrying as long as Minecraft is not reachable.

    Handy to start a script before the game. Use the result in a `with` block: it keeps this connection.

    Args:
        host: Address of the mod.
        port: Port of the mod.
        retry_seconds: Time between two attempts, in seconds.
        log: Called with a message at each attempt.

    Returns:
        A connected client.

    Example:
        ```python
        with connect_with_retry() as mc:
            mc.wait_for_world()
            ...
        ```
    """
    log(f"Connecting to Minecraft on {host}:{port}...")
    while True:
        try:
            return MinecraftClient(host, port).connect()
        except OSError:
            log(f"  Minecraft (with the McBot mod) is not reachable, retrying in {retry_seconds:g} s...")
            time.sleep(retry_seconds)


def _entity_query(options: dict[str, Any]) -> dict[str, Any]:
    """Entity options as the mod expects them; ``None`` values are left out (the mod's defaults apply)."""
    unknown = set(options) - set(ENTITY_QUERY_KEYS)
    if unknown:
        raise ValueError(f"Unknown entity options: {sorted(unknown)} (possible: {ENTITY_QUERY_KEYS})")
    query = {key: value for key, value in options.items() if value is not None}
    for corner in ("min", "max"):
        if corner in query:
            query[corner] = _block_pos(query[corner])
    if "types" in query:
        query["types"] = [query["types"]] if isinstance(query["types"], str) else list(query["types"])
    return query


def _block_pos(point: tuple[float, float, float]) -> list[int]:
    return [math.floor(c) for c in point]


def _wrap_degrees(angle: float) -> float:
    """Wraps an angle into [-180, 180)."""
    return (angle + 180.0) % 360.0 - 180.0
