import gzip
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import bpy
import pytest
from js5_builder import REGION_FIXTURES, build_region_cache
from runelite_json import load_locs, load_overlays, load_underlays

import rsps_toolkit.blender as addon
from rsps_toolkit.blender import import_item, preferences, region_import, region_scenery, region_terrain, rs_layers
from rsps_toolkit.blender.face_materials import srgb_to_linear, texture_image
from rsps_toolkit.blender.mesh import matching_set_aside_faces
from rsps_toolkit.formats import decode, face_colour_to_rgb
from rsps_toolkit.formats.cache_profile import SET_CACHE_FOLDER
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.loc_definition import read_locs
from rsps_toolkit.formats.region import (
    AREA_SIZE,
    EMPTY_TILE,
    LEVELS,
    Placement,
    Terrain,
    Tile,
    load_landscape,
    load_terrain,
)
from rsps_toolkit.formats.region_colours import HIDDEN
from rsps_toolkit.formats.region_placement import place_scenery
from rsps_toolkit.formats.region_shapes import Corner, TilePoint, tile_triangles
from rsps_toolkit.formats.sprite import decode_sprites
from rsps_toolkit.formats.texture import SIZE, decode_texture, texture_pixels

FLOORS = REGION_FIXTURES / "floors.json"
UNDERLAYS = load_underlays(FLOORS)
OVERLAYS = load_overlays(FLOORS)
BRIGHTNESS = 0.8
CORNERS = list(Corner)


@pytest.fixture(scope="module")
def terrain(tmp_path_factory) -> Terrain:
    folder = tmp_path_factory.mktemp("cache")
    build_region_cache(folder)
    return load_terrain(Js5Store(folder), 48, 50)


@pytest.fixture(autouse=True)
def empty_file():
    bpy.ops.wm.read_homefile(use_empty=True)


def decoded_image(texture_id: int) -> bpy.types.Image:
    texture = decode_texture(texture_id, (REGION_FIXTURES / "textures" / f"{texture_id}.dat").read_bytes())
    sprites = {
        sprite_id: decode_sprites(sprite_id, (REGION_FIXTURES / "sprites" / f"{sprite_id}.dat").read_bytes())
        for sprite_id in texture.sprites
    }
    return texture_image(texture_id, texture_pixels(texture, sprites, BRIGHTNESS), texture.opaque)


def terrain_of_48_50(terrain: Terrain) -> bpy.types.Object:
    # Overlays of 48_50 use textures 1 and 3 (floors.json).
    images = {texture: decoded_image(texture) for texture in (1, 3)}
    return region_terrain.terrain_object("Terrain 48_50", terrain, UNDERLAYS, OVERLAYS, images, BRIGHTNESS)


def made_terrain(tiles: dict[tuple[int, int], Tile]) -> Terrain:
    """Region 48_50 with height 0 everywhere, no underlay and no overlay, except the tiles given by their region x and y."""
    columns = [[[EMPTY_TILE] * AREA_SIZE for _ in range(AREA_SIZE)] for _ in range(LEVELS)]
    for (x, y), tile in tiles.items():
        columns[0][x + 64][y + 64] = tile
    return Terrain(48, 50, tuple(tuple(tuple(column) for column in level) for level in columns), ())


def mesh_of(obj: bpy.types.Object) -> bpy.types.Mesh:
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


type Point = tuple[float, float, float]


def faces_by_corners(obj: bpy.types.Object) -> dict[tuple[Point, ...], int]:
    """Each face of the mesh by the positions of its corners in loop order, rounded to whole game units."""
    mesh = mesh_of(obj)
    faces = {}
    for polygon in mesh.polygons:
        corners = []
        for i in range(polygon.loop_total):
            x, y, z = mesh.vertices[mesh.loops[polygon.loop_start + i].vertex_index].co
            corners.append((float(round(x)), float(round(y)), float(round(z))))
        faces[tuple(corners)] = polygon.index
    return faces


def point_position(terrain: Terrain, x: int, y: int, point: TilePoint) -> Point:
    """The Blender position of a tile point. The south-west corner of the region is at (0, 0, 0) (spec 35, decision 5),
    one game unit is one Blender unit, and the height points down in the game. A point between two corners has the sum
    of their heights shifted right by 1 (`SceneTileModel.java` lines 124 to 220)."""
    heights = [terrain.tile(0, x + corner.value[0], y + corner.value[1]).height for corner in point.corners]
    height = heights[0] if len(heights) == 1 else (heights[0] + heights[1]) >> 1
    return (x * 128 + point.x, y * 128 + point.y, -height)


def point_value(values: tuple[int, int, int, int], point: TilePoint) -> int:
    picked = [values[CORNERS.index(corner)] for corner in point.corners]
    return picked[0] if len(picked) == 1 else (picked[0] + picked[1]) >> 1


def shown_colour(colour: int) -> tuple[float, float, float]:
    red, green, blue = face_colour_to_rgb(colour, BRIGHTNESS)
    return srgb_to_linear(red / 255), srgb_to_linear(green / 255), srgb_to_linear(blue / 255)


def shown_shade(light: int) -> tuple[float, float, float]:
    # The textured rasteriser multiplies each channel of the texel by the light shifted left by 9 and then right by 16,
    # so by the light over 128 (`Graphics3D.java` line 2532 and line 3295 of the 2018 client).
    grey = srgb_to_linear(light / 128)
    return grey, grey, grey


