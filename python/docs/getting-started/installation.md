# Installation

You need three things running: **Minecraft 1.21.1 with the McBot mod**, a **singleplayer world**, and **Python**
with the `mcbot` package.

## Requirements

| Tool | Version | Why |
|---|---|---|
| [Git](https://git-scm.com/) | any | to get the code |
| JDK | 25 or newer | to build and start the mod (the mod itself targets Java 21, like Minecraft 1.21.1) |
| Python | 3.10 or newer | for your scripts |
| [uv](https://docs.astral.sh/uv/) | recent | manages the Python environment and dependencies |

=== "Windows"

    ```powershell
    winget install Git.Git EclipseAdoptium.Temurin.25.JDK astral-sh.uv
    ```

=== "macOS"

    ```bash
    brew install git uv
    brew install --cask temurin       # the latest JDK (25 or newer)
    ```

=== "Linux"

    Install Git and a JDK 25 with your package manager (or from [Adoptium](https://adoptium.net/)), then
    [uv](https://docs.astral.sh/uv/getting-started/installation/).

Open a new terminal afterwards and check: `java -version` must show 25 or higher. uv installs Python by itself
if needed.

## Get the code

```bash
git clone https://github.com/LouisMLettry/Craftilot.git
cd Craftilot
```

The repository holds the mod (`mod/`) and the Python package (`python/`).

## Start Minecraft with the mod

The simplest way is **development mode**: Gradle downloads Minecraft 1.21.1, Fabric and the mod's dependencies,
then starts the game with the mod already loaded.

=== "Windows"

    ```powershell
    cd mod
    .\gradlew.bat runClient
    ```

=== "macOS / Linux"

    ```bash
    cd mod
    ./gradlew runClient
    ```

The first start takes a few minutes. When the mod is ready, the log shows:

```
[McBot-Server/INFO] (mcbot) McBot listening on 127.0.0.1:5555
```

In the game, create a **singleplayer world**. A *Superflat* world in *Creative* mode is the easiest place to start:
flat, quiet and roomy. Cheats are not needed.

??? note "Using your own Minecraft installation instead"

    1. Build the mod: `./gradlew build` (or `.\gradlew.bat build`) in `mod/`. The mod is
       `mod/build/libs/mcbot-<version>.jar` (not the `-sources` one).
    2. Install [Fabric Loader](https://fabricmc.net/use/installer/) for Minecraft **1.21.1** (careful: not
       1.21.11).
    3. Download [Fabric API](https://modrinth.com/mod/fabric-api) for 1.21.1 (a version ending in `+1.21.1`).
    4. Copy both jars into the `mods` folder: `%APPDATA%\.minecraft\mods` on Windows,
       `~/Library/Application Support/minecraft/mods` on macOS, `~/.minecraft/mods` on Linux.
    5. In the launcher, start the **fabric-loader-1.21.1** profile.

    When you update the mod, remove the old `mcbot-*.jar` from `mods` first.

## Set up Python

In a second terminal:

```bash
cd python
uv sync
```

This creates a virtual environment in `python/.venv` with `mcbot` and its dependencies (numpy, Pillow).
Check that everything works, with Minecraft open and a world loaded:

```bash
uv run python scripts/demo_movements.py
```

The player walks, turns, jumps and looks around; the pictures it takes are saved in `python/frames/`.

!!! tip "You can click on your terminal"
    Minecraft normally pauses when its window loses focus. While a script is connected, the mod keeps it running
    (and closes the pause menu if it is open).

## Use mcbot in your own project

You can write your scripts in `python/scripts/` next to the examples, or keep your project in its own folder and
add `mcbot` as a dependency. The package is named `craftilot`; you import it as `mcbot`.

=== "From your clone (recommended)"

    ```bash
    uv init my-project && cd my-project
    uv add --editable ../Craftilot/python
    ```

    Editable: when you `git pull` the Craftilot repository, your project uses the new version at once.

=== "From GitHub"

    ```bash
    uv add "craftilot @ git+https://github.com/LouisMLettry/Craftilot#subdirectory=python"
    ```

    Pins the version in your `uv.lock`; run `uv lock --upgrade-package craftilot` to update.

The mod still has to run in Minecraft: build it from your clone as above.

Next: **[Your first script](first-script.md)**.
