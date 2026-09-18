# Overview

This is a desktop workshop that turns an avatar into a Garry’s Mod playermodel. You leave with a folder you drop into `addons` — not a Workshop upload.

The convert **engine** is a straight line (prepare tools, name the model, run the job, look at the result). The **app** is not that line. It is a workbench: convert is the loud action in the middle, and everything else is a room you can open when you need it.

## The workbench

| Room | What it is for |
|------|----------------|
| Tools | Are Blender, the compiler, and the rest actually here? A status light, not a hallway. |
| Library | Past converts. Re-open one, rename, run again. |
| Bench | The avatar you are working on now, and the button that converts it. |
| Shelves | What the job produced: body, first-person hands, textures, compiled model, addon folder. Open any of them. |
| Log | What the last job did, and where it failed. |

You can drop a file onto the window, poke a shelf, or fix tools without “going back a step.”

## What convert actually makes

One job fills the shelves:

- A playermodel GMod can spawn
- Matching first-person hands
- Textures the game will load
- An addon folder with a name and a short description

Under the hood that job still runs in order (rig, mesh, textures, compile body, compile hands, pack). The user does not have to drive those steps. They only notice them if they open the log or a shelf.

## What is here today

The engine can do a full convert. The desktop window can check tools and open a leftover preview. There is no workbench UI yet — no library, no drop-on-window bench, no shelves wired to the last job.

Workshop publish is out of scope on purpose.

## Next step

[index.md](index.md) if you need the how-to pages (export, preview, platform, services).