def corner_colours(obj: bpy.types.Object, face: int) -> list[tuple[float, float, float]]:
    mesh = mesh_of(obj)
    attribute = mesh.color_attributes[region_terrain.TERRAIN_COLOUR]
    assert isinstance(attribute, bpy.types.FloatColorAttribute)
    # The stubs do not support indexing a colour array, so the colours are read with foreach_get.
    flat = [0.0] * (len(mesh.loops) * 4)
    attribute.data.foreach_get("color", flat)
    polygon = mesh.polygons[face]
    loops = range(polygon.loop_start, polygon.loop_start + polygon.loop_total)
    return [(flat[4 * loop], flat[4 * loop + 1], flat[4 * loop + 2]) for loop in loops]


def face_material(obj: bpy.types.Object, face: int) -> bpy.types.Material:
    material = mesh_of(obj).materials[mesh_of(obj).polygons[face].material_index]
    assert material is not None
    return material


def material_image(material: bpy.types.Material) -> bpy.types.Image | None:
    tree = material.node_tree
    assert tree is not None
    images = [node.image for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeTexImage)]
    assert len(images) <= 1
    return images[0] if images else None


def corner_uvs(obj: bpy.types.Object, face: int) -> list[tuple[float, float]]:
    mesh = mesh_of(obj)
    layer = mesh.uv_layers.active
    assert layer is not None
    polygon = mesh.polygons[face]
    uvs = []
    for i in range(polygon.loop_total):
        u, v = layer.data[polygon.loop_start + i].uv
        uvs.append((round(u, 5), round(v, 5)))
    return uvs


def test_every_tile_of_48_50_has_the_triangles_of_its_shape_and_nothing_else(terrain):
    # Region 48_50 has no tile without an underlay and an overlay and no hidden overlay, so every tile draws all the
    # triangles of its shape (`region_shapes.tile_triangles`, which follows `SceneTileModel.java` lines 76 to 77).
    obj = terrain_of_48_50(terrain)

    expected = {
        tuple(point_position(terrain, x, y, point) for point in triangle.points)
        for x in range(64)
        for y in range(64)
        for triangle in tile_triangles(terrain.tile(0, x, y))
    }
    assert set(faces_by_corners(obj)) == expected
    assert len(mesh_of(obj).polygons) == len(expected)


def test_tiles_share_the_vertices_at_their_common_corners(terrain):
    # The 65 by 65 corners of the region, and the points inside or between tiles that their shapes add.
    obj = terrain_of_48_50(terrain)

    mesh = mesh_of(obj)
    positions = [tuple(round(c) for c in vertex.co) for vertex in mesh.vertices]
    assert len(positions) == len(set(positions))
    corner = (0, 0, -terrain.tile(0, 0, 0).height)
    assert corner in positions


# The colours of tiles of 48_50 at their corners from the lines of the 2018 client, copied from TILE_COLOURS in
# `tests/unit/test_region_colours.py`, in the order south-west, south-east, north-east, north-west: the underlay colours,
# then the overlay colours or None. The overlay of tiles (0, 0) and (60, 3) has texture 1, so its colours are the light.
CLIENT_COLOURS = {
    (0, 0): ((HIDDEN,) * 4, (84, 84, 84, 84)),
    (0, 44): ((8851, 8854, 8857, 8853), None),
    (2, 47): ((11025, 11023, 11024, 11023), (24, 21, 23, 21)),
    (11, 56): ((11027,) * 4, (2457,) * 4),
    (60, 3): ((11919, 11919, 11930, 11924), (84, 84, 126, 112)),
    (63, 63): ((16149, 16146, 16146, 16147), None),
}
TEXTURED = {(0, 0), (60, 3)}


@pytest.mark.parametrize(("x", "y"), CLIENT_COLOURS)
def test_each_face_corner_of_a_tile_shows_the_lit_colour_of_the_client(terrain, x, y):
    obj = terrain_of_48_50(terrain)
    faces = faces_by_corners(obj)
    underlay, overlay = CLIENT_COLOURS[(x, y)]

    for triangle in tile_triangles(terrain.tile(0, x, y)):
        values = overlay if triangle.overlay else underlay
        assert values is not None
        if values[0] == HIDDEN:
            continue
        face = faces[tuple(point_position(terrain, x, y, point) for point in triangle.points)]
        textured = triangle.overlay and (x, y) in TEXTURED
        shown = shown_shade if textured else shown_colour
        expected = [channel for point in triangle.points for channel in shown(point_value(values, point))]
        actual = [channel for colour in corner_colours(obj, face) for channel in colour]
        assert actual == pytest.approx(expected, abs=1e-6)


def test_the_underlay_part_of_a_tile_with_no_underlay_is_not_drawn(terrain):
    # Tile (0, 0) has overlay 6 with the stored shape 0 and no underlay. Its underlay colours are hidden (`class16.java`
    # line 167). The client draws the stored shape 0 as two overlay triangles (`Region.java` lines 344 to 345), so both
    # are drawn and textured.
    obj = terrain_of_48_50(terrain)
    faces = faces_by_corners(obj)
    tile = terrain.tile(0, 0, 0)

    assert tile.underlay == 0
    drawn = [faces[tuple(point_position(terrain, 0, 0, p) for p in t.points)] for t in tile_triangles(tile)]
    assert len(drawn) == 2
    assert all(material_image(face_material(obj, face)) is not None for face in drawn)


