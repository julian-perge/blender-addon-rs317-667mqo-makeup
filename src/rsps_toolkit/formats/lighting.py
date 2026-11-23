"""The client's per-vertex model lighting. Nothing here imports bpy.

This follows `ModelData.light` and `computeNormals` in the May 2018 RuneLite tree (revision 170,
`runescape-client/src/main/java/ModelData.java` lines 1408 to 1480 and 1538 to 1718). The player cases are checked
against lit models that the unchanged revision 149 client produced (see `tests/fixtures/appearance/reference.json`).
Textured faces, faces with alpha 254 or 255, and faces of render type 2 or 3 are checked on hand-made models against
the arithmetic of those lines (`tests/unit/test_lighting.py`). `dv.ae` and `dv.z` of gamepack 149 take the same branches with the same
clamps (docs/research/textured-light.md, section 1). Flat-shaded faces are covered only by the male player
cases (8 faces) and the hand-made models, and 32-bit overflow of the face normal is not modelled.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .model import Model

# The ambient, contrast and light direction that the client passes when it lights a player body.
PLAYER_LIGHTING = (64, 850, -30, -50, -30)


@dataclass(frozen=True)
class Shading:
    """One lit value per face corner, the way the client stores them.

    For a face with `light_values` False, a corner holds a lit HSL colour. For a face with it True (a textured face),
    a corner holds a light value from 2 to 126 that the client multiplies the texture by. A flat face holds its one
    value in `corner_a`, 0 in `corner_b` and -1 in `corner_c`. An untextured face of render type 3 holds 128, 0 and
    -1, and a hidden face holds 0, 0 and -2.
    """

    corner_a: list[int]
    corner_b: list[int]
    corner_c: list[int]
    light_values: list[bool]


def _divide(numerator: int, denominator: int) -> int:
    """Integer division that rounds toward zero, as in Java."""
    quotient = abs(numerator) // abs(denominator)
    return quotient if (numerator < 0) == (denominator < 0) else -quotient


def _face_normal(model: Model, face: tuple[int, int, int]) -> tuple[int, int, int]:
    a, b, c = (model.vertices[i] for i in face)
    bx, by, bz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    cx, cy, cz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    x, y, z = by * cz - cy * bz, bz * cx - cz * bx, bx * cy - cx * by
    while max(abs(x), abs(y), abs(z)) > 8192:
        x, y, z = x >> 1, y >> 1, z >> 1
    length = max(math.isqrt(x * x + y * y + z * z), 1)
    return _divide(x * 256, length), _divide(y * 256, length), _divide(z * 256, length)


def _shade(colour: int, intensity: int) -> int:
    intensity = (colour & 127) * intensity >> 7
    return (colour & 0xFF80) + min(max(intensity, 2), 126)


def _lit(colour: int | None, intensity: int) -> int:
    """`method2639` (ModelData.java lines 1818 to 1827) for a face colour, and `method2676` (lines 1830 to 1838) for
    a textured face, which has no colour."""
    return min(max(intensity, 2), 126) if colour is None else _shade(colour, intensity)


def _stored_render_types(model: Model) -> list[int]:
    """The render type of each face as the client stores it before lighting.

    A model read from the new format keeps the byte it read (ModelData.java line 638). Any other model gives 1 for a
    flat face and 0 for any other, as the client stores an old-format model (lines 932 to 938). A model joined by
    `appearance.merge` or made by hand has no new-format data, so a stored render type 2 or 3 of a joined part is lost
    and the face is lit from its flat shading alone, unless the caller passes `joined_render_types` to `light`.
    """
    if model.new_data is not None:
        return list(model.new_data.face_render_types)
    return [1 if flat else 0 for flat in model.flat_shaded]


def joined_render_types(models: Sequence[Model]) -> list[int]:
    """The stored render type of each face of `models` joined in order, as `appearance.merge` joins them.

    The client's join copies the stored render type of each face of each part, and a part without render types stores
    0 (ModelData.java lines 192, 207 to 209, 255 and 256). Such a part has no flat face, so it gives 0 here too.
    """
    return [kind for model in models for kind in _stored_render_types(model)]


def light(
    model: Model,
    lighting: tuple[int, int, int, int, int] = PLAYER_LIGHTING,
    render_types: Sequence[int] | None = None,
) -> Shading:
    """Light an assembled model as `ModelData.light` does, with the lighting (ambient, contrast, x, y, z).

    `render_types` is the stored render type of each face. When it is None, they come from the model itself."""
    return _light(model, lighting, _stored_render_types(model) if render_types is None else render_types)


def _light(model: Model, lighting: tuple[int, int, int, int, int], render_types: Sequence[int]) -> Shading:
    ambient, contrast, lx, ly, lz = lighting
    divisor = (math.isqrt(lx * lx + ly * ly + lz * lz) * contrast) >> 8
    sums = [[0, 0, 0, 0] for _ in model.vertices]
    face_normals: dict[int, tuple[int, int, int]] = {}
    # computeNormals (ModelData.java lines 1444 to 1476) reads the stored render type and not the alpha. A face of
    # render type 0 adds its normal to its vertices, a face of render type 1 keeps its own, and any other adds nothing.
    for index, face in enumerate(model.faces):
        normal = _face_normal(model, face)
        if render_types[index] == 1:
            face_normals[index] = normal
        elif render_types[index] == 0:
            for vertex in face:
                total = sums[vertex]
                total[0] += normal[0]
                total[1] += normal[1]
                total[2] += normal[2]
                total[3] += 1
    corners: tuple[list[int], list[int], list[int]] = ([], [], [])
    light_values: list[bool] = []
    for index, face in enumerate(model.faces):
        textured = model.face_textures[index] is not None
        colour = None if textured else model.face_colours[index]
        if not textured and colour is None:
            raise ValueError(f"Face {index} has no colour to light")
        light_values.append(textured)
        # ModelData.java lines 1614 to 1620: alpha -2 (254) makes the render type 3 and alpha -1 (255) makes it 2.
        alpha = model.face_alphas[index]
        kind = 3 if alpha == 254 else 2 if alpha == 255 else render_types[index]
        if kind == 0:
            # Lines 1639 to 1663 for an untextured face and lines 1674 to 1698 for a textured one.
            for slot, vertex in enumerate(face):
                x, y, z, magnitude = sums[vertex]
                corners[slot].append(_lit(colour, _divide(ly * y + lz * z + lx * x, divisor * magnitude) + ambient))
            continue
        if kind == 1:
            # Lines 1627 to 1631 and 1666 to 1670. The client never writes the second corner, so it stays 0.
            x, y, z = face_normals[index]
            value = _lit(colour, _divide(ly * y + lz * z + lx * x, divisor // 2 + divisor) + ambient)
            row = (value, 0, -1)
        elif kind == 3 and not textured:
            # Lines 1632 to 1634.
            row = (128, 0, -1)
        else:
            # Lines 1635 and 1636 for an untextured face and 1671 and 1672 for a textured one hide the face.
            row = (0, 0, -2)
        for slot, value in enumerate(row):
            corners[slot].append(value)
    return Shading(*corners, light_values)
