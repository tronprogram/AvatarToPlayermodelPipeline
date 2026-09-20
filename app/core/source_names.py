"""Source-legal material names. Stdlib only so Blender can import this."""

from __future__ import annotations

import re
from collections.abc import Hashable

_ILLEGAL = re.compile(r"[^A-Za-z0-9_]+")
_BLENDER_DUP = re.compile(r"(?:\.\d{3})+$")


def source_material_name(name: str) -> str:
    """Ready Player Me ``hair: Teased spikes_3`` → Source-legal ``hair``.

    Blender's second ``face`` datablock is ``face.001``. Strip that suffix
    before sanitizing so it stays ``face``, not ``face_001``.
    """
    head = name.split(":", 1)[0].strip() or name
    head = _BLENDER_DUP.sub("", head)
    clean = _ILLEGAL.sub("_", head).strip("_") or "mat"
    if clean[0].isdigit():
        clean = f"mat_{clean}"
    return clean[:63]


def allocate_source_name(
    base: str,
    texture_key: Hashable,
    assigned: dict[str, Hashable],
) -> str:
    """Reuse ``base`` when the same texture is already assigned; else ``base_2``.

    Two RPM ``face`` primitives that share one image stay ``face``. A second
    material that sanitizes to ``face`` but uses a different image becomes
    ``face_2`` so it gets its own VMT.
    """
    if base not in assigned:
        assigned[base] = texture_key
        return base
    if assigned[base] == texture_key:
        return base
    suffix = 2
    while True:
        candidate = f"{base[:60]}_{suffix}"
        if candidate not in assigned:
            assigned[candidate] = texture_key
            return candidate
        if assigned[candidate] == texture_key:
            return candidate
        suffix += 1