def test_a_tile_with_no_underlay_and_no_overlay_has_no_faces():
    # `class24.java` line 189 does not call `addTile` for it. Region 48_50 has no such tile, so the terrain is made for
    # the test: tile (10, 10) has underlay 48, and every other tile has nothing.
    terrain = made_terrain({(10, 10): Tile(0, 0, 48, 0, 0, 0)})

    obj = region_terrain.terrain_object("Terrain", terrain, UNDERLAYS, OVERLAYS, {}, BRIGHTNESS)

    centres = {(int(p.center.x) // 128, int(p.center.y) // 128) for p in mesh_of(obj).polygons}
    assert centres == {(10, 10)}
    assert len(mesh_of(obj).polygons) == 2


def test_the_hidden_overlay_part_of_a_tile_is_not_drawn():
    # Overlay 42 is definition 41, with colour 0xFF00FF (floors.json), which `class24.java` lines 252 to 255 hide. Shape 2
    # (stored shape 1) at rotation 0 has an underlay triangle and an overlay triangle (`SceneTileModel.java` line 77).
    # Region 48_50 has no hidden overlay, so the terrain is made for the test.
    tile = Tile(0, 0, 48, 42, 1, 0)
    terrain = made_terrain({(10, 10): tile})

    obj = region_terrain.terrain_object("Terrain", terrain, UNDERLAYS, OVERLAYS, {}, BRIGHTNESS)

    (underlay,) = [t for t in tile_triangles(tile) if not t.overlay]
    assert set(faces_by_corners(obj)) == {tuple(point_position(terrain, 10, 10, p) for p in underlay.points)}


def test_a_textured_overlay_uses_the_decoded_image(terrain):
    obj = terrain_of_48_50(terrain)
    faces = faces_by_corners(obj)

    for (x, y), texture in (((0, 0), 1), ((60, 3), 1)):
        for triangle in tile_triangles(terrain.tile(0, x, y)):
            face = faces[tuple(point_position(terrain, x, y, point) for point in triangle.points)]
            image = material_image(face_material(obj, face))
            if triangle.overlay:
                assert image is not None
                assert image.name == f"RS_Texture_{texture}"
            else:
                assert image is None


def test_the_texture_of_a_flat_tile_spans_the_tile_from_its_south_west_corner(terrain):
    # On a tile whose 4 corner heights are equal, the client maps the texture of every triangle with the south-west
    # corner as P, the south-east corner as M and the north-west corner as N (`Region.java` lines 1856 to 1857 and 1883,
    # and 1958 to 1959). P is texel (0, 0), the first texel of the top row, which is UV (0, 1) in Blender. Tile (0, 0) of
    # 48_50 is flat and textured.
    obj = terrain_of_48_50(terrain)
    faces = faces_by_corners(obj)
    corner_uv = {(0, 0): (0.0, 1.0), (128, 0): (1.0, 1.0), (128, 128): (1.0, 0.0), (0, 128): (0.0, 0.0)}

    for triangle in tile_triangles(terrain.tile(0, 0, 0)):
        face = faces[tuple(point_position(terrain, 0, 0, point) for point in triangle.points)]
        assert corner_uvs(obj, face) == [corner_uv[(point.x, point.y)] for point in triangle.points]


def test_the_texture_of_a_sloped_tile_spans_each_triangle_from_its_first_point(terrain):
    # On a tile whose corner heights differ, the client maps the texture of each triangle with its own points as P, M
    # and N, in the order that it draws them (`Region.java` lines 1858 to 1859 and 1883, and 1960 to 1961). Tile (8, 5)
    # of 48_50 is sloped, with shape 3 and texture 1.
    obj = terrain_of_48_50(terrain)
    faces = faces_by_corners(obj)
    tile = terrain.tile(0, 8, 5)
    heights = {terrain.tile(0, 8 + dx, 5 + dy).height for dx, dy in (corner.value for corner in Corner)}
    assert len(heights) > 1

    overlay = [t for t in tile_triangles(tile) if t.overlay]
    assert overlay
    for triangle in overlay:
        face = faces[tuple(point_position(terrain, 8, 5, point) for point in triangle.points)]
        assert corner_uvs(obj, face) == [(0.0, 1.0), (1.0, 1.0), (0.0, 0.0)]


def test_the_terrain_mesh_stores_no_game_values(terrain):
    obj = terrain_of_48_50(terrain)

    mesh = mesh_of(obj)
    assert not obj.keys()
    assert not mesh.keys()
    assert all(not material.keys() for material in mesh.materials if material is not None)
    assert {attribute.name for attribute in mesh.attributes if not attribute.is_internal} <= {
        region_terrain.TERRAIN_COLOUR,
        region_terrain.UV_MAP,
        "position",
        "sharp_face",
        "material_index",
    }


def surface_links(material: bpy.types.Material) -> set[tuple[str, str, str, str]]:
    tree = material.node_tree
    assert tree is not None
    return {
        (link.from_node.bl_idname, link.from_socket.name, link.to_node.bl_idname, link.to_socket.name)
        for link in tree.links
        if link.from_node and link.to_node and link.from_socket and link.to_socket
    }


def test_the_terrain_materials_are_unshaded_hide_back_faces_and_leave_transparent_texels_out(terrain):
    # The owner chose on 2026-11-14 that the terrain shows the client's lit colours unshaded, hides the back of each
    # face, and does not draw a transparent texel (issue 47, Decisions).
    obj = terrain_of_48_50(terrain)

    colour, *textured = [material for material in mesh_of(obj).materials if material is not None]
    assert len(textured) == 2
    for material in (colour, *textured):
        assert material.use_backface_culling
        tree = material.node_tree
        assert tree is not None
        assert not [node for node in tree.nodes if node.type == "BSDF_PRINCIPLED"]
    assert ("ShaderNodeEmission", "Emission", "ShaderNodeOutputMaterial", "Surface") in surface_links(colour)
    for material in textured:
        # The client reads one texel for each pixel and does not blend it with the texels next to it (`Graphics3D.java`
        # line 3294).
        tree = material.node_tree
        assert tree is not None
        (texels,) = [node for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeTexImage)]
        assert texels.interpolation == "Closest"
        links = surface_links(material)
        assert ("ShaderNodeTexImage", "Alpha", "ShaderNodeMixShader", "Factor") in links
        assert ("ShaderNodeBsdfTransparent", "BSDF", "ShaderNodeMixShader", "Shader") in links
        assert ("ShaderNodeEmission", "Emission", "ShaderNodeMixShader", "Shader") in links
        assert ("ShaderNodeMixShader", "Shader", "ShaderNodeOutputMaterial", "Surface") in links


def test_a_terrain_that_names_a_floor_definition_the_cache_lacks_is_refused():
    # The client would fail to look up the definition. Tile (10, 10) names underlay 48, which is definition 47.
    terrain = made_terrain({(10, 10): Tile(0, 0, 48, 0, 0, 0)})

    with pytest.raises(region_import.RefusalError, match=r"no underlay 47, which tile \(10, 10\)"):
        region_import._check_floors(terrain, {}, OVERLAYS)


@pytest.mark.parametrize(("x", "y"), [(-4, -4), (68, 68)])
def test_a_missing_underlay_at_the_edge_of_the_blend_is_refused(x, y):
    # The blend of tile (x, y) reads the underlays from x - 4 to x + 5 (`class24.java` lines 119 to 216, spec 35), so the
    # tiles of the region read them from -4 to 68.
    terrain = made_terrain({(x, y): Tile(0, 0, 48, 0, 0, 0)})

    with pytest.raises(region_import.RefusalError, match=rf"no underlay 47, which tile \({x}, {y}\)"):
        region_import._check_floors(terrain, {}, OVERLAYS)


@pytest.mark.parametrize(("x", "y"), [(-5, 10), (69, 10)])
def test_a_missing_underlay_outside_the_blend_is_not_refused(x, y):
    terrain = made_terrain({(x, y): Tile(0, 0, 48, 0, 0, 0)})

    region_import._check_floors(terrain, {}, OVERLAYS)


def test_a_missing_overlay_on_a_tile_of_the_region_is_refused():
    # Tile (10, 10) names overlay 42, which is definition 41.
    terrain = made_terrain({(10, 10): Tile(0, 0, 48, 42, 1, 0)})

    with pytest.raises(region_import.RefusalError, match=r"no overlay 41, which tile \(10, 10\)"):
        region_import._check_floors(terrain, UNDERLAYS, {})


def test_a_missing_overlay_outside_the_region_is_not_refused():
    # The import draws only the tiles of the region, so only they read their overlays (`region_colours.tile_colours`).
    # The underlay blend reads no overlay.
    terrain = made_terrain({(-1, 10): Tile(0, 0, 48, 42, 1, 0), (64, 10): Tile(0, 0, 48, 42, 1, 0)})

    region_import._check_floors(terrain, UNDERLAYS, {})


SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
needs_snapshot_430 = pytest.mark.skipif(
    not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder"
)


@pytest.fixture
def operator_registered():
    for cls in region_import.classes:
        bpy.utils.register_class(cls)
    yield
    for cls in reversed(region_import.classes):
        bpy.utils.unregister_class(cls)


@pytest.fixture
def snapshot_430(monkeypatch, operator_registered):
    monkeypatch.setattr(preferences, "cache_folder", lambda: SNAPSHOT_430)


def keyless_cache(folder: Path, **groups) -> Path:
    """A cache folder in `folder` with the groups that `build_region_cache` writes, and a keys folder next to it with no
    key file. The landscape then has no placements (`GLOSSARY.md`, Landscape keys), so the import needs no loc models,
    which `tests/fixtures/region/` does not hold."""
    cache = folder / "cache"
    build_region_cache(cache, **groups)
    (folder / "keys").mkdir()
    return cache


@pytest.fixture
def fixture_cache(monkeypatch, operator_registered, tmp_path):
    # The groups of snapshot 430 that the import of 48_50 reads, from `tests/fixtures/region/`, so the test needs no real
    # cache.
    cache = keyless_cache(tmp_path, definitions=True)
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)


