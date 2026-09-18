"""Write the autorun Lua that registers a GMod playermodel."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.templates import render_valve

_TEMPLATE_NAME = "playermodel.lua"
_SAFE_NAME = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class PlayermodelLua:
    """Named inputs for ``player_manager.AddValidModel``.

    ``model_path`` is the Lua path starting at ``models/``, with forward
    slashes, e.g. ``models/player/avatar/avatar.mdl``. ``hands_path`` is
    the C-arms MDL, e.g. ``models/weapons/c_arms_avatar.mdl``.
    """

    display_name: str
    model_path: str
    hands_path: str | None = None


class PlayerLuaService:
    """Write one autorun ``.lua`` into an output directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, spec: PlayermodelLua, filename: str | None = None) -> Path:
        """Render ``spec`` and write a lowercase ``.lua``. Returns that path."""
        self._validate(spec)
        self.directory.mkdir(parents=True, exist_ok=True)
        dest = self.directory / (filename or lua_filename(spec.display_name))
        dest.write_text(self.render(spec), encoding="utf-8", newline="\n")
        return dest

    def render(self, spec: PlayermodelLua) -> str:
        self._validate(spec)
        return render_valve(
            _TEMPLATE_NAME,
            display_name=spec.display_name,
            model_path=_slash(spec.model_path),
            hands_path=_slash(spec.hands_path) if spec.hands_path else None,
        )

    def _validate(self, spec: PlayermodelLua) -> None:
        if not spec.display_name.strip():
            raise ValueError("display_name is required")
        path = _slash(spec.model_path)
        if not path.startswith("models/") or not path.endswith(".mdl"):
            raise ValueError(
                "model_path must start with models/ and end with .mdl, "
                f"not {spec.model_path!r}"
            )
        if spec.hands_path:
            hands = _slash(spec.hands_path)
            if not hands.startswith("models/") or not hands.endswith(".mdl"):
                raise ValueError(
                    "hands_path must start with models/ and end with .mdl, "
                    f"not {spec.hands_path!r}"
                )


def source_slug(display_name: str) -> str:
    """Lowercase Source/Lua stem: ``My Avatar`` → ``my_avatar``."""
    stem = _SAFE_NAME.sub("_", display_name.strip().lower()).strip("_")
    if not stem:
        raise ValueError("display_name must contain letters or digits")
    return stem


def lua_filename(display_name: str) -> str:
    """``My Avatar`` → ``my_avatar.lua``."""
    return f"{source_slug(display_name)}.lua"


def _slash(value: str) -> str:
    return value.replace("\\", "/")
