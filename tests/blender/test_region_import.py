import gzip
import json
import os
import re
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bpy
import pytest
from js5_builder import REGION_FIXTURES, build_region_cache
from runelite_json import load_locs, load_overlays, load_underlays

import rsps_toolkit.blender as addon
from rsps_toolkit.blender import (
    appearance_collection,
    appearance_preview,
    appearance_props,
    import_item,
    preferences,
    region_import,
    region_scenery,
    region_terrain,
    rs_layers,
)
from rsps_toolkit.blender.face_materials import material_values, srgb_to_linear, texture_image
from rsps_toolkit.blender.mesh import matching_set_aside_faces, model_to_object
from rsps_toolkit.formats import decode, face_colour_to_rgb
from rsps_toolkit.formats.appearance import merge
from rsps_toolkit.formats.appearance_preset import AppearancePreset
from rsps_toolkit.formats.cache_profile import MODEL_INDEX, SET_CACHE_FOLDER
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.lighting import Shading
from rsps_toolkit.formats.loc_definition import LocDefinition, read_locs
from rsps_toolkit.formats.model import Model
from rsps_toolkit.formats.region import (
    AREA_SIZE,
    EMPTY_TILE,
    LEVELS,
    Placement,
    Terrain,
    Tile,
    ground_height,
    load_landscape,
    load_terrain,
)
from rsps_toolkit.formats.region_colours import HIDDEN, tile_colours
from rsps_toolkit.formats.region_light import loc_shadows
from rsps_toolkit.formats.region_loc_light import loc_light
from rsps_toolkit.formats.region_placement import place_scenery
from rsps_toolkit.formats.region_shapes import Corner, TilePoint, tile_triangles
from rsps_toolkit.formats.sprite import decode_sprites
from rsps_toolkit.formats.texture import SIZE, decode_texture, texture_pixels

FLOORS = REGION_FIXTURES / "floors.json"
APPEARANCE_FIXTURES = Path(__file__).parent.parent / "fixtures" / "appearance"
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


@pytest.mark.parametrize(("x", "y"), [(11, 56), (60, 3)])
def test_the_loc_shadows_darken_the_corner_colours_as_the_colour_module_gives_them(terrain, x, y):
    # Tile (11, 56) has an overlay with a plain colour and tile (60, 3) an overlay with texture 1. A wall shadow of 50 sits
    # on the south-west corner of the tile and an object shadow of 20 on its north-east corner.
    shadows = {(x, y): 50, (x + 1, y + 1): 20}
    images = {texture: decoded_image(texture) for texture in (1, 3)}
    shadowed = region_terrain.terrain_object("Terrain 48_50", terrain, UNDERLAYS, OVERLAYS, images, BRIGHTNESS, shadows)
    lit = tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS, shadows)
    unlit = tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS)
    assert lit is not None and lit.overlay is not None and lit != unlit
    faces = faces_by_corners(shadowed)

    for triangle in tile_triangles(terrain.tile(0, x, y)):
        values = lit.overlay if triangle.overlay else lit.underlay
        face = faces[tuple(point_position(terrain, x, y, point) for point in triangle.points)]
        textured = triangle.overlay and (x, y) in TEXTURED
        shown = shown_shade if textured else shown_colour
        expected = [channel for point in triangle.points for channel in shown(point_value(values, point))]
        actual = [channel for colour in corner_colours(shadowed, face) for channel in colour]
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


def test_the_tiles_of_a_terrain_that_have_a_face_are_counted_once_each():
    # Tile (10, 10) has an underlay and no shape, so it has 2 faces. Tile (11, 10) has a hidden overlay (overlay 42,
    # colour 0xFF00FF in floors.json) and no underlay, so all its parts are hidden. Tile (12, 10) has nothing. Tile (13, 10)
    # has an underlay and a hidden overlay of shape 2, so it has the underlay triangle only. Region 48_50 has none of these.
    terrain = made_terrain(
        {(10, 10): Tile(0, 0, 48, 0, 0, 0), (11, 10): Tile(0, 0, 0, 42, 0, 0), (13, 10): Tile(0, 0, 48, 42, 1, 0)}
    )

    obj = region_terrain.terrain_object("Terrain", terrain, UNDERLAYS, OVERLAYS, {}, BRIGHTNESS)

    assert len(mesh_of(obj).polygons) == 3
    assert region_terrain.drawn_tiles(obj) == 2


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


# Tile (3, 48) of 48_50 is flat at height -280 (`tests/unit/test_region_terrain.py`), so `class264.java` lines 106 to 108
# give -280 at its centre, and the Blender z is 280.
FLAT_TILE = (3, 48)
FLAT_TILE_POINT = (3 * 128 + 64, 48 * 128 + 64, 280)


@pytest.fixture
def player_registered():
    for cls in (*appearance_props.classes, *appearance_collection.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    yield
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_collection.classes)):
        bpy.utils.unregister_class(cls)


PLAYER_REFERENCE = json.loads((APPEARANCE_FIXTURES / "reference.json").read_text())["cases"][0]


