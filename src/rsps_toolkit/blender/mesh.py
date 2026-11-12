"""Converts between a Model and a Blender mesh object."""

from collections.abc import Sequence
from dataclasses import replace

import bpy

from ..formats import InvalidModelError, Model, ModelEncoding, SetAsideFace, restore_faces, set_aside_faces, texture_uvs
from . import face_materials, model_source, rs_layers
from .face_materials import FindTexture

# The original exporter gave faces without a stored priority this value.
DEFAULT_PRIORITY = 1


def model_to_object(
    model: Model,
    name: str,
    find_texture: FindTexture | None = None,
    brightness: float = face_materials.DEFAULT_BRIGHTNESS,
    shown_colours: Sequence[int | None] | None = None,
) -> bpy.types.Object:
    """Create a mesh object for the model and link it to the active collection.

    Face colours show as the client's palette colours at the given brightness setting. `shown_colours`, one per face
    of the model, replaces the colour a face shows; the face still stores the model's own colour as its game value.

    Game y points down, so a game vertex (x, y, z) becomes Blender (x, z, -y), with Blender's z up. Faces that
    repeat a vertex are kept beside the mesh rather than in it, and object_to_model puts them back.
    """
    shown = shown_colours
    if shown is not None:
        if len(shown) != len(model.faces):
            raise ValueError(f"{len(shown)} shown colours for {len(model.faces)} faces")
        # The shown colours follow the faces that stay in the mesh, the same ones the model keeps.
        shown = set_aside_faces(replace(model, face_colours=list(shown)))[0].face_colours
    model, aside = set_aside_faces(model)
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata([(x, z, -y) for x, y, z in model.vertices], [], model.faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    slots: dict[tuple[int | None, int | None, int, int | None], int] = {}
    materials: list[bpy.types.Material] = []
    stacked = _stacked_textured_faces(model)
    shown_per_face = [None] * len(model.faces) if shown is None else shown
    for face, (polygon, colour, texture, alpha, shown_colour) in enumerate(
        zip(mesh.polygons, model.face_colours, model.face_textures, model.face_alphas, shown_per_face, strict=True)
    ):
        # A face that shows its own colour has the key of a plain import, so that import keeps its materials.
        shown_instead = None if shown_colour == colour else shown_colour
        key = (colour, texture, alpha, shown_instead)
        if key not in slots:
            slots[key] = len(materials)
            materials.append(
                face_materials.face_material(colour, texture, alpha, find_texture, brightness, shown_instead)
            )
            mesh.materials.append(materials[-1])
        polygon.material_index = slots[key]
        if face in stacked:
            face_materials.show_stacked(materials[slots[key]])
    for polygon, flat in zip(mesh.polygons, model.flat_shaded, strict=True):
        polygon.use_smooth = not flat
    vertex_records = (
        None
        if model.new_data is None
        else [kind == model_source.VERTEX_RECORD for kind in model.new_data.texture_render_types]
    )
    rs_layers.write_texture_triangles(mesh, model.texture_triangles, model.face_texture_triangles, vertex_records)
    _write_uvs(mesh, model)
    rs_layers.write_set_aside_faces(mesh, aside)
    model_source.write_source(mesh, model)
    model_source.mark_imported(mesh, model)

    rs_layers.write_face_values(mesh, rs_layers.PRIORITY_LAYER, model.render_priorities)
    if model.face_skins is not None:
        rs_layers.write_face_values(mesh, rs_layers.FACE_SKIN_LAYER, model.face_skins)
    if model.vertex_skins is not None:
        rs_layers.write_vertex_skins(obj, model.vertex_skins)
    return obj


def object_to_model(obj: bpy.types.Object) -> Model:
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        raise TypeError(f"object {obj.name!r} is not a mesh")
    priorities = rs_layers.read_face_values(mesh, rs_layers.PRIORITY_LAYER)
    slots = list(mesh.materials)
    values = [face_materials.material_values(slots[i] if i < len(slots) else None) for i in _material_indices(mesh)]
    texture_triangles, face_texture_triangles = rs_layers.read_texture_triangles(mesh)
    source = model_source.read_source(mesh)
    flat_shaded = [not p.use_smooth for p in mesh.polygons]
    if source is not None:
        _check_shading(source, flat_shaded)
    try:
        model = Model(
            vertices=_game_positions(mesh),
            faces=[_triangle(mesh, p) for p in mesh.polygons],
            face_colours=[colour for colour, _, _ in values],
            face_textures=[texture for _, texture, _ in values],
            face_alphas=[alpha for _, _, alpha in values],
            render_priorities=priorities or [DEFAULT_PRIORITY] * len(mesh.polygons),
            face_skins=rs_layers.read_face_values(mesh, rs_layers.FACE_SKIN_LAYER),
            vertex_skins=rs_layers.read_vertex_skins(obj),
            texture_triangles=texture_triangles,
            face_texture_triangles=face_texture_triangles,
            flat_shaded=flat_shaded,
            encoding=ModelEncoding.OLD if source is None else source.encoding,
            profile=None if source is None else source.profile,
            new_data=None if source is None else source.new_data,
        )
    except InvalidModelError as error:
        if source is None:
            raise
        raise InvalidModelError(
            f"{error}; the mesh no longer fits its stored source fields, so {model_source.REIMPORT_ADVICE}"
        ) from error
    return restore_faces(model, rs_layers.read_set_aside_faces(mesh))


def _check_shading(source: model_source.MeshSource, flat_shaded: list[bool]) -> None:
    """Raise ValueError when a face's flat or smooth shading in Blender no longer matches its source render type.

    Unverified: render types 1 and 3 are taken to be flat. What changing a render type does in the client is not
    established, so a shading edit is refused instead of being written into the render type.
    """
    for face, (render_type, flat) in enumerate(zip(source.new_data.face_render_types, flat_shaded, strict=True)):
        if render_type < 0:
            raise ValueError(
                f"face {face} was added after import and has no source render type; {model_source.REIMPORT_ADVICE}"
            )
        if flat != (render_type in (1, 3)):
            raise ValueError(
                f"face {face} was {'smooth' if flat else 'flat'} when imported (render type {render_type}) and its "
                f"shading was changed; {model_source.REIMPORT_ADVICE}"
            )


def matching_set_aside_faces(mesh: bpy.types.Mesh) -> tuple[list[SetAsideFace], int]:
    """The set-aside faces whose vertices are still where they were, and how many no longer are.

    Deleting or merging vertices in Blender, which Clean Up does to the vertices only these faces use, renumbers
    the vertices after them, so a stored face would name others.
    """
    positions = _game_positions(mesh)
    stored = rs_layers.read_set_aside_faces(mesh)
    matching = [
        face
        for face in stored
        if all(i < len(positions) and positions[i] == c for i, c in zip(face.face, face.corners, strict=True))
    ]
    return matching, len(stored) - len(matching)


def _stacked_textured_faces(model: Model) -> set[int]:
    """The textured faces whose corner positions are the same as another textured face's, in any order."""
    by_corners: dict[frozenset[tuple[int, int, int]], list[int]] = {}
    for face, (corners, texture) in enumerate(zip(model.faces, model.face_textures, strict=True)):
        if texture is not None:
            by_corners.setdefault(frozenset(model.vertices[i] for i in corners), []).append(face)
    return {face for faces in by_corners.values() if len(faces) > 1 for face in faces}


def _game_positions(mesh: bpy.types.Mesh) -> list[tuple[int, int, int]]:
    return [rs_layers.game_position(v.co) for v in mesh.vertices]


def _material_indices(mesh: bpy.types.Mesh) -> list[int]:
    indices = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", indices)
    return indices


def _write_uvs(mesh: bpy.types.Mesh, model: Model) -> None:
    # The client reads texel rows from v (Graphics3D.rasterTextureAffineLine in the 2018 client), so v runs down
    # the texture, while Blender's image origin is the bottom-left corner. Untextured faces get (0, 0).
    uvs = []
    for face in range(len(model.faces)):
        corners = texture_uvs(model, face) or ((0.0, 0.0),) * 3
        uvs += [c for u, v in corners for c in (u, 1 - v)]
    uv_layer = mesh.uv_layers.new(name=rs_layers.PREVIEW_UVS)
    uv_layer.data.foreach_set("uv", uvs)
    stored = [0.0] * len(uvs)
    uv_layer.data.foreach_get("uv", stored)
    signatures = [
        rs_layers.uv_signature(
            zip(
                stored[2 * p.loop_start : 2 * p.loop_start + 6 : 2],
                stored[2 * p.loop_start + 1 : 2 * p.loop_start + 6 : 2],
                strict=True,
            )
        )
        for p in mesh.polygons
    ]
    attribute = mesh.attributes.new(rs_layers.UV_SIGNATURE, "INT", "FACE")
    attribute.data.foreach_set("value", signatures)  # pyrefly: ignore[missing-attribute]


def _triangle(mesh: bpy.types.Mesh, polygon: bpy.types.MeshPolygon) -> tuple[int, int, int]:
    if polygon.loop_total != 3:
        raise ValueError(f"face {polygon.index} has {polygon.loop_total} corners; RuneScape models only hold triangles")
    start = polygon.loop_start
    return (mesh.loops[start].vertex_index, mesh.loops[start + 1].vertex_index, mesh.loops[start + 2].vertex_index)
