"""studiomdl compile wrapper."""

from pathlib import Path

from app.core.process import CommandResult
from app.services.compile import CompileService, modelname_from_qc
from app.services.windows_tools import WindowsToolHost


def test_studiomdl_prefers_modified_compiler(tmp_path: Path, monkeypatch):
    from app.services import crowbar

    dest = tmp_path / "compiler" / "bin" / "studiomdl.exe"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"SFM")
    monkeypatch.setattr(crowbar, "data_dir", lambda: tmp_path)
    assert crowbar.studiomdl_exe() == dest


def test_modelname_from_qc_normalizes_slashes(tmp_path: Path):
    qc = tmp_path / "avatar.qc"
    qc.write_text('$modelname "player\\avatar\\avatar.mdl"\n', encoding="utf-8")
    assert modelname_from_qc(qc) == "player/avatar/avatar.mdl"


def test_compile_service_wine_argv(monkeypatch, tmp_path: Path):
    qc = tmp_path / "avatar.qc"
    qc.write_text('$modelname "player/avatar/avatar.mdl"\n', encoding="utf-8")
    compiler = tmp_path / "studiomdl.exe"
    compiler.write_bytes(b"")
    game = tmp_path / "garrysmod"
    (game / "gameinfo.txt").parent.mkdir(parents=True, exist_ok=True)
    (game / "gameinfo.txt").write_text("GameInfo {}\n", encoding="utf-8")
    mdl = game / "models" / "player" / "avatar" / "avatar.mdl"
    mdl.parent.mkdir(parents=True)
    mdl.write_bytes(b"IDST")
    (mdl.with_suffix(".vvd")).write_bytes(b"VVD")
    (mdl.with_name("avatar.dx90.vtx")).write_bytes(b"VTX")

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return CommandResult(argv=list(cmd), returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.services.compile.run_command", fake_run)
    monkeypatch.setattr("app.services.crowbar.studiomdl_exe", lambda: compiler)
    monkeypatch.setattr("app.services.compile.gmod_tools_root", lambda data: tmp_path)

    wine = tmp_path / "wine64"
    prefix = tmp_path / "pfx"
    host = WindowsToolHost(kind="wine", wine=wine, prefix=prefix)
    compiled = CompileService(host).compile(qc)

    assert captured["cmd"][0] == str(wine)
    assert captured["cmd"][1] == str(compiler)
    assert captured["cmd"][2:5] == ["-game", host.tool_path(game), "-nop4"]
    assert captured["cmd"][-1] == host.tool_path(qc)
    assert captured["env"]["WINEPREFIX"] == str(prefix)
    assert compiled.mdl == mdl
    assert compiled.vvd is not None
    assert compiled.vtx is not None
    assert compiled.model_name == "player/avatar/avatar.mdl"


def test_compile_service_native_argv(monkeypatch, tmp_path: Path):
    qc = tmp_path / "avatar.qc"
    qc.write_text('$modelname "player/avatar/avatar.mdl"\n', encoding="utf-8")
    compiler = tmp_path / "studiomdl.exe"
    compiler.write_bytes(b"")
    game = tmp_path / "garrysmod"
    (game / "gameinfo.txt").parent.mkdir(parents=True, exist_ok=True)
    (game / "gameinfo.txt").write_text("GameInfo {}\n", encoding="utf-8")
    mdl = game / "models" / "player" / "avatar" / "avatar.mdl"
    mdl.parent.mkdir(parents=True)
    mdl.write_bytes(b"IDST")

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return CommandResult(argv=list(cmd), returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.services.compile.run_command", fake_run)
    monkeypatch.setattr("app.services.crowbar.studiomdl_exe", lambda: compiler)
    monkeypatch.setattr("app.services.compile.gmod_tools_root", lambda data: tmp_path)

    compiled = CompileService(WindowsToolHost(kind="native")).compile(qc)
    assert captured["cmd"][0] == str(compiler)
    assert captured["cmd"][1:4] == ["-game", str(game.resolve()), "-nop4"]
    assert captured["cmd"][-1] == str(qc.resolve())
    assert compiled.mdl == mdl
