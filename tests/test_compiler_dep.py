from pathlib import Path
from zipfile import ZipFile

from app.services.deps.extract import extract_hlmvplusplus, extract_modified_compiler
from app.services.deps.detect import find_modified_compiler
from app.services.setup_inventory import DEFAULT_SELECTED, SETUP_TREE


def test_extract_promotes_modified_complier(tmp_path: Path):
    archive = tmp_path / "Gmod-Model-Port-Template-main.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr(
            "Gmod-Model-Port-Template-main/Modified Complier/bin/studiomdl.exe",
            b"mdl",
        )
        zf.writestr(
            "Gmod-Model-Port-Template-main/Proportion Trick/readme.txt",
            b"ok",
        )
    data = tmp_path / "data"
    extract_modified_compiler(archive, data)
    exe = data / "compiler" / "bin" / "studiomdl.exe"
    assert exe.is_file()
    assert exe.read_bytes() == b"mdl"
    assert find_modified_compiler(data) == exe


def test_extract_promotes_hlmvplusplus(tmp_path: Path):
    archive = tmp_path / "hammerplusplus_2013mp_build8871.zip"
    with ZipFile(archive, "w") as zf:
        zf.writestr("hammerplusplus_2013mp_build8871/bin/hlmvplusplus.exe", b"exe")
        zf.writestr("hammerplusplus_2013mp_build8871/bin/hlmvplusplus.dll", b"dll")
    compiler_bin = tmp_path / "data" / "compiler" / "bin"
    compiler_bin.mkdir(parents=True)
    data = tmp_path / "data"
    extract_hlmvplusplus(archive, data)
    bundled = data / "hlmvplusplus" / "hlmvplusplus.exe"
    assert bundled.is_file()
    assert bundled.read_bytes() == b"exe"
    assert (compiler_bin / "hlmvplusplus.exe").read_bytes() == b"exe"
    assert (compiler_bin / "hlmvplusplus.dll").read_bytes() == b"dll"


def test_default_setup_requires_compiler_not_2013():
    assert "compiler" in DEFAULT_SELECTED
    assert "hlmvplusplus" in DEFAULT_SELECTED
    assert "sdk2013" not in DEFAULT_SELECTED
    labels = {item_id: label for item_id, label, _parent in SETUP_TREE}
    assert "compile" in labels["compiler"].lower()
    assert "HLMV++" in labels["hlmvplusplus"]
    assert "sdk2013" not in labels
