"""The terrain mesh of a region: one object for the level 0 tiles, with the client's lit colour at each face corner.

The south-west corner of the region is at Blender (0, 0, 0) (spec 35, decision 5). One game unit is one Blender unit, as
in model import, so one tile is 128 units wide. The game's height points down, so a Blender z is the height negated.

The mesh stores no game values, and export does not read it. Its colours and texture coordinates are only for showing
the terrain, so a user can edit or delete its vertices freely.
"""

from collections.abc import Mapping, Sequence

import bpy

from ..formats import face_colour_to_rgb
from ..formats.floor_definition import Overlay, Underlay
from ..formats.region import REGION_SIZE, Terrain
from ..formats.region_colours import HIDDEN, tile_colours
from ..formats.region_shapes import Corner, TilePoint, tile_triangles
from ..formats.texture_uvs import projected_uvs
from .face_materials import srgb_to_linear

TILE_SIZE = 128
TERRAIN_COLOUR = "rs_terrain_colour"
UV_MAP = "UVMap"
NO_TEXTURE = -1

_CORNERS = list(Corner)

type Position = tuple[int, int, int]


def terrain_object(
    name: str,
    terrain: Terrain,
    underlays: Mapping[int, Underlay],
    overlays: Mapping[int, Overlay],
    images: Mapping[int, bpy.types.Image],
    brightness: float,
) -> bpy.types.Object:
    """A new object, linked to no collection, with the level 0 tiles of the terrain's region.

    `underlays` and `overlays` hold the floor definitions by id. `images` holds the decoded image of each texture that an
    overlay of the region uses, by texture id. `brightness` is the Brightness preference that the colours are shown at.

    Each tile gets the triangles of `region_shapes.tile_triangles`. A triangle whose first point has the colour `HIDDEN`
    and no texture is not drawn, because the client checks only that colour (`Region.java` lines 1852, 1879 and 1967).
    Tiles share the vertices at the points where they meet.
    """
    vertices: dict[Position, int] = {}
    faces: list[tuple[int, int, int]] = []
    textures: list[int] = []
    colours: list[float] = []
    uvs: list[float] = []
    for x in range(REGION_SIZE):
        for y in range(REGION_SIZE):
            lit = tile_colours(terrain, x, y, underlays, overlays)
            if lit is None:
                continue
            heights = [terrain.tile(0, x + dx, y + dy).height for dx, dy in (corner.value for corner in _CORNERS)]
            flat = len(set(heights)) == 1
            for triangle in tile_triangles(terrain.tile(0, x, y)):
                values = lit.overlay if triangle.overlay else lit.underlay
                # A tile gets overlay triangles and overlay colours only when it has an overlay, so this never fails.
                assert values is not None
                texture = lit.texture if triangle.overlay else NO_TEXTURE
                if texture == NO_TEXTURE and _point_value(values, triangle.points[0]) == HIDDEN:
                    continue
                positions = [_position(x, y, point, heights) for point in triangle.points]
                a, b, c = (vertices.setdefault(position, len(vertices)) for position in positions)
                faces.append((a, b, c))
                textures.append(texture)
                for point in triangle.points:
                    value = _point_value(values, point)
                    colours += _shade(value) if texture != NO_TEXTURE else _colour(value, brightness)
                uvs += _texture_uvs(x, y, positions, heights, flat) if texture != NO_TEXTURE else [0.0] * 6
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(px, py, -height) for px, py, height in vertices], [], faces)
    slots = {NO_TEXTURE: 0}
    mesh.materials.append(_colour_material())
    for texture in sorted(set(textures) - {NO_TEXTURE}):
        slots[texture] = len(slots)
        mesh.materials.append(_texture_material(texture, images[texture]))
    mesh.polygons.foreach_set("material_index", [slots[texture] for texture in textures])
    attribute = mesh.color_attributes.new(TERRAIN_COLOUR, "FLOAT_COLOR", "CORNER")
    attribute.data.foreach_set("color", colours)
    mesh.color_attributes.active_color = attribute
    mesh.color_attributes.render_color_index = mesh.color_attributes.find(TERRAIN_COLOUR)
    mesh.uv_layers.new(name=UV_MAP).data.foreach_set("uv", uvs)
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def _position(x: int, y: int, point: TilePoint, heights: list[int]) -> Position:
    """The game position of a tile point: x east and y north in game units from the region's south-west corner, and the
    height, which `_point_value` gives from the heights of the tile's corners."""
    return x * TILE_SIZE + point.x, y * TILE_SIZE + point.y, _point_value(heights, point)