def created_player(cache: Path) -> bpy.types.Object:
    """The rig of a new player from Create Player, with the first appearance of the appearance reference file."""
    preset = AppearancePreset(
        149, 430, PLAYER_REFERENCE["female"], tuple(PLAYER_REFERENCE["equipment"]), tuple(PLAYER_REFERENCE["colours"])
    )
    appearance_props.from_preset(bpy.context.scene.rs_appearance, preset)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.create_appearance_preview(cache_folder=str(cache)) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    collection = appearance_preview.collection_of(bpy.context.active_object)
    assert collection is not None
    return appearance_collection.armature_of(collection)


def linked(obj: bpy.types.Object) -> None:
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)


def hit_below(obj: bpy.types.Object, x: float, y: float) -> float:
    """The z where a ray straight down from far above (x, y) first hits the object, which stands at the origin."""
    hit, location, _, _ = obj.ray_cast((x, y, 10_000.0), (0.0, 0.0, -1.0))
    assert hit
    return location.z


def lowest_z(objects: list[bpy.types.Object]) -> float:
    """The lowest world z of the evaluated vertices of the objects."""
    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lowest = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            lowest.append(min((evaluated.matrix_world @ v.co).z for v in mesh.vertices))
        finally:
            evaluated.to_mesh_clear()
    return min(lowest)


def test_the_tile_to_position_point_is_the_centre_of_the_tile_at_the_clients_height(terrain):
    assert region_terrain.tile_position(terrain, *FLAT_TILE) == FLAT_TILE_POINT


def test_a_player_placed_at_the_tile_to_position_point_of_a_flat_tile_stands_on_the_terrain_mesh(
    terrain, player_registered, cache
):
    obj = terrain_of_48_50(terrain)
    linked(obj)
    rig = created_player(cache)

    rig.location = region_terrain.tile_position(terrain, *FLAT_TILE)

    assert (rig.location.x, rig.location.y, rig.location.z) == FLAT_TILE_POINT
    assert hit_below(obj, rig.location.x, rig.location.y) == pytest.approx(rig.location.z)
    # The client's model of this player has its lowest vertex at game height 6 (`before_lighting` in the appearance
    # reference file), so its feet are 6 units below the ground point, and the Blender player's lowest vertex is too.
    feet = max(y for _, y, _ in PLAYER_REFERENCE["before_lighting"]["vertices"])
    player = appearance_preview.collection_of(rig)
    assert player is not None
    assert lowest_z(appearance_collection.parts(player)) == pytest.approx(FLAT_TILE_POINT[2] - feet)


def test_after_the_terrain_mesh_is_edited_the_tile_to_position_point_is_the_same(terrain):
    obj = terrain_of_48_50(terrain)
    linked(obj)
    mesh = mesh_of(obj)
    for vertex in mesh.vertices:
        vertex.co.z += 500
    mesh.update()

    assert hit_below(obj, FLAT_TILE_POINT[0], FLAT_TILE_POINT[1]) == pytest.approx(FLAT_TILE_POINT[2] + 500)
    assert region_terrain.tile_position(terrain, *FLAT_TILE) == FLAT_TILE_POINT


def test_a_bridge_tile_gives_the_ground_under_the_bridge(terrain):
    # Tile (40, 0) is a bridge tile with level 0 ground at height 0 and the bridge at level 1 height -240
    # (`tests/unit/test_region_terrain.py`). `class264.java` lines 99 to 101 would give the bridge, but the import has no
    # level 1 (spec 35, part 8).
    assert region_terrain.tile_position(terrain, 40, 0) == (40 * 128 + 64, 64, 0)


@pytest.mark.parametrize(("x", "y"), [(-1, 0), (64, 0), (0, -1), (0, 64)])
def test_a_tile_outside_the_region_has_no_tile_to_position_point(terrain, x, y):
    with pytest.raises(ValueError, match="outside region 48_50"):
        region_terrain.tile_position(terrain, x, y)


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


def expected_tiles(terrain: Terrain) -> int:
    """The tiles of the region that have a triangle to draw, from the colour module and the tile shapes: a tile with no
    underlay and no overlay has none, and a triangle is not drawn when it has no texture and its first point has the
    colour `HIDDEN` (`Region.java` lines 1852, 1879 and 1967)."""
    count = 0
    for x in range(64):
        for y in range(64):
            lit = tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS)
            if lit is None:
                continue
            for triangle in tile_triangles(terrain.tile(0, x, y)):
                values = lit.overlay if triangle.overlay else lit.underlay
                assert values is not None
                if (triangle.overlay and lit.texture != -1) or point_value(values, triangle.points[0]) != HIDDEN:
                    count += 1
                    break
    return count


def reported_info(capfd) -> str:
    """The one INFO message that the operator reported. Blender prints it to its standard output as `Info: <message>`,
    which a call through `bpy.ops` does not hand back otherwise."""
    lines = [line for line in capfd.readouterr().out.splitlines() if line.startswith("Info: Imported region")]
    assert len(lines) == 1
    return lines[0].removeprefix("Info: ")


def test_the_report_text_gives_each_number_and_names_the_bridge_tiles():
    report = region_import.RegionReport(
        tiles=4000,
        scenery=region_scenery.SceneryCounts(placements=10, objects=12, shared_meshes=3, own_meshes=2, shown_nothing=1),
        bridge_tiles=tuple((3112 + dx, 3200 + dy) for dx in range(4) for dy in range(7)),
        has_key=True,
    )

    assert region_import.report_text(48, 50, report) == (
        "Imported region 48_50: 4000 tiles, 9 placements made as 12 objects, 3 shared meshes, 2 own meshes, 1 placements "
        "that showed nothing, the region had a key. 28 bridge tiles are left out: x 3112 to 3115, y 3200 to 3206"
    )


