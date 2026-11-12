"""The contact sheet operator. Every expected value is a decision of spec/12-contact-sheet-and-runbook.md (approved
by the user on 2026-11-12) or a comparison of two renders."""

import json
from array import array
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender import (
    appearance_collection,
    appearance_contact_sheet,
    appearance_preview,
    appearance_props,
)
from rsps_toolkit.formats.appearance_preset import AppearancePreset

POSE = json.loads((Path(__file__).parent.parent / "fixtures" / "animation149" / "walk" / "pose-male.json").read_text())
# Small cells keep the renders short. The spec's "Settled on approval" 1 sets Workbench and small cells for the tests.
CELL = (160, 240)
RENDER_SETTINGS = (
    "engine",
    "resolution_x",
    "resolution_y",
    "resolution_percentage",
    "filepath",
    "use_border",
    "use_stamp",
    "use_stamp_frame",
    "use_stamp_date",
    "use_stamp_camera",
    "stamp_font_size",
)


@pytest.fixture(autouse=True)
def registered(clean):
    for cls in (*appearance_props.classes, *appearance_contact_sheet.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    scene = bpy.context.scene
    assert scene is not None
    engine, frame = scene.render.engine, scene.frame_current
    settings = scene.render.image_settings
    media_type, file_format = settings.media_type, settings.file_format
    percentage, border = scene.render.resolution_percentage, scene.render.use_border
    scene.render.engine = "BLENDER_WORKBENCH"  # pyrefly: ignore[bad-assignment]
    yield
    settings.media_type, settings.file_format = media_type, file_format
    scene.render.resolution_percentage, scene.render.use_border = percentage, border
    # Save Preset saves the active player in place of the panel, so an active player left here fails the tests of
    # test_appearance_files.py, which run next.
    bpy.context.view_layer.objects.active = None  # pyrefly: ignore[missing-attribute]
    scene.render.engine = engine
    scene.frame_set(frame)
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_contact_sheet.classes)):
        bpy.utils.unregister_class(cls)


def player(cache):
    preset = AppearancePreset(149, 430, POSE["female"], tuple(POSE["equipment"]), tuple(POSE["colours"]))
    body, shading = appearance_preview.assemble_lit(preset, cache)
    collection = appearance_collection.build_collection(body, shading, preset, "Player")
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    return collection


# One pixel is four 32-bit floats: red, green, blue and alpha.
PIXEL = 16


def pixels(path):
    """The rows of the PNG from the top down. Each row is the bytes of its pixels."""
    image = bpy.data.images.load(str(path))
    width, height = image.size  # pyrefly: ignore[not-iterable]
    values = array("f", bytes(PIXEL * width * height))
    image.pixels.foreach_get(values)
    bpy.data.images.remove(image)
    data = values.tobytes()
    return [data[PIXEL * width * y : PIXEL * width * (y + 1)] for y in reversed(range(height))]


def size(image):
    return len(image[0]) // PIXEL, len(image)


def sheet(path, frames, views="front,right", cell=CELL):
    result = bpy.ops.rsps.contact_sheet(  # pyrefly: ignore[missing-attribute]
        filepath=str(path), frames=frames, views=views, cell_width=cell[0], cell_height=cell[1]
    )
    assert result == {"FINISHED"}
    return pixels(path)


def cells(image, cell=CELL):
    """The cells of a sheet as `cells[row][column]`. Each cell is its rows from the top down."""
    width, height = cell
    columns, rows = size(image)[0] // width, size(image)[1] // height
    return [
        [
            [row[PIXEL * width * column : PIXEL * width * (column + 1)] for row in image[height * r : height * (r + 1)]]
            for column in range(columns)
        ]
        for r in range(rows)
    ]


