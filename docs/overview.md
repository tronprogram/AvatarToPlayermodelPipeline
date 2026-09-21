# Overview

This is a desktop hallway that turns an avatar into a Garry’s Mod playermodel. You leave with a zip you drop into `garrysmod/addons` — not a Workshop upload.

The convert **engine** is a straight line (prepare tools, name the model, run the job, zip the addon). The **app** is that line, as Metro Setup / Convert / Settings screens.

## The hallway

| Screen | What it is for |
|--------|----------------|
| Welcome | Begin configuration. |
| Setup | Find or install Blender 5.2 LTS, Source Tools, SteamCMD, GMod dedicated (4020), and Source SDK 2013 MP (243750). Crowbar is optional. |
| Convert | Drop a 360sona, name it, run the job, download `{slug}.zip`. |
| Settings | Path overrides, Convert defaults, zip destination, Wine prefix. |

On macOS and Linux, Setup and Convert stop after the intro if there is no valid Wine prefix. Point Settings at a prefix (`drive_c` present) or Cancel.

## What convert actually makes

One job fills the zip:

- A playermodel GMod can spawn
- Matching first-person hands
- Textures the game will load
- An addon folder with a name and a short description

The archive extracts to `garrysmod/addons/<slug>/`. Under the hood the job still runs in order (rig, mesh, textures, compile body, compile hands, pack).

## Compiler

Compile uses stock **Source SDK Base 2013 Multiplayer** `bin/studiomdl.exe` (Steam app **243750**). Install it with `steam://install/243750`, then let Setup detect a Steam library folder or point Settings at that tree. There is no patched compiler under `data/compiler/`.

Garry's Mod dedicated (app **4020**) still uses anonymous SteamCMD.

Workshop publish is out of scope on purpose.

## Next step

[index.md](index.md) if you need the how-to pages (export, preview, platform, services).