def import_region(x: int = 48, y: int = 50) -> set[str]:
    # The stubs only list Blender's own operators.
    return bpy.ops.import_scene.rs_region(region_x=x, region_y=y)  # pyrefly: ignore[missing-attribute]


def region_collections() -> list[bpy.types.Collection]:
    scene = bpy.context.scene
    assert scene is not None
    return [c for c in scene.collection.children if c.name.startswith("Region 48_50")]


@needs_snapshot_430
def test_the_operator_imports_the_terrain_of_48_50_into_its_own_collection(snapshot_430):
    assert import_region() == {"FINISHED"}

    (region,) = region_collections()
    assert region.name == "Region 48_50"
    assert [obj.name for obj in region.objects] == ["Terrain 48_50"]
    (scenery,) = region.children
    assert scenery.name == "Scenery 48_50"
    assert not scenery.children
    terrain = load_terrain(Js5Store(SNAPSHOT_430), 48, 50)
    expected = sum(len(tile_triangles(terrain.tile(0, x, y))) for x in range(64) for y in range(64))
    assert len(mesh_of(region.objects[0]).polygons) == expected


def test_one_undo_removes_the_whole_import(fixture_cache):
    # Background Blender pushes undo states only when asked, so the test pushes one before and after the operator. In
    # the user interface, Blender pushes the state after the operator only when it has the UNDO option.
    assert "UNDO" in region_import.RS_OT_import_region.bl_options
    bpy.ops.ed.undo_push(message="Before the import")
    import_region()
    bpy.ops.ed.undo_push(message="Region imported")
    assert region_collections()

    bpy.ops.ed.undo()

    assert not region_collections()
    assert not [obj for obj in bpy.data.objects if obj.name.startswith("Terrain")]


