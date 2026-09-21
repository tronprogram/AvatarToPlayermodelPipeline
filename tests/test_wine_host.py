"""Wine bottle discovery and validation."""

import plistlib
from pathlib import Path

from app.services.user_settings import UserSettings, save_settings
from app.services.wine_host import (
    WineCandidate,
    _whisky_identity,
    chosen_candidate,
    host_id,
    list_candidates,
    select_prefix,
    wine_ready,
)


def _bottle(root: Path, name: str) -> Path:
    prefix = root / name
    (prefix / "drive_c").mkdir(parents=True)
    return prefix


def _wine_bin(tmp_path: Path) -> Path:
    wine = tmp_path / "wine64"
    wine.write_text("", encoding="utf-8")
    wine.chmod(0o755)
    return wine


def _candidate(
    tmp_path: Path,
    name: str,
    wine: Path,
    *,
    version: str = "7.7",
    kind: str = "whisky",
) -> WineCandidate:
    return WineCandidate(
        kind=kind,  # type: ignore[arg-type]
        name=name,
        version=version,
        prefix=_bottle(tmp_path, name).resolve(),
        wine=wine,
    )


def test_host_id_normalizes_arch(monkeypatch):
    monkeypatch.setattr("app.services.wine_host.platform.system", lambda: "Darwin")
    monkeypatch.setattr("app.services.wine_host.platform.machine", lambda: "arm64")
    assert host_id() == "darwin-arm64"
    monkeypatch.setattr("app.services.wine_host.platform.machine", lambda: "x86_64")
    assert host_id() == "darwin-x86_64"


def test_whisky_label_includes_version_name_and_path(tmp_path: Path):
    prefix = _bottle(tmp_path, "D7DEAA45-E464-46A1-BB49-44F83D85431E")
    (prefix / "Metadata.plist").write_bytes(
        plistlib.dumps(
            {
                "info": {"name": "test"},
                "wineConfig": {
                    "wineVersion": {"major": 7, "minor": 7, "patch": 0},
                },
            }
        )
    )
    name, version = _whisky_identity(prefix)
    assert name == "test"
    assert version == "7.7"
    item = WineCandidate(
        kind="whisky",
        name=name,
        version=version,
        prefix=prefix,
        wine=None,
    )
    assert item.label == f"Whisky 7.7, Bottle test - {prefix}"


def test_wine_label_omits_bottle_name():
    item = WineCandidate(
        kind="wine",
        name="",
        version="9.22",
        prefix=Path("/home/me/.wine"),
        wine=None,
    )
    assert item.label == "Wine 9.22 - /home/me/.wine"


def test_list_candidates_names_whisky_bottles(tmp_path: Path, monkeypatch):
    bottles = tmp_path / "Bottles"
    first = _bottle(bottles, "aaa")
    second = _bottle(bottles, "bbb")
    (first / "Metadata.plist").write_bytes(
        plistlib.dumps(
            {
                "info": {"name": "test"},
                "wineConfig": {"wineVersion": {"major": 7, "minor": 7, "patch": 0}},
            }
        )
    )
    (second / "Metadata.plist").write_bytes(
        plistlib.dumps(
            {
                "info": {"name": "openmpt"},
                "wineConfig": {"wineVersion": {"major": 7, "minor": 7, "patch": 0}},
            }
        )
    )
    wine = _wine_bin(tmp_path)
    monkeypatch.setattr("app.services.wine_host.sys_darwin", lambda: True)
    monkeypatch.setattr("app.services.wine_host.is_windows", lambda: False)
    monkeypatch.setattr("app.services.wine_host._WHISKY_BOTTLE_ROOTS", (bottles,))
    monkeypatch.setattr("app.services.wine_host.whisky_wine", lambda: wine)
    monkeypatch.setattr("app.services.wine_host.find_wine", lambda: wine)
    monkeypatch.setattr("app.services.wine_host._CROSSOVER_BOTTLES", tmp_path / "no-cx")
    monkeypatch.setattr("app.services.wine_host.data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr("app.services.wine_host._launcher_version", lambda _launcher: "7.7")
    monkeypatch.delenv("WINEPREFIX", raising=False)
    found = list_candidates()
    labels = [item.label for item in found]
    assert any(item.prefix == first.resolve() for item in found)
    assert any(item.prefix == second.resolve() for item in found)
    assert any(label.startswith("Whisky 7.7, Bottle test - ") for label in labels)
    assert any(label.startswith("Whisky 7.7, Bottle openmpt - ") for label in labels)


def test_one_candidate_is_ready_without_override(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    save_settings(UserSettings(wine_prefix=""))
    wine = _wine_bin(tmp_path)
    candidate = _candidate(tmp_path, "only", wine)
    monkeypatch.setattr("app.services.wine_host.wine_is_required", lambda: True)
    monkeypatch.setattr("app.services.wine_host.list_candidates", lambda: (candidate,))
    assert wine_ready() is True
    assert chosen_candidate() == candidate


def test_two_candidates_need_a_choice(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.user_settings.data_dir", lambda: tmp_path)
    save_settings(UserSettings(wine_prefix=""))
    wine = _wine_bin(tmp_path)
    a = _candidate(tmp_path, "a", wine)
    b = _candidate(tmp_path, "b", wine)
    monkeypatch.setattr("app.services.wine_host.wine_is_required", lambda: True)
    monkeypatch.setattr("app.services.wine_host.list_candidates", lambda: (a, b))
    monkeypatch.setattr("app.services.wine_host.find_wine", lambda: wine)
    monkeypatch.setattr("app.services.wine_host.whisky_wine", lambda: wine)
    assert wine_ready() is False
    assert chosen_candidate() is None
    assert select_prefix(b.prefix) is None
    assert chosen_candidate() == b


def test_select_prefix_rejects_folder_without_drive_c(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert select_prefix(empty) is not None