def test_the_report_text_says_when_the_region_had_no_key_and_has_no_bridge_tiles_to_name():
    report = region_import.RegionReport(
        tiles=5, scenery=region_scenery.SceneryCounts(0, 0, 0, 0, 0), bridge_tiles=(), has_key=False
    )

    assert region_import.report_text(1, 2, report) == (
        "Imported region 1_2: 5 tiles, 0 placements made as 0 objects, 0 shared meshes, 0 own meshes, 0 placements that "
        "showed nothing, the region had no key"
    )


def test_bridge_tiles_that_are_not_one_rectangle_are_named_by_runs_of_columns():
    tiles = ((10, 5), (10, 6), (11, 5), (11, 6), (12, 9), (13, 9), (14, 9), (14, 10))

    assert region_import.bridge_text(tiles) == "x 10 to 11, y 5 to 6; x 12 to 13, y 9; x 14, y 9 to 10"


def test_a_region_with_no_key_file_gets_its_terrain_and_no_scenery_and_the_report_says_so(fixture_cache, terrain):
    # `fixture_cache` has a keys folder with no key file for 48_50 (`GLOSSARY.md`, Landscape keys).
    scene = bpy.context.scene
    assert scene is not None
    cache = preferences.cache_folder()
    assert cache is not None

    region, report = region_import.import_region(scene.collection, cache, 48, 50, BRIGHTNESS)

    assert report.has_key is False
    assert report.scenery == region_scenery.SceneryCounts(0, 0, 0, 0, 0)
    (terrain_obj,) = region.objects
    assert terrain_obj.name == "Terrain 48_50"
    assert report.tiles == expected_tiles(terrain) > 0
    (scenery,) = region.children
    assert not scenery.objects
    assert "the region had no key" in region_import.report_text(48, 50, report)


@needs_snapshot_430
def test_the_report_of_48_50_equals_the_counts_of_the_scene_and_names_the_28_bridge_tiles(snapshot_430, terrain):
    scene = bpy.context.scene
    assert scene is not None
    region, report = region_import.import_region(scene.collection, SNAPSHOT_430, 48, 50, BRIGHTNESS)

    (scenery,) = region.children
    assert report.has_key is True
    assert report.tiles == expected_tiles(terrain)
    assert report.scenery.objects == len(scenery.objects)
    assert report.scenery.placements == len(level_0_rows())
    objects, nothing = reference_scenery()
    assert report.scenery.shown_nothing == nothing
    assert report.scenery.placements_made == len(level_0_rows()) - nothing
    assert report.scenery.objects == len(objects)
    assert report.bridge_tiles == tuple((x, y) for x in range(3112, 3116) for y in range(3200, 3207))
    text = region_import.report_text(48, 50, report)
    assert "28 bridge tiles" in text
    assert "x 3112 to 3115, y 3200 to 3206" in text
    assert f"{report.tiles} tiles" in text


@needs_snapshot_430
def test_the_operator_reports_the_text_of_the_report_with_the_bridge_tiles(snapshot_430, capfd):
    assert import_region() == {"FINISHED"}

    message = reported_info(capfd)
    assert message.startswith("Imported region 48_50: ")
    assert "the region had a key" in message
    assert "28 bridge tiles are left out: x 3112 to 3115, y 3200 to 3206" in message


def test_the_operator_reports_that_a_region_had_no_key(fixture_cache, capfd):
    assert import_region() == {"FINISHED"}

    message = reported_info(capfd)
    assert "0 placements made as 0 objects" in message
    assert "the region had no key" in message


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
    region, report = region_import.import_region(scene.collection, SNAPSHOT_430, 48, 50, BRIGHTNESS)

    counts = report.scenery
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


WALL_SHADOW_CORNERS = {
    # PacketBuffer.java lines 254 to 284 (type 0) and 307 to 316 and 370 to 379 (types 1 and 3), by rotation.
    0: {0: ((0, 0), (0, 1)), 1: ((0, 1), (1, 1)), 2: ((1, 0), (1, 1)), 3: ((0, 0), (1, 0))},
    1: {0: ((0, 1),), 1: ((1, 1),), 2: ((1, 0),), 3: ((0, 0),)},
    3: {0: ((0, 1),), 1: ((1, 1),), 2: ((1, 0),), 3: ((0, 0),)},
}


def level_0_rows() -> list[dict]:
    return [row for row in LANDSCAPE_ROWS if row["level"] == 0]


def reference_wall_shadows() -> dict[tuple[int, int], int]:
    """The shadow 50 that each wall of type 0, 1 and 3 of 48_50 with a shadow writes at its corners, from the reference
    rows. A wall writes 50 whatever the corner held."""
    shadows = {}
    for row in level_0_rows():
        if row["type"] in WALL_SHADOW_CORNERS and LOC_ROWS[row["id"]]["shadow"]:
            for dx, dy in WALL_SHADOW_CORNERS[row["type"]][row["rotation"]]:
                shadows[(row["x"] + dx, row["y"] + dy)] = 50
    return shadows


