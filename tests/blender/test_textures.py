import json
import shutil
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender.mesh import model_to_object
from rsps_toolkit.blender.preferences import first_texture, folder_in_setting
from rsps_toolkit.formats import decode

FIXTURES = Path(__file__).parent.parent / "fixtures"
TEXTURED = [FIXTURES / "models" / "osrs" / "135.dat", FIXTURES / "models" / "worn" / "7122.dat"]
# Copied from the Old School dump; fixture 135 uses texture 16.
TEXTURES = FIXTURES / "textures"


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    yield


@pytest.mark.parametrize("dat", TEXTURED, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_uv_layer_holds_runelite_uvs_with_v_flipped(dat: Path):
    # The expected UVs are RuneLite's (ModelReference.java). The client reads texel rows from v
    # (Graphics3D.rasterTextureAffineLine in the 2018 client), so v runs down the image, while Blender's image
    # origin is the bottom-left corner. Where RuneLite has NaN, see tests/unit/test_texture_uvs.py.
    ref = json.loads(dat.with_suffix(".json").read_text())
    model = decode(dat.read_bytes())

    mesh = model_to_object(model, dat.stem).data
    assert isinstance(mesh, bpy.types.Mesh)
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None
    flat = [0.0] * (2 * len(mesh.loops))
    uv_layer.data.foreach_get("uv", flat)

    for face, polygon in enumerate(mesh.polygons):
        us, vs = ref["face_texture_u"][face], ref["face_texture_v"][face]
        if us is None:
            continue
        got = flat[2 * polygon.loop_start : 2 * polygon.loop_start + 6]
        expected = [c for u, v in zip(us, vs, strict=True) for c in (u, 1 - v)]
        assert got == pytest.approx(expected, rel=1e-4, abs=1e-5), f"face {face}"


def test_first_texture_finds_id_png_in_the_first_folder_that_has_it(tmp_path: Path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    shutil.copy(TEXTURES / "16.png", second / "16.png")

    assert first_texture([first, second], 16) == second / "16.png"
    assert first_texture([first, second], 2) is None
    assert first_texture([tmp_path / "missing", second], 16) == second / "16.png"


def test_texture_folder_setting_starting_with_a_tilde_means_the_home_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A leading ~ names the home folder in the shell and in Python's os.path.expanduser, and users type paths that way.
    monkeypatch.setenv("HOME", str(tmp_path))

    assert folder_in_setting("~/textures") == tmp_path / "textures"


def test_textured_face_shows_its_png():
    model = decode(TEXTURED[0].read_bytes())
    texture = next(t for t in model.face_textures if t is not None)

    mesh = model_to_object(model, "textured", lambda i: first_texture([TEXTURES], i)).data
    assert isinstance(mesh, bpy.types.Mesh)

    images = [
        node.image.filepath
        for material in mesh.materials
        if material is not None and material.node_tree is not None
        for node in material.node_tree.nodes
        if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None
    ]
    assert str(TEXTURES / f"{texture}.png") in images


def test_missing_texture_shows_flat_magenta():
    # The user chose magenta so that missing textures stand out (ADR 0006).
    model = decode(TEXTURED[0].read_bytes())

    mesh = model_to_object(model, "missing", lambda i: None).data
    assert isinstance(mesh, bpy.types.Mesh)

    textured = [m for m in mesh.materials if m is not None and "rs_texture_id" in m]
    assert textured
    for material in textured:
        rgba = [0.0] * 4
        material.diffuse_color.foreach_get(rgba)
        assert rgba == pytest.approx([1.0, 0.0, 1.0, 1.0])