def test_a_second_import_makes_a_second_copy(fixture_cache):
    import_region()
    import_region()

    first, second = sorted(region_collections(), key=lambda c: c.name)
    assert (first.name, second.name) == ("Region 48_50", "Region 48_50.001")
    assert first.objects[0].data != second.objects[0].data


def test_a_failure_while_building_leaves_nothing_behind(fixture_cache, monkeypatch):
    def fail(*args):
        raise ValueError("The build failed")

    monkeypatch.setattr(region_import, "terrain_object", fail)

    with pytest.raises(RuntimeError, match="The build failed"):
        import_region()
    assert not bpy.data.collections
    assert not bpy.data.objects
    assert not bpy.data.meshes
    assert not bpy.data.materials
    assert not bpy.data.images


def test_without_a_cache_folder_the_operator_stops_with_the_message_of_the_other_cache_operators(
    monkeypatch, operator_registered
):
    monkeypatch.setattr(preferences, "cache_folder", lambda: None)

    with pytest.raises(RuntimeError, match=re.escape(SET_CACHE_FOLDER)):
        import_region()
    assert not bpy.data.collections
    assert not bpy.data.objects


def test_a_region_whose_terrain_the_cache_lacks_is_refused(monkeypatch, operator_registered, tmp_path):
    # The owner chose on 2026-11-14 that the import refuses a region whose own terrain group the cache lacks (issue 47,
    # Decisions). The cache holds the 8 neighbours of 48_50 but not 48_50 itself.
    cache = keyless_cache(
        tmp_path, terrains=tuple(f"m{x}_{y}" for x in (47, 48, 49) for y in (49, 50, 51) if (x, y) != (48, 50))
    )
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)

    with pytest.raises(RuntimeError, match="The cache has no terrain for region 48_50"):
        import_region()
    assert not bpy.data.collections
    assert not bpy.data.objects


def test_an_overlay_texture_that_the_cache_lacks_stops_the_import(monkeypatch, operator_registered, tmp_path):
    # The owner chose on 2026-11-14 that a texture id that index 9 lacks stops the import with a message (issue 47,
    # Decisions). The overlays of 48_50 use textures 1 and 3 (floors.json), and the cache leaves out texture 1.
    cache = keyless_cache(tmp_path, definitions=True, textures_left_out=(1,))
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)

    with pytest.raises(RuntimeError, match="Group 0 of index 9 of the cache has no texture 1"):
        import_region()
    assert not bpy.data.collections
    assert not bpy.data.objects
    assert not bpy.data.images


@needs_snapshot_430
def test_the_texture_materials_read_decoded_images_not_the_texture_folder(snapshot_430, monkeypatch, tmp_path):
    # A texture folder of wrong PNGs: every texel black.
    wrong = bpy.data.images.new("wrong", 128, 128)
    wrong.filepath_raw = str(tmp_path / "1.png")
    wrong.file_format = "PNG"
    wrong.save()
    bpy.data.images.remove(wrong)
    monkeypatch.setattr(preferences, "texture_folders", lambda: [tmp_path])

    import_region()

    (region,) = region_collections()
    images = {
        image.name: image
        for material in mesh_of(region.objects[0]).materials
        if material is not None
        for image in [material_image(material)]
        if image is not None
    }
    assert set(images) == {"RS_Texture_1", "RS_Texture_3"}
    for texture_id in (1, 3):
        image = images[f"RS_Texture_{texture_id}"]
        assert image.packed_file is not None
        expected = [(pixel >> 16, pixel >> 8 & 0xFF, pixel & 0xFF) for pixel in reference_pixels(texture_id)]
        assert [rgba[:3] for rgba in rgba_from_the_top(image)] == expected


LANDSCAPE_ROWS = json.loads((REGION_FIXTURES / "landscape.json").read_text())
"""RuneLite's `LocationsLoader` reading of the landscape of 48_50, in the order of the file."""
LOC_ROWS = {row["id"]: row for row in json.loads((REGION_FIXTURES / "locs.json").read_text())}
"""RuneLite's `ObjectLoader` reading of the locs of the placements of 48_50 and of their impostors."""


def reference_shown_loc(loc_id: int) -> int:
    """The loc that a placement of `loc_id` shows, from the reference rows: `ObjectComposition.getImpostor` (lines 830 to
    845) takes the impostor for the value 0 of the varbit or varp, and the last impostor when the loc has neither."""
    row = LOC_ROWS[loc_id]
    impostors = row["configChangeDest"]
    if impostors is None:
        return loc_id
    value = 0 if row["varbitID"] != -1 or row["varpID"] != -1 else -1
    return impostors[value] if 0 <= value < len(impostors) - 1 else impostors[-1]