def object_shadow_corners() -> set[tuple[int, int]]:
    """The corners of the footprints of the objects of 48_50 with a shadow, which swap width and length at the rotations
    1 and 3 (`PacketBuffer.java` lines 169 to 177). These objects write a shadow that depends on their model, which the
    reference rows do not give."""
    corners = set()
    for row in level_0_rows():
        loc = LOC_ROWS[row["id"]]
        if row["type"] in (10, 11) and loc["shadow"]:
            width, length = (loc["sizeY"], loc["sizeX"]) if row["rotation"] in (1, 3) else (loc["sizeX"], loc["sizeY"])
            corners |= {(row["x"] + dx, row["y"] + dy) for dx in range(width + 1) for dy in range(length + 1)}
    return corners


def wall_corner_away_from_objects() -> tuple[int, int]:
    """The first corner of a wall of type 0 of 48_50 with no object corner within 2 corners of it, so the 4 tiles that
    share it have only wall shadows in their light."""
    objects = object_shadow_corners()
    for row in level_0_rows():
        if row["type"] != 0 or not LOC_ROWS[row["id"]]["shadow"]:
            continue
        dx, dy = WALL_SHADOW_CORNERS[0][row["rotation"]][0]
        x, y = row["x"] + dx, row["y"] + dy
        if 3 <= x <= 60 and 3 <= y <= 60 and not any(abs(ox - x) <= 2 and abs(oy - y) <= 2 for ox, oy in objects):
            return x, y
    raise AssertionError("48_50 has no wall of type 0 away from the objects that cast shadows")


def assert_tile_shows(obj: bpy.types.Object, terrain: Terrain, x: int, y: int, shadows: dict[tuple[int, int], int]):
    """Each face of tile (x, y) has the colours that `tile_colours` gives with `shadows`."""
    lit = tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS, shadows)
    assert lit is not None
    faces = faces_by_corners(obj)
    for triangle in tile_triangles(terrain.tile(0, x, y)):
        values = lit.overlay if triangle.overlay else lit.underlay
        assert values is not None
        if values[0] == HIDDEN:
            continue
        face = faces[tuple(point_position(terrain, x, y, point) for point in triangle.points)]
        shown = shown_shade if triangle.overlay and lit.texture != -1 else shown_colour
        expected = [channel for point in triangle.points for channel in shown(point_value(values, point))]
        actual = [channel for colour in corner_colours(obj, face) for channel in colour]
        assert actual == pytest.approx(expected, abs=1e-6), (x, y)


@needs_snapshot_430
def test_the_terrain_corners_next_to_a_wall_of_48_50_have_the_colour_with_the_shadow_of_the_wall(snapshot_430, terrain):
    # The corner light reads the shadows of the corner and of the 4 corners next to it (`class24.java` lines 107 to 115).
    # The 4 tiles that share a corner of the wall read only wall shadows, which come from the reference rows.
    corner_x, corner_y = wall_corner_away_from_objects()
    shadows = reference_wall_shadows()
    assert shadows[(corner_x, corner_y)] == 50
    import_region()

    (region,) = region_collections()
    tiles = [(corner_x - 1 + dx, corner_y - 1 + dy) for dx in (0, 1) for dy in (0, 1)]
    for x, y in tiles:
        assert_tile_shows(region.objects[0], terrain, x, y, shadows)
    assert any(
        tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS, shadows) != tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS)
        for x, y in tiles
    )


@needs_snapshot_430
def test_a_terrain_corner_far_from_any_placement_has_the_colour_with_no_shadow(snapshot_430, terrain):
    rows = level_0_rows()
    # A placement reaches the tiles within 3 of its tile, and an object with a wider footprint reaches 3 from each corner.
    origins = {(row["x"], row["y"]) for row in rows} | object_shadow_corners()
    near = {(x, y) for ox, oy in origins for x in range(ox - 3, ox + 4) for y in range(oy - 3, oy + 4)}
    far = [
        (x, y)
        for x in range(64)
        for y in range(64)
        if (x, y) not in near and tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS) is not None
    ]
    assert len(far) > 100
    import_region()

    (region,) = region_collections()
    for x, y in far:
        assert_tile_shows(region.objects[0], terrain, x, y, {})


@needs_snapshot_430
def test_the_terrain_of_48_50_has_the_colours_with_the_wall_and_object_shadows_of_its_placements(snapshot_430, terrain):
    # The anchor tests above check the wall shadows and the far tiles against the reference rows. The shadow of an object
    # depends on its model, so this test builds the shadows with `loc_shadows` from the models of the cache and checks
    # that the import passes them on to every tile.
    store = Js5Store(SNAPSHOT_430)
    placements = [placement for placement in load_landscape(store, 48, 50).placements if placement.level == 0]
    locs = read_locs(store, {placement.loc for placement in placements})
    placed = place_scenery(placements, locs, terrain_height(terrain))

    def model_vertices(loc_model):
        parts = [decode(store.container(MODEL_INDEX, model_id), profile="osrs-149") for model_id in loc_model.model_ids]
        return (parts[0] if len(parts) == 1 else merge(parts)).vertices

    shadows = loc_shadows(placed, locs, model_vertices)
    assert max(shadows.values()) == 50 and any(0 < shadow < 50 for shadow in shadows.values())
    expected = region_terrain.terrain_object(
        "Terrain", terrain, UNDERLAYS, OVERLAYS, {1: decoded_image(1), 3: decoded_image(3)}, BRIGHTNESS, shadows
    )
    unlit = terrain_of_48_50(terrain)
    import_region()

    (region,) = region_collections()
    imported = [corner_colours(region.objects[0], face.index) for face in mesh_of(region.objects[0]).polygons]
    assert imported == [corner_colours(expected, face.index) for face in mesh_of(expected).polygons]
    assert imported != [corner_colours(unlit, face.index) for face in mesh_of(unlit).polygons]


