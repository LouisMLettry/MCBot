# Protocol

You don't need this page to use `mcbot`. It describes the messages between the package and the mod, if you want to
talk to the mod from another language or understand what a method sends.

## Transport

- TCP on `127.0.0.1`, port 5555 by default, **one client at a time**.
- One request, one response, in order. Integers are big-endian.
- **Request:** `uint32` length, then a UTF-8 JSON object with a `type`.
- **Response:** `uint32` length, then a JSON object; then `uint32` length and binary data (length 0 if none). The
  JSON field `payload` names the binary data:
    - `frame`: raw RGB pixels, `height × width × 3` bytes, row by row from the top;
    - `blocks`: one `uint16` per block (index into `palette`), ordered by x, then y, then z.
- Every response holds the player's state (see [The player's state](../concepts/state.md)) and `ok`. When `ok` is
  `false`, `error` says why.

## Requests

| `type` | Fields | Effect |
|---|---|---|
| `ping` | | Returns the state. |
| `config` | `width`, `height`, `hide_gui` (optional) | Image size (16 to 1024 pixels); hides the interface like F1. |
| `step` | `ticks`, `frame`, `action` {boolean keys, `yaw`, `pitch`}, `entities` (optional, the options of `entities`) | Applies the action for `ticks` ticks, then responds. With `entities`: the entities, as the frame shows them. |
| `game_mode` | `mode` (`survival`, `creative`, `adventure`, `spectator`) | Changes the game mode; responds once applied. |
| `fly` | `enabled` | Starts or stops flying (creative). |
| `select_block` | `block`, `slot` (0 to 8, optional) | Puts the block in hand. → `slot`, `item`, `is_block` |
| `place_block` | `x`, `y`, `z`, `face` (default `up`), `look` (default `true`), `replace` (default `false`) | Places the held block. → `placed`, `target`, `block`, `replaced`, `reason`, `message` |
| `break_block` | `x`, `y`, `z`, `look` | Breaks the block (creative). → `broken`, `block`, `reason`, `message` |
| `set_blocks` | `blocks`: `[[x, y, z, "state"], …]` | Writes exact block states, in loaded chunks only; responds once the game shows them, or 10 ticks after the server wrote them. → `blocks` (full states written), `changed` (`[[x, y, z, "state now"], …]` for the cells the game changed on its own) |
| `blocks` | `min` and `max` `[x, y, z]`, **or** `chunk` `[cx, cz]`, **or** `radius`; `states` (default `false`) | Blocks of the box. → `origin`, `shape` `[sx, sy, sz]`, `palette`, and the indices as binary data |
| `entities` | `radius` (default 32, max 256) **or** `min` and `max`; `types` (default all); `limit` (default 256, max 4096); `visibility` (default `false`) | Entities around the player, nearest first. → `entities`: a list of objects with the fields of [`Entity`][mcbot.Entity] (fields that don't apply are left out) |

## Example

```python
import json, socket, struct

sock = socket.create_connection(("127.0.0.1", 5555))

def send(message):
    body = json.dumps(message).encode()
    sock.sendall(struct.pack(">I", len(body)) + body)

def receive_exact(size):
    data = b""
    while len(data) < size:
        data += sock.recv(size - len(data))
    return data

def receive_block():
    (length,) = struct.unpack(">I", receive_exact(4))
    return receive_exact(length)

send({"type": "ping"})
info = json.loads(receive_block())
data = receive_block()       # empty for a ping
print(info["pos"])
```
