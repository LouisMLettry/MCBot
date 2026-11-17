# Troubleshooting

## Python can't connect

`ConnectionRefusedError`, or `connect_with_retry` keeps printing *Minecraft (with the McBot mod) is not reachable*.

- Is Minecraft running, **with the mod**? The game log must show `McBot listening on 127.0.0.1:5555`.
- With your own Minecraft installation: did you start the **fabric-loader-1.21.1** profile, with both
  `mcbot-<version>.jar` and Fabric API in the `mods` folder?
- Was the game started with another port (`-Dmcbot.port=...`)? Pass the same `port` to `MinecraftClient`.

## The script hangs at the first command

The mod serves **one connection at a time**: another script (or a Python shell, or a notebook) is still connected.
Close it; the waiting script then goes on. Without that, it fails after `timeout` seconds (130 by default).

## `McBotError: No world loaded`

Join a singleplayer world first, or call `mc.wait_for_world()` at the start of your script.

## Minecraft refuses to start: McBot needs Minecraft 1.21.1

You installed Fabric for another version, often **1.21.11** instead of **1.21.1**. Install Fabric Loader for
exactly 1.21.1, use a Fabric API whose version ends in `+1.21.1`, and start the `fabric-loader-…-1.21.1` profile.

## The mod is not loaded

- Only `mcbot-<version>.jar` goes in `mods`, not `mcbot-<version>-sources.jar`.
- When updating, remove the old `mcbot-*.jar` first: two versions can't be loaded together.

## `java -version` is too old, or Gradle complains about Java

Building the mod needs a **JDK 25 or newer**. Install it (see [Installation](getting-started/installation.md)),
then open a **new** terminal so that it is found.

## The Python environment is broken after copying the project

A `.venv` folder only works on the machine and system where it was created. Delete it and recreate it:

```bash
cd python
rm -rf .venv
uv sync
```

## `McBotError: Chunk (…) is not loaded`

You are reading blocks outside the area loaded around the player. Read closer to the player, or raise the render
distance in the game's video settings.

## Images look distorted

The image size doesn't have the same aspect ratio as the game window. Use a ratio of 16:9 (the default window is
854 × 480), such as `mc.config(width=160, height=90)`, or resize the window.

## The player keeps walking after my script stopped sending commands

Keys stay pressed until the next command. Call `mc.stop()` before long computations and at the end of your script.
Closing the connection (leaving the `with` block, or ending the script) releases them too.