LIGHT_FIELDS = ("ambient", "contrast", "mergeNormals", "modelSizeX", "modelSizeHeight", "modelSizeY")
"""The fields of a reference row that the loc light reads: the ambient, the contrast, `nonFlatShading` (which RuneLite
names `mergeNormals`) and the scale."""


@needs_snapshot_430
def test_objects_of_locs_that_are_not_contoured_share_a_mesh_exactly_when_every_input_of_the_light_is_the_same(
    snapshot_430,
):
    # ADR 0027: placements share a mesh only when the models, recolours, retextures, rotation, mirror, scale, diagonal
    # turn, ambient, contrast and nonFlatShading are the same. The turns of a part come from `place_scenery`, which
    # `test_region_placement.py` checks. A loc that is not contoured shares its mesh unless Blender cannot hold its
    # transform, which needs a scale that is not 128 (`region_contour`), and no loc of 48_50 is scaled (spec 35). A
    # name that two objects have is left out, because Blender numbers the second.
    import_region()

    store = Js5Store(SNAPSHOT_430)
    terrain = load_terrain(store, 48, 50)
    placements = [p for p in load_landscape(store, 48, 50).placements if p.level == 0]
    placed = place_scenery(placements, read_locs(store, {p.loc for p in placements}), terrain_height(terrain))
    parts = {
        f"Loc {p.placement.loc} at {p.placement.x}_{p.placement.y}" + (" part 2" if index else ""): part
        for p in placed
        for index, part in enumerate(p.parts)
    }
    objects, _ = reference_scenery()
    names = Counter(name for name, _, _ in objects)
    mesh_by_key: dict[tuple[object, ...], bpy.types.Mesh] = {}
    for name, key, contoured in objects:
        if contoured or names[name] != 1:
            continue
        part = parts[name]
        shown = LOC_ROWS[reference_shown_loc(int(name.split()[1]))]
        diagonal = part.model_type == 4 and part.model_rotation > 3
        light_key = (
            *key,
            part.model_rotation & 3,
            part.model.mirrored,
            diagonal,
            *(shown[field] for field in LIGHT_FIELDS),
        )
        mesh = mesh_of(scenery_object(name))
        assert mesh_by_key.setdefault(light_key, mesh) is mesh, name
    assert len(set(mesh_by_key.values())) == len(mesh_by_key)


def test_a_placement_that_shows_nothing_makes_no_object_and_is_counted():
    # locs.json: loc 83 has no model for type 10, so a placement of type 10 shows nothing.
    locs = load_locs(REGION_FIXTURES / "locs.json")
    placement = Placement(83, 0, 5, 5, 10, 0)
    placed = place_scenery([placement], locs, lambda x, y: 0)
    collection = bpy.data.collections.new("Scenery")

    counts = region_scenery.scenery_objects(collection, placed, locs, {}, {}, {}, lambda x, y: 0, BRIGHTNESS)

    assert not collection.objects
    assert (counts.placements, counts.placements_made, counts.objects, counts.shown_nothing) == (1, 0, 0, 1)


HAND_COLOUR = (10 << 10) | (3 << 7) | 100
HAND_MODEL = Model(
    vertices=[(0, 0, 0), (128, -10, 0), (0, -40, 128), (64, -200, 64)],
    # A smooth face, a flat face, a face that repeats a vertex (set aside, so the mesh has no polygon for it), a
    # textured face and a face with alpha 255, which the client hides.
    faces=[(0, 1, 2), (0, 2, 3), (0, 0, 1), (1, 2, 3), (0, 1, 3)],
    face_colours=[HAND_COLOUR, HAND_COLOUR, HAND_COLOUR, None, HAND_COLOUR],
    face_textures=[None, None, None, 1, None],
    render_priorities=[0] * 5,
    face_alphas=[0, 0, 0, 0, 255],
    face_texture_triangles=[None] * 5,
    flat_shaded=[False, True, False, False, False],
)


def hand_loc(**changes: Any) -> LocDefinition:
    """A loc that shows model 11 for type 10, with the defaults of the `ObjectComposition` constructor (lines 262 to
    296), the ambient 16 and the contrast 50, changed as given."""
    defaults: dict[str, Any] = {
        "models": (11,),
        "loc_types": None,
        "width": 1,
        "length": 1,
        "recolours": (),
        "retextures": (),
        "scale": (128, 128, 128),
        "offset": (0, 0, 0),
        "mirrored": False,
        "contoured_ground": -1,
        "non_flat_shading": False,
        "animation": -1,
        "impostors": None,
        "impostor_varbit": -1,
        "impostor_varp": -1,
        "ambient": 16,
        "contrast": 50,
    }
    return replace(load_locs(REGION_FIXTURES / "locs.json")[83], **(defaults | changes))