def reference_model(loc_id: int, model_type: int) -> tuple[int, ...] | None:
    """The models that `ObjectComposition.getModel` (lines 694 to 751) shows for a loc and a model type, from the
    reference rows. A loc without types shows all its models, only for type 10."""
    row = LOC_ROWS[loc_id]
    models, types = row["objectModels"] or [], row["objectTypes"]
    if types is None:
        return tuple(models) if model_type == 10 and models else None
    return (models[types.index(model_type)],) if model_type in types else None


type ReferenceKey = tuple[tuple[int, ...], ...]
RECOLOUR_FIELDS = ("recolorToFind", "recolorToReplace", "retextureToFind", "textureToReplace")


def reference_scenery() -> tuple[list[tuple[str, ReferenceKey, bool]], int]:
    """Each scenery object that the import of 48_50 makes, from the reference rows, and the count of the placements that
    show nothing. An object is its name, the models, recolours and retextures that it shows, and whether its loc is
    contoured.

    A wall decoration asks for type 4 and an object of type 11 for type 10 (`PacketBuffer.java` lines 212 to 503). A
    wall of type 2 and a wall decoration of type 8 ask twice with the same type (`Region.java` from line 1360). The owner
    chose on 2026-11-14 that each model is one object, and that the second is named with ` part 2` (issue 49,
    Decisions)."""
    objects: list[tuple[str, ReferenceKey, bool]] = []
    nothing = 0
    for row in LANDSCAPE_ROWS:
        if row["level"] != 0:
            continue
        shown = reference_shown_loc(row["id"])
        loc_type = row["type"]
        model_type = 4 if 4 <= loc_type <= 8 else 10 if loc_type == 11 else loc_type
        models = None if shown == -1 else reference_model(shown, model_type)
        if models is None:
            nothing += 1
            continue
        loc = LOC_ROWS[shown]
        key = (models, *(tuple(loc[field] or ()) for field in RECOLOUR_FIELDS))
        contoured = loc["contouredGround"] != -1
        name = f"Loc {row['id']} at {row['x']}_{row['y']}"
        objects.append((name, key, contoured))
        if loc_type in (2, 8):
            objects.append((f"{name} part 2", key, contoured))
    return objects, nothing


def scenery_of_48_50() -> bpy.types.Collection:
    (region,) = region_collections()
    (scenery,) = region.children
    return scenery


def without_number(name: str) -> str:
    """The name without the `.001` that Blender adds when the name is taken."""
    return re.sub(r"\.\d{3}$", "", name)


def scenery_object(name: str) -> bpy.types.Object:
    (obj,) = [obj for obj in scenery_of_48_50().objects if obj.name == name]
    return obj


@needs_snapshot_430
def test_the_import_of_48_50_makes_one_object_for_each_model_that_a_level_0_placement_shows(snapshot_430):
    started = time.perf_counter()
    import_region()
    print(f"The import of 48_50 took {time.perf_counter() - started:.1f} seconds")

    objects = scenery_of_48_50().objects
    assert Counter(without_number(obj.name) for obj in objects) == Counter(
        name for name, _, _ in reference_scenery()[0]
    )
    assert all(obj.type == "MESH" for obj in objects)


@needs_snapshot_430
def test_the_import_counts_the_placements_and_meshes_that_it_made(snapshot_430):
    scene = bpy.context.scene
    assert scene is not None
    region, counts = region_import.import_region(scene.collection, SNAPSHOT_430, 48, 50, BRIGHTNESS)

    objects, nothing = reference_scenery()
    (scenery,) = region.children
    own = {mesh_of(obj) for obj in scenery.objects if without_number(mesh_of(obj).name) == without_number(obj.name)}
    shared = {mesh_of(obj) for obj in scenery.objects} - own
    assert counts.placements == sum(1 for row in LANDSCAPE_ROWS if row["level"] == 0)
    assert counts.shown_nothing == nothing
    assert counts.placements_made == counts.placements - nothing
    assert counts.objects == len(objects) == len(scenery.objects)
    assert counts.own_meshes == len(own)
    assert counts.shared_meshes == len(shared)
    assert all(mesh.users == 1 for mesh in own)


@needs_snapshot_430
def test_objects_of_locs_that_are_not_contoured_share_a_mesh_exactly_when_they_show_the_same_models_and_colours(
    snapshot_430,
):
    # A loc that is not contoured shares its mesh unless Blender cannot hold its transform, which needs a scale that is
    # not 128 (`region_contour`), and no loc of 48_50 is scaled (spec 35). A name that two objects have is left out,
    # because Blender numbers the second.
    import_region()

    objects, _ = reference_scenery()
    names = Counter(name for name, _, _ in objects)
    keys = {name: key for name, key, contoured in objects if not contoured and names[name] == 1}
    mesh_by_key: dict[ReferenceKey, bpy.types.Mesh] = {}
    for name, key in keys.items():
        mesh = mesh_of(scenery_object(name))
        assert mesh_by_key.setdefault(key, mesh) is mesh, name
    assert len(set(mesh_by_key.values())) == len(mesh_by_key)


