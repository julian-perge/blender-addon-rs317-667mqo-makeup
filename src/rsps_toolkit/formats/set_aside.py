"""Faces that repeat a vertex, taken out of a model and put back.

Such faces have no area, and 1,753 of 27,612 Old School models hold some. Blender freezes entering Edit Mode on a
mesh with them, so import keeps them out of the mesh and export puts them back where they were.
"""

from dataclasses import dataclass, replace

from .model import Face, InvalidModelError, Model, Vertex


@dataclass(frozen=True)
class SetAsideFace:
    # The face's position in the model it was taken from.
    index: int
    face: Face
    # The positions of the face's three vertices when it was set aside, so a holder that renumbers vertices can
    # tell whether the face still names the same ones.
    corners: tuple[Vertex, Vertex, Vertex]
    colour: int | None
    texture: int | None
    alpha: int
    priority: int
    face_skin: int | None
    texture_triangle: int | None
    flat: bool
    textured_colour: int | None = None
    render_type: int | None = None


def set_aside_faces(model: Model) -> tuple[Model, list[SetAsideFace]]:
    """Return the model without the faces that repeat a vertex, and those faces in model order."""
    keep, aside = [], []
    source = model.new_data
    for i, face in enumerate(model.faces):
        if len(set(face)) == 3:
            keep.append(i)
            continue
        a, b, c = face
        aside.append(
            SetAsideFace(
                index=i,
                face=face,
                corners=(model.vertices[a], model.vertices[b], model.vertices[c]),
                colour=model.face_colours[i],
                texture=model.face_textures[i],
                alpha=model.face_alphas[i],
                priority=model.render_priorities[i],
                face_skin=None if model.face_skins is None else model.face_skins[i],
                texture_triangle=model.face_texture_triangles[i],
                flat=model.flat_shaded[i],
                textured_colour=None if source is None else source.textured_face_colours[i],
                render_type=None if source is None else source.face_render_types[i],
            )
        )
    skins = model.face_skins
    return replace(
        model,
        faces=[model.faces[i] for i in keep],
        face_colours=[model.face_colours[i] for i in keep],
        face_textures=[model.face_textures[i] for i in keep],
        face_alphas=[model.face_alphas[i] for i in keep],
        render_priorities=[model.render_priorities[i] for i in keep],
        face_skins=None if skins is None else [skins[i] for i in keep],
        face_texture_triangles=[model.face_texture_triangles[i] for i in keep],
        flat_shaded=[model.flat_shaded[i] for i in keep],
        new_data=None
        if source is None
        else replace(
            source,
            textured_face_colours=tuple(source.textured_face_colours[i] for i in keep),
            face_render_types=tuple(source.face_render_types[i] for i in keep),
        ),
    ), aside


def restore_faces(model: Model, aside: list[SetAsideFace]) -> Model:
    """Put set-aside faces back at their positions; a model without face skins gets none back."""
    faces, colours, textures = list(model.faces), list(model.face_colours), list(model.face_textures)
    alphas, priorities, flat = list(model.face_alphas), list(model.render_priorities), list(model.flat_shaded)
    triangles = list(model.face_texture_triangles)
    skins = None if model.face_skins is None else list(model.face_skins)
    source = model.new_data
    source_colours = [] if source is None else list(source.textured_face_colours)
    source_types = [] if source is None else list(source.face_render_types)
    # In ascending order each face lands at its old position, since every earlier face is already back.
    for face in sorted(aside, key=lambda f: f.index):
        at = min(face.index, len(faces))
        faces.insert(at, face.face)
        colours.insert(at, face.colour)
        textures.insert(at, face.texture)
        alphas.insert(at, face.alpha)
        priorities.insert(at, face.priority)
        triangles.insert(at, face.texture_triangle)
        flat.insert(at, face.flat)
        if skins is not None:
            skins.insert(at, face.face_skin or 0)
        if source is not None:
            if face.render_type is None or (face.texture is not None and face.textured_colour is None):
                raise InvalidModelError(
                    f"Set-aside face {face.index} lacks OSRS-149 source fields; reimport the original DAT"
                )
            source_colours.insert(at, face.textured_colour)
            source_types.insert(at, face.render_type)
    return replace(
        model,
        faces=faces,
        face_colours=colours,
        face_textures=textures,
        face_alphas=alphas,
        render_priorities=priorities,
        face_skins=skins,
        face_texture_triangles=triangles,
        flat_shaded=flat,
        new_data=None
        if source is None
        else replace(source, textured_face_colours=tuple(source_colours), face_render_types=tuple(source_types)),
    )
