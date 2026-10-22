"""Client TCP pour le mod McBot (Fabric) : envoie des actions au joueur et reçoit son état et des images."""

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

# Physique du vol créatif : à chaque tick la vitesse horizontale est multipliée par 0,91 et la verticale par 0,6.
# Distance parcourue avant l'arrêt si on relâche tout = vitesse × 1 / (1 - frottement).
HORIZONTAL_STOP_FACTOR = 1 / (1 - 0.91)
VERTICAL_STOP_FACTOR = 1 / (1 - 0.6)
MAX_TURN_PER_STEP = 45.0


class McBotError(RuntimeError):
    """Erreur renvoyée par le mod (par exemple : aucun monde chargé)."""


class MinecraftClient:
    """Pilote le joueur Minecraft via le mod McBot.

    Chaque ``step`` maintient les touches demandées pendant ``ticks`` ticks (20 ticks = 1 s)
    puis renvoie ``(image, info)``. Les touches restent enfoncées jusqu'à la commande suivante :
    appeler ``stop()`` pour tout relâcher.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 130.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self.frame_width = 128
        self.frame_height = 128

    # --- Connexion ---------------------------------------------------------------------------

    def connect(self) -> "MinecraftClient":
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return self

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "MinecraftClient":
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- Commandes du protocole ---------------------------------------------------------------

    def ping(self) -> dict[str, Any]:
        return self._request({"type": "ping"})[1]

    def wait_for_world(self, poll_seconds: float = 3.0, log: Callable[[str], None] = print) -> dict[str, Any]:
        """Attend que le joueur soit dans un monde (le script peut être lancé depuis le menu principal)."""
        info = self.ping()
        while not info["in_world"]:
            log("  En attente : entre dans un monde solo...")
            time.sleep(poll_seconds)
            info = self.ping()
        return info

    def config(self, width: int, height: int, hide_gui: bool | None = None) -> dict[str, Any]:
        """Définit la taille des images renvoyées (et masque éventuellement l'interface, comme F1)."""
        request: dict[str, Any] = {"type": "config", "width": width, "height": height}
        if hide_gui is not None:
            request["hide_gui"] = hide_gui
        info = self._request(request)[1]
        self.frame_width = info["frame_width"]
        self.frame_height = info["frame_height"]
        return info

    def step(self, ticks: int = 1, frame: bool = False, yaw: float = 0.0, pitch: float = 0.0,
             **keys: bool) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Maintient les touches ``keys`` pendant ``ticks`` ticks et tourne la caméra de ``yaw``/``pitch`` degrés.

        Touches possibles : forward, back, left, right, jump, sprint, sneak, attack, use.
        ``yaw`` > 0 tourne vers la droite, ``pitch`` > 0 regarde vers le bas.
        """
        unknown = set(keys) - set(ACTION_KEYS)
        if unknown:
            raise ValueError(f"Touches inconnues : {sorted(unknown)} (possibles : {ACTION_KEYS})")
        action = {key: bool(keys.get(key, False)) for key in ACTION_KEYS}
        action["yaw"] = float(yaw)
        action["pitch"] = float(pitch)
        return self._request({"type": "step", "ticks": int(ticks), "frame": frame, "action": action})

    # --- Raccourcis ---------------------------------------------------------------------------

    def stop(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Relâche toutes les touches."""
        return self.step(ticks=1, frame=frame)

    def forward(self, seconds: float, sprint: bool = False, jump: bool = False,
                frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        return self.step(_ticks(seconds), frame=frame, forward=True, sprint=sprint, jump=jump)

    def turn(self, degrees: float, seconds: float = 0.5,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Tourne sur place (degrés > 0 : vers la droite)."""
        return self.step(_ticks(seconds), frame=frame, yaw=degrees)

    def look(self, pitch: float, seconds: float = 0.5,
             frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Lève (pitch < 0) ou baisse (pitch > 0) la tête."""
        return self.step(_ticks(seconds), frame=frame, pitch=pitch)

    def jump(self, frame: bool = False) -> tuple[np.ndarray | None, dict[str, Any]]:
        return self.step(ticks=10, frame=frame, jump=True)

    # --- Construction -------------------------------------------------------------------------

    def set_game_mode(self, mode: str) -> dict[str, Any]:
        """Change le mode de jeu (survival, creative, adventure, spectator) ; monde solo uniquement, sans cheats."""
        return self._request({"type": "game_mode", "mode": mode})[1]

    def set_build_mode(self, enabled: bool = True) -> dict[str, Any]:
        """Mode construction = créatif : blocs illimités, vol autorisé, destruction instantanée."""
        return self.set_game_mode("creative" if enabled else "survival")

    def set_flying(self, enabled: bool = True) -> dict[str, Any]:
        """Active/désactive le vol (mode construction requis). En vol : jump = monter, sneak = descendre.

        Tant que le vol est activé par le script, le mod le rallume s'il est coupé en l'air.
        """
        return self._request({"type": "fly", "enabled": enabled})[1]

    def select_block(self, block: str, slot: int | None = None) -> dict[str, Any]:
        """Met un bloc en main, par exemple ``"oak_planks"`` ou ``"minecraft:glass"``.

        En mode construction, le bloc est créé dans l'emplacement ``slot`` (0-8) de la barre d'accès rapide
        (par défaut l'emplacement actuel). En survie, il doit déjà être dans la barre.
        """
        request: dict[str, Any] = {"type": "select_block", "block": block}
        if slot is not None:
            request["slot"] = slot
        return self._request(request)[1]

    def place_block(self, x: float, y: float, z: float, face: str = "up", look: bool = True) -> dict[str, Any]:
        """Pose le bloc tenu en main dans la case (x, y, z), qui doit être à portée (5 blocs en créatif).

        Pas besoin de bloc voisin : on peut construire en l'air. ``face`` (face cliquée) oriente certains blocs :
        ``"up"`` = bûche verticale / dalle du bas, ``"down"`` = dalle du haut, ``"north"``… = bûche couchée.
        Renvoie ``info`` avec ``placed`` (bool) et, en cas d'échec, ``reason`` (occupied, out_of_reach,
        no_block_selected, player_in_the_way, rejected) et ``message``.
        """
        if face not in FACES:
            raise ValueError(f"Face inconnue : {face!r} (possibles : {FACES})")
        return self._request({"type": "place_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "face": face, "look": look})[1]

    def break_block(self, x: float, y: float, z: float, look: bool = True) -> dict[str, Any]:
        """Casse instantanément le bloc (x, y, z) (mode construction). Renvoie ``info`` avec ``broken`` (bool)."""
        return self._request({"type": "break_block", "x": math.floor(x), "y": math.floor(y), "z": math.floor(z),
                              "look": look})[1]

    def fly_to(self, x: float, y: float, z: float, tolerance: float = 0.75, vertical_tolerance: float = 0.35,
               max_steps: int = 600, face_target: bool = True) -> dict[str, Any]:
        """Vole jusqu'à la position (x, y, z) des pieds, puis s'arrête et relâche les touches.

        Pilotage : on estime où le joueur s'arrêterait s'il relâchait tout (il garde de l'élan), et on appuie
        sur avancer/reculer/gauche/droite/monter/descendre pour amener ce point d'arrêt sur la cible.
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

            # Écart entre la cible et le point d'arrêt prévu, exprimé dans le repère du joueur.
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
        raise McBotError(f"fly_to : cible ({x:.1f}, {y:.1f}, {z:.1f}) non atteinte, position {info['pos']}")

    # --- Monde ---------------------------------------------------------------------------------

    def get_blocks(self, corner1: tuple[float, float, float], corner2: tuple[float, float, float],
                   states: bool = False) -> BlockVolume:
        """Blocs de la boîte entre deux coins (inclus), en coordonnées monde.

        La boîte est limitée à la hauteur du monde et à 1 048 576 blocs (3 × 3 chunks entiers) ; ses chunks doivent
        être chargés (dans la distance d'affichage). Avec ``states=True``, la palette contient l'état complet des
        blocs (``"minecraft:oak_log[axis=y]"``) au lieu de leur seul nom.
        """
        return self._blocks({"min": _block_pos(corner1), "max": _block_pos(corner2)}, states)

    def get_chunk(self, cx: int | None = None, cz: int | None = None, states: bool = False) -> BlockVolume:
        """Chunk entier (16 × hauteur du monde × 16) de coordonnées de chunk (cx, cz) ; par défaut, celui du joueur."""
        if (cx is None) != (cz is None):
            raise ValueError("Donner cx et cz, ou aucun des deux")
        if cx is None:
            x, _, z = self.ping()["pos"]
            cx, cz = math.floor(x) // 16, math.floor(z) // 16
        return self._blocks({"chunk": [cx, cz]}, states)

    def get_blocks_around(self, radius: int = 8, states: bool = False) -> BlockVolume:
        """Cube de côté 2 × radius + 1 centré sur le bloc des pieds du joueur (position lue au même tick)."""
        return self._blocks({"radius": radius}, states)

    def _blocks(self, box: dict[str, Any], states: bool) -> BlockVolume:
        ids, info = self._request({"type": "blocks", **box, "states": states})
        return BlockVolume(ids, info["palette"], tuple(info["origin"]))

    # --- Transport ----------------------------------------------------------------------------

    def _request(self, message: dict[str, Any]) -> tuple[np.ndarray | None, dict[str, Any]]:
        """Envoie une requête ; renvoie les données binaires décodées (image ou indices de blocs) et le JSON."""
        if self._sock is None:
            raise RuntimeError("Non connecté : appeler connect() d'abord")

        payload = json.dumps(message).encode("utf-8")
        self._sock.sendall(struct.pack(">I", len(payload)) + payload)

        info = json.loads(self._recv_block().decode("utf-8"))
        raw_data = self._recv_block()
        if not info.get("ok", False):
            raise McBotError(info.get("error", "erreur inconnue"))

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
                raise ConnectionError("Connexion fermée par Minecraft")
            buffer.extend(chunk)
        return bytes(buffer)


def connect_with_retry(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, retry_seconds: float = 3.0,
                       log: Callable[[str], None] = print) -> MinecraftClient:
    """Se connecte au mod, en réessayant tant que Minecraft n'est pas lancé."""
    log(f"Connexion à Minecraft sur {host}:{port}...")
    while True:
        try:
            return MinecraftClient(host, port).connect()
        except OSError:
            log(f"  Minecraft (avec le mod McBot) n'est pas joignable, nouvel essai dans {retry_seconds:g} s...")
            time.sleep(retry_seconds)


def _block_pos(point: tuple[float, float, float]) -> list[int]:
    return [math.floor(c) for c in point]


def _ticks(seconds: float) -> int:
    return max(1, round(seconds * TICKS_PER_SECOND))


def _wrap_degrees(angle: float) -> float:
    """Ramène un angle dans [-180, 180)."""
    return (angle + 180.0) % 360.0 - 180.0