def test_a_placement_that_shows_nothing_makes_no_object_and_is_counted():
    # locs.json: loc 83 has no model for type 10, so a placement of type 10 shows nothing.
    locs = load_locs(REGION_FIXTURES / "locs.json")
    placement = Placement(83, 0, 5, 5, 10, 0)
    placed = place_scenery([placement], locs, lambda x, y: 0)
    collection = bpy.data.collections.new("Scenery")

    counts = region_scenery.scenery_objects(collection, placed, locs, {}, {}, lambda x, y: 0, BRIGHTNESS)

    assert not collection.objects
    assert (counts.placements, counts.placements_made, counts.objects, counts.shown_nothing) == (1, 0, 0, 1)


@needs_snapshot_430
def test_an_object_with_a_shared_mesh_holds_the_transform_of_its_placement(snapshot_430):
    # The transform rules are in `formats/region_placement.py` and its tests. Loc 84 at (16, 46) is a wall of type 2, so
    # it has two models, and the first is mirrored. Another placement shares the mesh of the first.
    import_region()

    store = Js5Store(SNAPSHOT_430)
    terrain = load_terrain(store, 48, 50)
    placements = [p for p in load_landscape(store, 48, 50).placements if p.level == 0]
    placed = place_scenery(placements, read_locs(store, {p.loc for p in placements}), terrain_height(terrain))
    first, second = next(p for p in placed if (p.placement.loc, p.placement.x, p.placement.y) == (84, 16, 46)).parts
    assert first.model.mirrored
    assert mesh_of(scenery_object("Loc 84 at 16_46")).users > 1
    for name, part in (("Loc 84 at 16_46", first), ("Loc 84 at 16_46 part 2", second)):
        assert part.rotation is not None
        assert part.scale is not None
        obj = scenery_object(name)
        assert xyz(obj.location) == pytest.approx(part.location)
        assert xyz(obj.rotation_euler) == pytest.approx((0, 0, part.rotation))
        assert xyz(obj.scale) == pytest.approx(part.scale)
    assert scenery_object("Loc 84 at 16_46").scale.y == -1


def xyz(vector) -> tuple[float, float, float]:
    return vector.x, vector.y, vector.z


def terrain_height(terrain: Terrain):
    return lambda x, y: terrain.tile(0, x, y).height


def mesh_name(loc_id: int, model_type: int) -> str:
    """The name of a shared mesh, which the owner chose on 2026-11-14 (issue 49, Decisions): the loc that first shows it,
    its models, and ` recoloured` when the loc has recolours or retextures."""
    models = reference_model(loc_id, model_type)
    assert models is not None
    row = LOC_ROWS[loc_id]
    recoloured = " recoloured" if row["recolorToFind"] or row["retextureToFind"] else ""
    return f"Loc {loc_id} model {'+'.join(str(model) for model in models)}{recoloured}"


@needs_snapshot_430
def test_contoured_placements_on_flat_ground_share_one_mesh(snapshot_430):
    # Loc 1631 is contoured (locs.json, contouredGround 0). Its walls of type 0 at (11, 56) and (11, 57) stand where every
    # corner that the client tests has the same height, so the client returns the model unchanged (`ModelData.java` line
    # 1152, ADR 0023).
    import_region()

    first, second = scenery_object("Loc 1631 at 11_56"), scenery_object("Loc 1631 at 11_57")
    assert mesh_of(first) is mesh_of(second)
    assert without_number(mesh_of(first).name) == mesh_name(1631, 0)


@needs_snapshot_430
def test_a_contoured_placement_on_uneven_ground_has_its_own_mesh_and_an_object_with_only_a_position(snapshot_430):
    # Loc 4735 is contoured (locs.json, contouredGround 0), and its ground decoration at (1, 47) stands on uneven ground.
    import_region()

    obj = scenery_object("Loc 4735 at 1_47")
    assert mesh_of(obj).users == 1
    assert mesh_of(obj).name == obj.name
    assert xyz(obj.rotation_euler) == (0, 0, 0)
    assert xyz(obj.scale) == (1, 1, 1)
    assert len({round(vertex.co.z) for vertex in mesh_of(obj).vertices}) > 1


@needs_snapshot_430
def test_the_stored_data_of_an_own_mesh_holds_its_moved_vertices(snapshot_430):
    # The owner chose on 2026-11-14 that an own mesh is made from its vertices rounded to whole game units, so that
    # what model import stores matches the mesh (issue 49, Decisions). Export drops a set-aside face whose stored
    # corners no longer match the vertices (`mesh.matching_set_aside_faces`).
    import_region()

    own = [
        mesh_of(obj)
        for obj in scenery_of_48_50().objects
        if without_number(mesh_of(obj).name) == without_number(obj.name)
    ]
    assert own
    for mesh in own:
        assert matching_set_aside_faces(mesh)[1] == 0
        coordinates = [0.0] * (3 * len(mesh.vertices))
        mesh.vertices.foreach_get("co", coordinates)
        assert all(value == round(value) for value in coordinates)
    assert any(rs_layers.read_set_aside_faces(mesh) for mesh in own)


@needs_snapshot_430
def test_the_own_mesh_of_a_mirrored_placement_swaps_the_first_and_last_corner_of_each_face(snapshot_430):
    # Loc 12686 at (40, 7) is mirrored (locs.json, isRotated) and stands on uneven ground, so its mesh holds the
    # mirrored vertices, and `ModelData.method2633` (lines 1380 to 1390) swaps the corners. Its model is 13536.
    import_region()

    mesh = mesh_of(scenery_object("Loc 12686 at 40_7"))
    model = decode(Js5Store(SNAPSHOT_430).container(7, 13536), profile="osrs-149")
    expected = [(c, b, a) for a, b, c in model.faces if len({a, b, c}) == 3]
    corners = [
        tuple(mesh.loops[polygon.loop_start + i].vertex_index for i in range(polygon.loop_total))
        for polygon in mesh.polygons
    ]
    assert corners == expected