def _point_value(values: Sequence[int], point: TilePoint) -> int:
    """The height, colour or light of a tile point, from the values of the tile's corners in the order of `Corner`. A
    point between two corners has the sum of theirs shifted right by 1 (`SceneTileModel.java` lines 124 to 220)."""
    picked = [values[_CORNERS.index(corner)] for corner in point.corners]
    return picked[0] if len(picked) == 1 else (picked[0] + picked[1]) >> 1


def _colour(colour: int, brightness: float) -> list[float]:
    return [*(srgb_to_linear(channel / 255) for channel in face_colour_to_rgb(colour, brightness)), 1.0]


def _shade(light: int) -> list[float]:
    """The grey that the texture of a textured overlay is multiplied by. The client multiplies each channel of a texel
    by the light shifted left by 9 (`Graphics3D.java` line 2532) and then by that value shifted right by 8 and the
    product shifted right by 8 (line 3295), so by the light over 128. The client multiplies the shown 0 to 255 values,
    and Blender multiplies linear values. Both give the same product only for a pure power curve, which the sRGB curve
    is close to, so the shown colour is close to the client's but not exact."""
    grey = srgb_to_linear(light / 128)
    return [grey, grey, grey, 1.0]


def _texture_uvs(x: int, y: int, positions: list[Position], heights: list[int], flat: bool) -> list[float]:
    """The texture coordinates of a textured triangle. On a tile whose 4 corner heights are equal, the client maps every
    triangle with the south-west corner as P, the south-east corner as M and the north-west corner as N (`Region.java`
    lines 1856 to 1857, 1883 and 1958 to 1959). On another tile, each triangle has its own points as P, M and N, in the
    order that the client draws them (lines 1858 to 1859, 1883 and 1960 to 1961). The south-west triangle of a tile
    without a shape has those three corners as its own points, so both rules give it the same mapping (line 1883).

    The client draws the texture of a tile with the same `Graphics3D.rasterTexture` as the face of a model, so the
    coordinates are made as model import makes them: P is (0, 0), M is (1, 0) and N is (0, 1), and Blender's v is 1 less
    the client's, because the rows of a Blender image start at the bottom."""
    if flat:
        south_west, south_east, _, north_west = (
            (x * TILE_SIZE + dx * TILE_SIZE, y * TILE_SIZE + dy * TILE_SIZE, heights[i])
            for i, (dx, dy) in enumerate(corner.value for corner in _CORNERS)
        )
        pmn = (south_west, south_east, north_west)
    else:
        pmn = (positions[0], positions[1], positions[2])
    a, b, c = (_vector(position) for position in positions)
    p, m, n = (_vector(position) for position in pmn)
    corners = projected_uvs((a, b, c), (p, m, n))
    return [value for u, v in corners for value in (u, 1 - v)]


def _vector(position: Position) -> tuple[float, float, float]:
    x, y, height = position
    return float(x), float(y), float(height)


def _colour_material() -> bpy.types.Material:
    """A material that shows the lit corner colours unshaded, because they already hold the client's light. It hides the
    back of each face, as the client does (`Region.java` lines 1840, 1867 and 1945)."""
    material = bpy.data.materials.new("RS Terrain")
    nodes, links = _emission_tree(material)
    attribute = nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = TERRAIN_COLOUR
    links.new(attribute.outputs["Color"], nodes["Emission"].inputs["Color"])
    return material


def _texture_material(texture: int, image: bpy.types.Image) -> bpy.types.Material:
    """A material that shows the decoded image times the corner shade, unshaded. A transparent texel is not drawn, as in
    the client (`face_materials.texture_image`). The image is read one texel per pixel without filtering, as model
    import reads it."""
    material = bpy.data.materials.new(f"RS Terrain Texture {texture}")
    nodes, links = _emission_tree(material)
    texels = nodes.new("ShaderNodeTexImage")
    texels.image = image
    texels.interpolation = "Closest"
    attribute = nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = TERRAIN_COLOUR
    multiply = nodes.new("ShaderNodeMix")
    multiply.data_type = "RGBA"
    multiply.blend_type = "MULTIPLY"
    multiply.inputs["Factor"].default_value = 1.0
    links.new(texels.outputs["Color"], multiply.inputs["A"])
    links.new(attribute.outputs["Color"], multiply.inputs["B"])
    links.new(multiply.outputs["Result"], nodes["Emission"].inputs["Color"])
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(texels.outputs["Alpha"], mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(nodes["Emission"].outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    return material


def _emission_tree(material: bpy.types.Material) -> tuple[bpy.types.Nodes, bpy.types.NodeLinks]:
    if material.node_tree is None:
        material.use_nodes = True
    material.use_backface_culling = True
    tree = material.node_tree
    assert tree is not None
    nodes, links = tree.nodes, tree.links
    nodes.remove(nodes["Principled BSDF"])
    emission = nodes.new("ShaderNodeEmission")
    emission.name = "Emission"
    links.new(emission.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    return nodes, links
