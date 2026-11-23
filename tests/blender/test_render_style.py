import bpy
import pytest

import rsps_toolkit.blender as addon


@pytest.fixture
def registered():
    addon.register()
    bpy.ops.wm.read_homefile(use_empty=True)
    yield
    addon.unregister()


def eevee_engine() -> str:
    """The EEVEE engine as the running Blender names it: BLENDER_EEVEE_NEXT in 4.2 to 4.5, BLENDER_EEVEE in 5."""
    engine = bpy.types.RenderSettings.bl_rna.properties["engine"]
    assert isinstance(engine, bpy.types.EnumProperty)
    engines = [item.identifier for item in engine.enum_items]
    return next(engine for engine in engines if engine.startswith("BLENDER_EEVEE"))


# Issue 170, gap k: the operator failed on Blender 5.3 with "enum BLENDER_EEVEE_NEXT not found".
def test_make_render_rs_style_finishes_and_sets_the_eevee_engine_of_the_running_blender(registered):
    mesh = bpy.data.meshes.new("triangle")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(bpy.data.objects.new("triangle", mesh))

    assert bpy.ops.rsps.setup_runescape_style() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]

    assert scene.render.engine == eevee_engine()