def hand_scenery(
    locs: dict[int, LocDefinition], placements: list[Placement], height=lambda x, y: -40
) -> tuple[bpy.types.Collection, region_scenery.SceneryCounts]:
    """The scenery of the placements, where every loc shows `HAND_MODEL`."""
    placed = place_scenery(placements, locs, height)
    models: dict[tuple[int, ...], Model] = {
        (model_id,): HAND_MODEL for model_id in {model for loc in locs.values() for model in loc.models}
    }
    keys = {
        region_scenery.model_key(part, locs[p.shown_id]): models[part.model.model_ids]
        for p in placed
        if p.shown_id is not None
        for part in p.parts
    }
    render_types: dict[tuple[int, ...], list[int]] = {model_ids: [0, 1, 0, 0, 0] for model_ids in models}
    collection = bpy.data.collections.new("Scenery")
    counts = region_scenery.scenery_objects(collection, placed, locs, keys, render_types, {}, height, BRIGHTNESS)
    return collection, counts


def test_two_placements_that_differ_only_in_rotation_get_two_meshes_and_two_equal_ones_share_one():
    # ADR 0027 and rule 7 of spec 105: the client lights a loc model after its turn (ObjectComposition.java lines 792
    # to 801 and 585), so the rotation is part of the mesh key.
    locs = {1: hand_loc()}
    placements = [Placement(1, 0, 5, 5, 10, 0), Placement(1, 0, 8, 5, 10, 0), Placement(1, 0, 11, 5, 10, 1)]

    collection, counts = hand_scenery(locs, placements)

    first, second, turned = (mesh_of(obj) for obj in collection.objects)
    assert first is second
    assert turned is not first
    assert (counts.shared_meshes, counts.own_meshes) == (2, 0)


@pytest.mark.parametrize(
    "change",
    [
        {"mirrored": True},
        {"scale": (128, 256, 128)},
        {"ambient": 20},
        {"contrast": 75},
        {"non_flat_shading": True},
        {"recolours": ((HAND_COLOUR, 200),)},
    ],
    ids=lambda change: next(iter(change)),
)
def test_two_placements_of_one_model_that_differ_in_one_input_of_the_light_get_two_meshes(change):
    # ADR 0027 and rule 7 of spec 105. ObjectComposition.java lines 753 to 820 mirror and scale the model before the
    # light, line 585 lights it with the ambient and the contrast, and lines 586 to 590 leave a nonFlatShading loc to
    # Region.applyLighting.
    locs = {1: hand_loc(), 2: hand_loc(**change)}

    collection, _ = hand_scenery(locs, [Placement(1, 0, 5, 5, 10, 0), Placement(2, 0, 8, 5, 10, 0)])

    first, second = (mesh_of(obj) for obj in collection.objects)
    assert first is not second


def test_a_diagonal_wall_decoration_and_a_straight_one_of_one_model_get_two_meshes():
    # A type 6 decoration at rotation 0 asks for getModel(4, 4), and a type 4 decoration asks for getModel(4, 0)
    # (PacketBuffer.java lines 422 to 430). The loc of the first has the mirror flag, which ObjectComposition.java line
    # 753 cancels for the rotation 4, so the two parts differ only by the diagonal turn. Lines 787 to 790 make that turn
    # before the light.
    locs = {1: hand_loc(loc_types=(4,), mirrored=True), 2: hand_loc(loc_types=(4,))}
    placements = [Placement(1, 0, 5, 5, 6, 0), Placement(2, 0, 8, 5, 4, 0)]

    collection, _ = hand_scenery(locs, placements)

    diagonal, straight = (p.parts[0] for p in place_scenery(placements, locs, lambda x, y: -40))
    assert (diagonal.model_rotation, straight.model_rotation) == (4, 0)
    assert diagonal.model.mirrored is straight.model.mirrored is False
    first, second = (mesh_of(obj) for obj in collection.objects)
    assert first is not second


def lit_corners(obj: bpy.types.Object) -> list[list[tuple[float, ...]]]:
    """The `rs_lit` colour of each corner of each polygon, in loop order."""
    mesh = mesh_of(obj)
    attribute = mesh.color_attributes[appearance_preview.LIT_ATTRIBUTE]
    assert isinstance(attribute, bpy.types.FloatColorAttribute)
    assert attribute.domain == "CORNER"
    flat = [0.0] * (len(mesh.loops) * 4)
    attribute.data.foreach_get("color", flat)
    return [
        [tuple(flat[4 * loop : 4 * loop + 4]) for loop in range(polygon.loop_start, polygon.loop_start + 3)]
        for polygon in mesh.polygons
    ]


def expected_lit(shading: Shading) -> list[list[tuple[float, ...]]]:
    """The `rs_lit` colours of the polygons of `HAND_MODEL` in the client's corner order of `shading`.

    An untextured corner shows its lit colour at the Brightness preference, as the player's `rs_lit` does. A textured
    corner holds its light value as a grey, which the texture is multiplied by (`shown_shade`). A flat face has the
    third corner -1 and shows its first value at each corner. A face that the client hides has the third corner -2
    and gets the alpha 0. The owner chose the grey and the alpha 0 on 2026-11-17 (issue 129)."""
    a, b, c = shading.corner_a, shading.corner_b, shading.corner_c
    assert (c[1], c[4]) == (-1, -2)
    return [
        [(*shown_colour(a[0]), 1.0), (*shown_colour(b[0]), 1.0), (*shown_colour(c[0]), 1.0)],
        [(*shown_colour(a[1]), 1.0)] * 3,
        [(*shown_shade(a[3]), 1.0), (*shown_shade(b[3]), 1.0), (*shown_shade(c[3]), 1.0)],
        [(0.0, 0.0, 0.0, 0.0)] * 3,
    ]


