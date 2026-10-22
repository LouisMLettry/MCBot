# Troubleshooting

Problems already met, and their fix.

## Game crashes when a script connects: `IllegalAccessError ... class_1661.field_7545`

```
java.lang.IllegalAccessError: class com.mcbot.BotController tried to access private field
net.minecraft.class_1661.field_7545
```

**Cause:** the game runs Minecraft **1.21.11**, not **1.21.1**. In 1.21.11 the "selected hotbar slot" field of the
inventory became private, and the mod reads it in every response. The mod still loads because `fabric.mod.json`
accepts any `1.21.x`.

**Fix:** install Fabric Loader for exactly 1.21.1, use a Fabric API built for `+1.21.1`, and start the
`fabric-loader-…-1.21.1` profile in the launcher.

Since 2026-10-22, `fabric.mod.json` requires exactly `1.21.1`: on a wrong version, Fabric now stops at startup
with a message saying McBot needs Minecraft 1.21.1, instead of this crash.

## Python venv does not work after copying the project

The `.venv` folder is specific to the machine and OS it was created on (a Windows venv has `Scripts\`, not `bin/`).
Delete it and let uv recreate it:

```bash
cd python
rm -rf .venv
uv sync
```

## Wrong jar in the `mods` folder

`mod/build/libs/` contains `mcbot-<version>.jar` (the mod) and `mcbot-<version>-sources.jar` (source code only).
Only the first one goes into `mods`. When updating, remove the old `mcbot-*.jar` first.

On the Mac, `mods/mcbot-0.2.1.jar` is a symbolic link to `mod/build/libs/mcbot-0.2.1.jar`. If the mod version
changes, the jar gets a new name and the link points to nothing, so the mod is not loaded and Python can't connect.
Recreate the link with the new name.

## `git add` fails: `'python/' does not have a commit checked out`

`uv init` creates its own Git repository inside `python/`. Remove `python/.git` (after checking it holds nothing)
so the whole project lives in one repository.

## `git push` / `git ls-remote`: `Permission denied (publickey)`

GitHub does not accept the SSH key of this machine. Add `~/.ssh/id_rsa.pub` (or a new key) in GitHub →
Settings → SSH and GPG keys, then test with `ssh -T git@github.com`.