@needs_snapshot_430
def test_an_impostor_shows_the_loc_for_value_0(snapshot_430):
    # locs.json: loc 14908 has varbit 2098 and the impostor 7102 for value 0. Its placement at (15, 51) is a wall
    # decoration of type 5, which asks for type 4.
    import_region()

    assert without_number(mesh_of(scenery_object("Loc 14908 at 15_51")).name) == mesh_name(
        reference_shown_loc(14908), 4
    )


@needs_snapshot_430
def test_an_animated_loc_shows_its_model_with_no_animation(snapshot_430):
    # locs.json: loc 197 has the animation 481. Its placement at (53, 44) is a wall decoration of type 4.
    import_region()

    obj = scenery_object("Loc 197 at 53_44")
    assert without_number(mesh_of(obj).name) == mesh_name(197, 4)
    assert mesh_of(obj).polygons
    assert obj.animation_data is None


@needs_snapshot_430
def test_the_scenery_materials_use_the_decoded_images(snapshot_430, monkeypatch):
    def no_texture_folder(texture_id):
        raise AssertionError(f"The import looked up texture {texture_id} in the texture folder")

    monkeypatch.setattr(preferences, "find_texture", no_texture_folder)

    import_region()

    images = {
        image
        for obj in scenery_of_48_50().objects
        for material in mesh_of(obj).materials
        if material is not None
        for image in [material_image(material)]
        if image is not None
    }
    assert images
    assert all(image.packed_file is not None and image.name.startswith("RS_Texture_") for image in images)


@needs_snapshot_430
def test_one_undo_removes_the_whole_import_with_its_scenery(snapshot_430):
    bpy.ops.ed.undo_push(message="Before the import")
    import_region()
    bpy.ops.ed.undo_push(message="Region imported")
    assert scenery_of_48_50().objects

    bpy.ops.ed.undo()

    assert not region_collections()
    assert not bpy.data.objects
    assert not bpy.data.meshes


@needs_snapshot_430
def test_a_failure_while_building_the_scenery_leaves_nothing_behind(snapshot_430, monkeypatch):
    built = region_import.scenery_objects

    def fail(*args):
        built(*args)
        raise ValueError("The build failed")

    monkeypatch.setattr(region_import, "scenery_objects", fail)

    with pytest.raises(RuntimeError, match="The build failed"):
        import_region()
    assert not bpy.data.collections
    assert not bpy.data.objects
    assert not bpy.data.meshes
    assert not bpy.data.materials
    assert not bpy.data.images


# The entry text, the operator name and the properties are spec 35, decision 6 and part 9.
def test_the_menu_entry_adds_the_region_operator_with_its_text():
    calls = []
    layout = SimpleNamespace(operator=lambda idname, text: calls.append((idname, text)))

    region_import.menu_entry(SimpleNamespace(layout=layout), None)

    assert calls == [("import_scene.rs_region", "RS Region (from cache)")]


def test_the_region_entry_follows_the_item_entry_in_file_import():
    addon.register()
    try:
        draw_functions = bpy.types.TOPBAR_MT_file_import.draw._draw_funcs  # pyrefly: ignore[missing-attribute]
        item = draw_functions.index(import_item.menu_entry)
        assert draw_functions[item + 1] is region_import.menu_entry
    finally:
        addon.unregister()
    assert region_import.menu_entry not in bpy.types.TOPBAR_MT_file_import.draw._draw_funcs  # pyrefly: ignore[missing-attribute]


def test_the_region_properties_are_whole_numbers_from_0_to_255_with_defaults_48_and_50(operator_registered):
    properties = bpy.ops.import_scene.rs_region.get_rna_type().properties  # pyrefly: ignore[missing-attribute]
    for name, default in (("region_x", 48), ("region_y", 50)):
        prop = properties[name]
        assert prop.type == "INT"
        assert (prop.hard_min, prop.hard_max, prop.default) == (0, 255, default)


def reference_pixels(texture_id: int) -> tuple[int, ...]:
    """RuneLite's pixels of one texture at brightness 0.8, row by row from the top, from the reference file that
    `tests/fixtures/TextureReference.java` writes. The Brightness preference is 0.8 when the add-on is not enabled."""
    lines = iter(gzip.decompress((REGION_FIXTURES / "textures.txt.gz").read_bytes()).decode().splitlines())
    for header in lines:
        _, texture, _, _ = header.split()
        for _ in range(4):
            _, brightness = next(lines).split()
            rows = [next(lines) for _ in range(SIZE)]
            if int(texture) == texture_id and float(brightness) == BRIGHTNESS:
                return tuple(int(pixel, 16) for row in rows for pixel in row.split())
    raise LookupError(texture_id)


def rgba_from_the_top(image: bpy.types.Image) -> list[tuple[int, ...]]:
    """The image's pixels as 0 to 255 channels, row by row from the top. Blender's rows start at the bottom."""
    flat = [0.0] * (SIZE * SIZE * 4)
    image.pixels.foreach_get(flat)
    channels = [round(value * 255) for value in flat]
    rows = [channels[row * SIZE * 4 : (row + 1) * SIZE * 4] for row in range(SIZE)]
    return [tuple(row[i : i + 4]) for row in reversed(rows) for i in range(0, SIZE * 4, 4)]