def flat_list(rows) -> list[float]:
    return [value for row in rows for corner in row for value in corner]


def test_each_corner_of_a_shared_mesh_holds_the_loc_light_of_its_placement():
    locs = {1: hand_loc()}
    placement = Placement(1, 0, 5, 5, 10, 1)

    collection, _ = hand_scenery(locs, [placement])

    (obj,) = collection.objects
    (part,) = place_scenery([placement], locs, lambda x, y: -40)[0].parts
    shading = loc_light(placement, part, locs, HAND_MODEL, lambda x, y: -40, [0, 1, 0, 0, 0])
    assert flat_list(lit_corners(obj)) == pytest.approx(flat_list(expected_lit(shading)), abs=1e-6)
    mesh = mesh_of(obj)
    assert mesh.color_attributes.active_color_name == appearance_preview.LIT_ATTRIBUTE
    assert mesh.color_attributes.render_color_index == mesh.color_attributes.find(appearance_preview.LIT_ATTRIBUTE)


def test_a_shared_mesh_of_a_mirrored_loc_holds_the_light_of_its_last_corner_at_its_first():
    # The shared mesh keeps the model's corner order, and the object mirrors it with a scale of -1. The client swaps the
    # first and the last corner of each face before the light (ModelData.method2633, lines 1380 to 1390), so the
    # light's corner_a belongs to the model's last corner.
    locs = {1: hand_loc(mirrored=True)}
    placement = Placement(1, 0, 5, 5, 10, 0)

    collection, _ = hand_scenery(locs, [placement])

    (obj,) = collection.objects
    (part,) = place_scenery([placement], locs, lambda x, y: -40)[0].parts
    assert part.model.mirrored
    shading = loc_light(placement, part, locs, HAND_MODEL, lambda x, y: -40, [0, 1, 0, 0, 0])
    expected = [row[::-1] for row in expected_lit(shading)]
    assert flat_list(lit_corners(obj)) == pytest.approx(flat_list(expected), abs=1e-6)


def test_an_own_mesh_of_a_mirrored_loc_holds_the_light_in_its_swapped_corner_order():
    # A contoured loc on uneven ground has its own mesh, whose faces already have the first and last corner swapped
    # (`region_scenery._moved`), so its corners take the light in the client's order.
    locs = {1: hand_loc(mirrored=True, contoured_ground=0)}
    placement = Placement(1, 0, 5, 5, 10, 0)

    def tilt(_x: int, y: int) -> int:
        return -128 * y

    collection, counts = hand_scenery(locs, [placement], tilt)

    (obj,) = collection.objects
    assert counts.own_meshes == 1
    (part,) = place_scenery([placement], locs, tilt)[0].parts
    shading = loc_light(placement, part, locs, HAND_MODEL, tilt, [0, 1, 0, 0, 0])
    assert flat_list(lit_corners(obj)) == pytest.approx(flat_list(expected_lit(shading)), abs=1e-6)


def test_a_joined_model_is_lit_with_the_render_types_that_the_scenery_is_given():
    # A loc of several models is joined by appearance.merge, which keeps no render types, so the import passes the
    # stored render types of the parts (lighting.joined_render_types). Render type 2 hides the first face (ModelData.java
    # lines 1635 and 1636).
    locs = {1: hand_loc()}
    placement = Placement(1, 0, 5, 5, 10, 0)
    placed = place_scenery([placement], locs, lambda x, y: -40)
    (part,) = placed[0].parts
    collection = bpy.data.collections.new("Scenery")

    region_scenery.scenery_objects(
        collection,
        placed,
        locs,
        {region_scenery.model_key(part, locs[1]): HAND_MODEL},
        {(11,): [2, 1, 0, 0, 0]},
        {},
        lambda x, y: -40,
        BRIGHTNESS,
    )

    (obj,) = collection.objects
    assert lit_corners(obj)[0] == [(0.0, 0.0, 0.0, 0.0)] * 3


