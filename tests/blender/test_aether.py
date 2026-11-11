from collections.abc import Iterator

import bpy
import pytest

from rsps_toolkit.blender import aether_materials
from rsps_toolkit.blender.mesh import model_to_object
from rsps_toolkit.formats import Model


@pytest.fixture(autouse=True)
def panel_registered() -> Iterator[None]:
    # The panel's parent belongs to another module, and these tests need only the properties and the operator.
    bpy.utils.register_class(aether_materials.RGBProperties)
    bpy.utils.register_class(aether_materials.AETHER_OT_ResetMaterials)
    bpy.types.Scene.aether_rgb_props = bpy.props.PointerProperty(type=aether_materials.RGBProperties)
    yield
    del bpy.types.Scene.aether_rgb_props
    bpy.utils.unregister_class(aether_materials.AETHER_OT_ResetMaterials)
    bpy.utils.unregister_class(aether_materials.RGBProperties)


@pytest.fixture
def stacked() -> bpy.types.Object:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    model = Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2), (0, 1, 2)],
        face_colours=[None, None],
        face_textures=[1, 2],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[False, False],
    )
    obj = model_to_object(model, "stacked")
    obj.select_set(True)
    aether_materials.store_original_colors(obj)
    return obj


def render_methods(obj: bpy.types.Object) -> set[str]:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return {m.surface_render_method for m in mesh.materials if m is not None}


def test_tinting_keeps_stacked_textured_faces_blended(stacked: bpy.types.Object):
    # The user chose blending for stacked faces, which showed black with the Dithered method that tinting used to set.
    aether_materials.refresh_materials(bpy.context)

    assert render_methods(stacked) == {"BLENDED"}


def test_resetting_keeps_stacked_textured_faces_blended(stacked: bpy.types.Object):
    bpy.ops.aether.reset_materials()  # pyrefly: ignore[missing-attribute]

    assert render_methods(stacked) == {"BLENDED"}


def test_resetting_a_material_that_is_not_stacked_still_stops_blending():
    # The user chose to leave every other material as it was, and resetting one used to set its blend method to OPAQUE.
    # Blender itself says what that gives.
    reference = bpy.data.materials.new("reference")
    reference.blend_method = "OPAQUE"
    model = Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        face_colours=[100],
        face_textures=[None],
        render_priorities=[0],
        face_alphas=[128],
        face_texture_triangles=[None],
        flat_shaded=[False],
    )
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    obj = model_to_object(model, "plain")
    obj.select_set(True)
    aether_materials.store_original_colors(obj)

    bpy.ops.aether.reset_materials()  # pyrefly: ignore[missing-attribute]

    assert render_methods(obj) == {reference.surface_render_method}