def drawn_columns(cell):
    """The columns of a cell that hold a pixel unlike the cell's top right pixel, which is background.

    Blender dithers a saved render, so two background pixels differ by a small amount.
    """
    rows = [memoryview(row).cast("f") for row in cell]
    background = rows[0][-4:]
    return [
        x
        for x in range(len(rows[0]) // 4)
        if any(abs(row[4 * x + channel] - background[channel]) > 0.02 for row in rows for channel in range(3))
    ]


def state():
    scene = bpy.context.scene
    assert scene is not None
    return {
        "render": {name: getattr(scene.render, name) for name in RENDER_SETTINGS},
        "format": (scene.render.image_settings.media_type, scene.render.image_settings.file_format),
        "camera": scene.camera,
        "frame": (scene.frame_current, scene.frame_subframe),
        "range": (scene.frame_start, scene.frame_end),
        "hidden": {obj.name: obj.hide_render for obj in bpy.data.objects},
        "cameras": sorted(camera.name for camera in bpy.data.cameras),
        "images": sorted(image.name for image in bpy.data.images),
    }


def test_the_operator_is_not_offered_without_an_active_player():
    assert not bpy.ops.rsps.contact_sheet.poll()  # pyrefly: ignore[missing-attribute]


def test_the_sheet_has_one_column_per_frame_and_one_row_per_view(cache, tmp_path):
    player(cache)
    image = sheet(tmp_path / "sheet.png", "1,2,3", "front,right,top,back")
    assert size(image) == (CELL[0] * 3, CELL[1] * 4)


def test_the_defaults_are_two_rows_of_cells_of_320_by_480(cache, tmp_path):
    player(cache)
    path = tmp_path / "sheet.png"
    assert bpy.ops.rsps.contact_sheet(filepath=str(path), frames="1") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert size(pixels(path)) == (320, 480 * 2)


def test_the_rows_are_the_views_in_the_order_given(cache, tmp_path):
    player(cache)
    front_right = cells(sheet(tmp_path / "a.png", "1", "front,right"))
    right_front = cells(sheet(tmp_path / "b.png", "1", "right,front"))
    assert front_right[0][0] != front_right[1][0]
    assert front_right[0][0] == right_front[1][0]
    assert front_right[1][0] == right_front[0][0]


def test_a_player_mesh_that_is_hidden_for_renders_is_in_the_sheet_and_stays_hidden(cache, tmp_path):
    collection = player(cache)
    shown = sheet(tmp_path / "shown.png", "1")
    mesh = appearance_collection.mesh_of(collection)
    mesh.hide_render = True
    assert sheet(tmp_path / "hidden.png", "1") == shown
    assert mesh.hide_render


def test_the_columns_are_the_frames_in_the_order_given(cache, tmp_path):
    collection = player(cache)
    rig = appearance_collection.armature_of(collection)
    rig.keyframe_insert("location", frame=1)
    rig.location.x += 300
    rig.keyframe_insert("location", frame=2)
    rows = slice(CELL[1] - 44)
    first, second = cells(sheet(tmp_path / "a.png", "1,2", "front"))[0]
    swapped_second, swapped_first = cells(sheet(tmp_path / "b.png", "2,1", "front"))[0]
    assert first[rows] != second[rows]
    assert first[rows] == swapped_first[rows]
    assert second[rows] == swapped_second[rows]


def test_only_the_active_player_is_in_the_sheet(cache, tmp_path):
    collection = player(cache)
    alone = sheet(tmp_path / "alone.png", "1")
    other = player(cache)
    appearance_collection.armature_of(other).location.x += 40
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    assert sheet(tmp_path / "both.png", "1") == alone


def test_two_frames_with_the_same_pose_differ_only_in_the_frame_number(cache, tmp_path):
    player(cache)
    first, second = cells(sheet(tmp_path / "sheet.png", "1,2", "front"))[0]
    changed = [y for y in range(CELL[1]) if first[y] != second[y]]
    # The frame number is in the lowest part of the cell, in letters of 22 pixels (feedback.py, the accepted layout).
    assert changed
    assert changed[0] >= CELL[1] - 2 * 22


def test_a_row_has_one_camera_so_a_player_that_moves_is_at_another_place_in_the_next_cell(cache, tmp_path):
    collection = player(cache)
    rig = appearance_collection.armature_of(collection)
    rig.keyframe_insert("location", frame=1)
    rig.location.x += 300
    rig.keyframe_insert("location", frame=2)
    first, second = cells(sheet(tmp_path / "sheet.png", "1,2", "front"))[0]
    # The stamp is in the lowest rows, so the player is read above them.
    here, there = drawn_columns(first[: CELL[1] - 44]), drawn_columns(second[: CELL[1] - 44])
    assert max(here) < min(there) or max(there) < min(here)


def test_the_operator_restores_everything_it_changes(cache, tmp_path):
    collection = player(cache)
    other = player(cache)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    appearance_collection.mesh_of(other).hide_render = True
    # Each setting gets a value that the operator does not set, so a setting that is not restored shows.
    scene = bpy.context.scene
    assert scene is not None
    scene.camera = bpy.data.objects.new("Scene Camera", bpy.data.cameras.new("Scene Camera"))
    scene.collection.objects.link(scene.camera)
    scene.render.image_settings.file_format = "JPEG"
    scene.render.resolution_percentage = 50
    scene.render.use_border = True
    scene.frame_set(7, subframe=0.5)
    before = state()
    sheet(tmp_path / "sheet.png", "1,2")
    assert state() == before


def test_a_file_without_a_render_result_image_gets_none(cache, tmp_path):
    player(cache)
    for image in list(bpy.data.images):
        if image.type == "RENDER_RESULT":
            bpy.data.images.remove(image)
    before = state()
    sheet(tmp_path / "sheet.png", "1")
    assert state() == before


def test_a_failed_render_restores_everything_and_writes_no_file(cache, tmp_path, monkeypatch):
    player(cache)
    renders = []

    def fail_on_the_second_cell(*args, **kwargs):
        renders.append(1)
        if len(renders) == 2:
            raise RuntimeError("the render failed")
        return real(*args, **kwargs)

    real = appearance_contact_sheet.render_cell
    monkeypatch.setattr(appearance_contact_sheet, "render_cell", fail_on_the_second_cell)
    before = state()
    path = tmp_path / "sheet.png"
    with pytest.raises(RuntimeError, match="the render failed"):
        bpy.ops.rsps.contact_sheet(filepath=str(path), frames="1,2", cell_width=CELL[0], cell_height=CELL[1])  # pyrefly: ignore[missing-attribute]
    assert state() == before
    assert not path.exists()


def test_the_player_still_reads_as_unedited(cache, tmp_path):
    collection = player(cache)
    assert not appearance_collection.is_edited(collection)
    sheet(tmp_path / "sheet.png", "1,2")
    assert not appearance_collection.is_edited(collection)


@pytest.mark.parametrize(
    ("properties", "named"),
    [
        ({"frames": ""}, "frames"),
        ({"frames": "1,,2"}, "frames"),
        ({"frames": "1,x,2"}, "'x'"),
        ({"frames": "1.5"}, "'1.5'"),
        ({"frames": "1", "views": ""}, "views"),
        ({"frames": "1", "views": "front,below"}, "'below'"),
    ],
)
def test_a_bad_value_is_refused_by_name_and_no_file_is_written(cache, tmp_path, properties, named):
    player(cache)
    path = tmp_path / "sheet.png"
    before = state()
    with pytest.raises(RuntimeError, match=named):
        bpy.ops.rsps.contact_sheet(filepath=str(path), **properties)  # pyrefly: ignore[missing-attribute]
    assert not path.exists()
    assert state() == before


def test_an_empty_file_path_is_refused(cache):
    player(cache)
    with pytest.raises(RuntimeError, match="file path"):
        bpy.ops.rsps.contact_sheet(frames="1")  # pyrefly: ignore[missing-attribute]


def test_a_player_without_a_mesh_is_refused(cache, tmp_path):
    collection = player(cache)
    rig = appearance_collection.armature_of(collection)
    for obj in [obj for obj in collection.objects if obj.type == "MESH"]:
        bpy.data.objects.remove(obj)
    bpy.context.view_layer.objects.active = rig  # pyrefly: ignore[missing-attribute]
    path = tmp_path / "sheet.png"
    with pytest.raises(RuntimeError, match="no mesh"):
        bpy.ops.rsps.contact_sheet(filepath=str(path), frames="1")  # pyrefly: ignore[missing-attribute]
    assert not path.exists()


def test_a_player_whose_meshes_have_no_vertex_is_refused(cache, tmp_path):
    collection = player(cache)
    for obj in collection.objects:
        if obj.type == "MESH":
            obj.data = bpy.data.meshes.new("Empty")
    path = tmp_path / "sheet.png"
    before = state()
    with pytest.raises(RuntimeError, match="no vertex"):
        bpy.ops.rsps.contact_sheet(filepath=str(path), frames="1")  # pyrefly: ignore[missing-attribute]
    assert state() == before
    assert not path.exists()
