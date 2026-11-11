import bpy
import bpy.utils.previews

from ..formats import cache_profile

# Import all classes and functions from the other modules
from . import (
    aether_materials,
    appearance_clip,
    appearance_collection,
    appearance_files,
    appearance_items,
    appearance_panel,
    appearance_props,
    appearance_swatches,
    export_model,
    import_animation,
    import_model,
    importer_667,
    painter,
    pmn_texturing,
    preferences,
    render_style,
    ui,
    upgrade_materials,
    weighter,
)

classes = (
    *preferences.classes,
    *appearance_props.classes,
    *appearance_files.classes,
    *appearance_items.classes,
    *appearance_collection.classes,
    *appearance_clip.classes,
    *appearance_panel.classes,
    *weighter.classes,
    *ui.classes,
    *pmn_texturing.classes,
    *painter.classes,
    *render_style.classes,
    *aether_materials.classes,
    *import_model.classes,
    *import_animation.classes,
    *export_model.classes,
    *upgrade_materials.classes,
    *importer_667.classes,
)

label_draw_handler = None
priority_overlay_handler = None
priority_text_handler = None
tskin_overlay_handler = None
tskin_text_handler = None


def register():
    """Register all parts of the addon."""
    global \
        label_draw_handler, \
        priority_overlay_handler, \
        priority_text_handler, \
        tskin_overlay_handler, \
        tskin_text_handler

    # Register all classes FIRST
    for cls in classes:
        bpy.utils.register_class(cls)

    # THEN register scene properties AFTER the classes are registered
    weighter.register_properties()
    import_animation.register_properties()
    bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(
        name="Output Directory", description="Directory to export files", default="", subtype="DIR_PATH", maxlen=1024
    )
    painter.register_properties()
    appearance_props.register_properties()
    bpy.app.handlers.load_post.append(appearance_props.fill_scenes)
    # Registration runs where scene data may not be written, so the open file's scenes are filled a moment later.
    bpy.app.timers.register(appearance_props.fill_scenes, first_interval=0.0)
    appearance_collection.watch_selection()
    bpy.app.handlers.load_post.append(appearance_collection.watch_selection)
    bpy.app.handlers.undo_post.append(appearance_collection.follow_active_player)
    bpy.app.handlers.redo_post.append(appearance_collection.follow_active_player)

    # PMN properties
    bpy.types.Scene.rs_pmn = bpy.props.PointerProperty(type=pmn_texturing.RsPmnSceneProperties)

    # Register Aether properties
    bpy.types.Object.rgb_props = bpy.props.PointerProperty(type=aether_materials.RGBProperties)
    bpy.types.Scene.aether_rgb_props = bpy.props.PointerProperty(type=aether_materials.RGBProperties)

    if "main" not in pmn_texturing.preview_collections:
        pmn_texturing.preview_collections["main"] = bpy.utils.previews.new()

    # Add draw handlers with proper wrapper functions
    def label_draw_wrapper():
        weighter.draw_labels_callback(None, bpy.context)

    def priority_overlay_wrapper():
        painter.draw_overlay(bpy.context, painter.PRIORITY)

    def priority_text_wrapper():
        painter.draw_text(bpy.context, painter.PRIORITY)

    def tskin_overlay_wrapper():
        painter.draw_overlay(bpy.context, painter.FACE_SKIN)

    def tskin_text_wrapper():
        painter.draw_text(bpy.context, painter.FACE_SKIN)

    label_draw_handler = bpy.types.SpaceView3D.draw_handler_add(label_draw_wrapper, (), "WINDOW", "POST_PIXEL")
    priority_overlay_handler = bpy.types.SpaceView3D.draw_handler_add(
        priority_overlay_wrapper, (), "WINDOW", "POST_VIEW"
    )
    priority_text_handler = bpy.types.SpaceView3D.draw_handler_add(priority_text_wrapper, (), "WINDOW", "POST_PIXEL")
    tskin_overlay_handler = bpy.types.SpaceView3D.draw_handler_add(tskin_overlay_wrapper, (), "WINDOW", "POST_VIEW")
    tskin_text_handler = bpy.types.SpaceView3D.draw_handler_add(tskin_text_wrapper, (), "WINDOW", "POST_PIXEL")

    # The stubs type menu draw functions as taking only a context, but Blender passes the menu and the context.
    bpy.types.TOPBAR_MT_file_import.append(import_model.menu_entry)  # pyrefly: ignore[bad-argument-type]
    bpy.types.TOPBAR_MT_file_import.append(importer_667.menu_func_import_667)  # pyrefly: ignore[bad-argument-type]


def unregister():
    """Unregister all parts of the addon."""
    global \
        label_draw_handler, \
        priority_overlay_handler, \
        priority_text_handler, \
        tskin_overlay_handler, \
        tskin_text_handler

    bpy.types.TOPBAR_MT_file_import.remove(import_model.menu_entry)  # pyrefly: ignore[bad-argument-type]
    bpy.types.TOPBAR_MT_file_import.remove(importer_667.menu_func_import_667)  # pyrefly: ignore[bad-argument-type]

    # Remove draw handlers first
    if label_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(label_draw_handler, "WINDOW")
        label_draw_handler = None
    if priority_overlay_handler:
        bpy.types.SpaceView3D.draw_handler_remove(priority_overlay_handler, "WINDOW")
        priority_overlay_handler = None
    if priority_text_handler:
        bpy.types.SpaceView3D.draw_handler_remove(priority_text_handler, "WINDOW")
        priority_text_handler = None
    if tskin_overlay_handler:
        bpy.types.SpaceView3D.draw_handler_remove(tskin_overlay_handler, "WINDOW")
        tskin_overlay_handler = None
    if tskin_text_handler:
        bpy.types.SpaceView3D.draw_handler_remove(tskin_text_handler, "WINDOW")
        tskin_text_handler = None

    if pmn_texturing.pmn_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(pmn_texturing.pmn_draw_handler, "WINDOW")
        pmn_texturing.pmn_draw_handler = None

    pcoll = pmn_texturing.preview_collections.get("main")
    # A preview collection is a dict, so one with no previews loaded counts as false, and testing for None frees it too
    # (issue 06).
    if pcoll is not None:
        bpy.utils.previews.remove(pcoll)
    pmn_texturing.preview_collections.clear()

    # Clean up properties
    try:
        del bpy.types.Scene.exporter_output_dir
        del bpy.types.Scene.rs_pmn
        del bpy.types.Object.rgb_props
        del bpy.types.Scene.aether_rgb_props
    except AttributeError:
        pass

    painter.unregister_properties()
    if appearance_props.fill_scenes in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(appearance_props.fill_scenes)
    if bpy.app.timers.is_registered(appearance_props.fill_scenes):
        bpy.app.timers.unregister(appearance_props.fill_scenes)
    if appearance_collection.watch_selection in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(appearance_collection.watch_selection)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if appearance_collection.follow_active_player in handlers:
            handlers.remove(appearance_collection.follow_active_player)
    appearance_collection.stop_watching_selection()
    appearance_props.unregister_properties()
    appearance_swatches.unregister()
    cache_profile.clear_shared_profiles()
    weighter.unregister_properties()
    import_animation.unregister_properties()

    # Unregister classes LAST
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("✅ RSPS TOOLKIT unregistered!")