@needs_snapshot_430
def test_an_object_with_a_shared_mesh_holds_the_transform_of_its_placement(snapshot_430):
    # The transform rules are in `formats/region_placement.py` and its tests. Loc 84 at (16, 46) is a wall of type 2, so
    # it has two models, and the first is mirrored. Neither is contoured, so both have a shared mesh, which has the name
    # of its loc model and not of its object.
    import_region()

    store = Js5Store(SNAPSHOT_430)
    terrain = load_terrain(store, 48, 50)
    placements = [p for p in load_landscape(store, 48, 50).placements if p.level == 0]
    placed = place_scenery(placements, read_locs(store, {p.loc for p in placements}), terrain_height(terrain))
    first, second = next(p for p in placed if (p.placement.loc, p.placement.x, p.placement.y) == (84, 16, 46)).parts
    assert first.model.mirrored
    assert without_number(mesh_of(scenery_object("Loc 84 at 16_46")).name) == mesh_name(84, 2)
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
def test_a_contoured_placement_on_uneven_ground_puts_each_vertex_at_the_clients_height(snapshot_430):
    # Loc 4735 (locs.json) has contouredGround 0, the scale 128, no offset, no mirror and the one model 4401. Its ground
    # decoration at (1, 47) has rotation 0 and a footprint of 1 by 1, so the client draws the model's own vertices at
    # the tile centre (`PacketBuffer.java` lines 169 to 200). The client draws the placement at the mean height of the
    # tile's four corners (lines 197 and 198), and contour 0 adds the ground under each vertex less that same mean
    # (`ModelData.java` line 1162 onwards). So a vertex (x, y, z) stands at the game height ground + y, where ground is
    # the height under the vertex (`class264.java` lines 96 to 108, which blends the corners as `Model.method2720` does).
    import_region()

    obj = scenery_object("Loc 4735 at 1_47")
    store = Js5Store(SNAPSHOT_430)
    terrain = load_terrain(store, 48, 50)
    model = decode(store.container(7, 4401), profile="osrs-149")
    centre_x, centre_z = 1 * 128 + 64, 47 * 128 + 64
    expected = [
        (centre_x + x, centre_z + z, -(ground_height(terrain, centre_x + x, centre_z + z) + y))
        for x, y, z in model.vertices
    ]
    world = [xyz(obj.location + vertex.co) for vertex in mesh_of(obj).vertices]
    assert world == expected


@needs_snapshot_430
def test_a_scenery_object_keeps_the_vertex_skins_of_its_model(snapshot_430):
    # The vertex skins are vertex groups. `region_scenery._mesh` removes the object that `model_to_object` made, and
    # every object of the shared mesh must still read the skins. Loc 5558 at (13, 58) shows model 2241, whose vertex
    # skins the cache holds.
    import_region()

    model = decode(Js5Store(SNAPSHOT_430).container(7, 2241), profile="osrs-149")
    assert model.vertex_skins
    obj = scenery_object("Loc 5558 at 13_58")
    assert rs_layers.read_vertex_skins(obj) == model.vertex_skins
    for other in scenery_of_48_50().objects:
        if other.data is obj.data:
            assert rs_layers.read_vertex_skins(other) == model.vertex_skins, other.name


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


def drawn(material: bpy.types.Material | None) -> tuple[object, ...]:
    """The game values of a material and how it draws: its colour, its image, its render method and its culling."""
    assert material is not None
    image = material_image(material)
    rgba = [0.0] * 4
    material.diffuse_color.foreach_get(rgba)
    return (
        *material_values(material),
        tuple(round(c, 6) for c in rgba),
        None if image is None else image.name,
        material.surface_render_method,
        material.use_backface_culling,
    )


def scenery_meshes_of_48_50() -> list[bpy.types.Mesh]:
    scene = bpy.context.scene
    assert scene is not None
    region, _ = region_import.import_region(scene.collection, SNAPSHOT_430, 48, 50, BRIGHTNESS)
    (scenery,) = region.children
    return list({mesh_of(obj): None for obj in scenery.objects})


@needs_snapshot_430
def test_the_scenery_of_48_50_has_one_material_for_each_material_key(snapshot_430):
    # Issue 67 measured 325 material keys in the scenery of 48_50 on snapshot 430. Scenery passes no shown colours, so
    # the values, the image and the draw settings of a material give its key.
    meshes = scenery_meshes_of_48_50()

    materials = {material for mesh in meshes for material in mesh.materials}
    assert None not in materials
    assert len(materials) == len({drawn(material) for material in materials}) == 325


@needs_snapshot_430
def test_every_scenery_mesh_of_48_50_has_rs_lit_on_its_corners(snapshot_430):
    # ADR 0027: the region import bakes the loc light into `rs_lit`. The hand-made tests above check its values.
    meshes = scenery_meshes_of_48_50()

    assert meshes
    for mesh in meshes:
        attribute = mesh.color_attributes.get(appearance_preview.LIT_ATTRIBUTE)
        assert attribute is not None, mesh.name
        assert attribute.domain == "CORNER"
        assert len(attribute.data) == len(mesh.loops)


def drawn_scenery_faces_of_48_50() -> dict[str, list[tuple[object, ...]]]:
    """How each face of each scenery object of 48_50 draws, by object name."""
    scene = bpy.context.scene
    assert scene is not None
    region, _ = region_import.import_region(scene.collection, SNAPSHOT_430, 48, 50, BRIGHTNESS)
    (scenery,) = region.children
    return {
        obj.name: [drawn(mesh_of(obj).materials[polygon.material_index]) for polygon in mesh_of(obj).polygons]
        for obj in scenery.objects
    }


@needs_snapshot_430
def test_each_scenery_face_draws_as_the_material_of_its_own_model_import_would(snapshot_430, monkeypatch):
    def own_materials(*args, materials=None, **kwargs):
        return model_to_object(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(region_scenery, "model_to_object", own_materials)
        own = drawn_scenery_faces_of_48_50()
    # The second import starts from an empty file, so that its objects and images get the same names as the first.
    bpy.ops.wm.read_homefile(use_empty=True)
    shared = drawn_scenery_faces_of_48_50()

    assert own.keys() == shared.keys()
    for name, faces in shared.items():
        assert faces == own[name], name


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


@needs_snapshot_430
def test_a_failure_while_building_the_terrain_after_the_scenery_leaves_nothing_behind(snapshot_430, monkeypatch):
    # The scenery is made before the terrain, so a failure of the terrain comes after the scenery objects exist.
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
