# Overview

This is a "desktop" (It really is a web app running in a browser) (I genuinely don't know how to do a good looking native application) program that turns a 360sona avatar into a Garry’s Mod playermodel.

Basically got inspired and made it feel like the average installer.

## The screens

| Screen   | What it is for                                                                                                                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Welcome  | Begin configuration.                                                                                                                                                                                                                   |
| Setup    | Find or install Blender 5.2 LTS, Source Tools, the modified Source compiler, HLMV++, SteamCMD, and the Garry's Mod Dedicated Server tooling. Additionally, if you're running an Unix-like system, you can select a Wine bottle to use. |
| Convert  | Drop a 360sona, name it, run the job, download `{slug}.zip`.                                                                                                                                                                           |
| Settings | Path overrides, Convert defaults, zip destination,etc.                                                                                                                                                                                 |

## Setup Assistant

The setup assistant will assist you in the process of setting up the program to convert your 360sona avatar into a Garry's Mod playermodel.

Internally, the setup process will:

1. Setup a Wine prefix to use if you're running an Unix-like system.
2. Download and install Blender 5.2 LTS, Blender Source Tools, the modified Source compiler, HLMV++, SteamCMD, and Garry's Mod Dedicated Server tooling.

## Convert Assistant

The convert assistant will assist you in the process of converting your 360sona avatar into a Garry's Mod playermodel.

Internally, the convert process will:

1. Line the bones up: ValveBiped names, Source axes (`+X` forward), about 72 units tall.
2. Export Source DMX in headless Blender: reference mesh, physics capsules, ragdoll and proportion clips, and arm-weighted C-arms.
3. Turn the GLB skins into VTF 7.4 and VertexLitGeneric VMTs, then copy them into the GMod tools materials tree.
4. Compile the playermodel QC, then the first-person hands QC. Gender picks the citizen anim set (`m_anm.mdl` or `f_anm.mdl`).
5. Pack an addon folder (`addon.json`, autorun Lua that registers the model and the hands, both MDL families, materials) and zip it as `{slug}.zip`.

The convert assistant will also assist you in the process of previewing your playermodel in HLMV++.

- Note: HLMV++ is only available on Windows. Trying to use it on a Unix-like system will probably fail with a tier0 dll error. If you really want to preview the model, you could get the Source SDK 2013 Multiplayer SDK and use its vanilla HLMV.

Path names for a given display name are in [export.md](export.md).

## Compiler

The convert assistant uses BobmacU’s modified SFM `studiomdl.exe` under `data/compiler/` (weight cull 0.0001). Setup downloads it from [Gmod-Model-Port-Template](https://github.com/BobmacU/Gmod-Model-Port-Template). Preview uses **HLMV++** from [Hammer++](https://github.com/ficool2/HammerPlusPlus-Website/releases). The convert assistant uses the same compiler to compile the playermodel and the first-person hands.

Garry's Mod dedicated (app **4020**) still uses anonymous SteamCMD.
