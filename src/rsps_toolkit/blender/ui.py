from textwrap import wrap

import bpy

from . import rs_layers
from .animation import binding_warning, is_presentation


def draw_presentation_notice(layout, obj) -> None:
    if obj is not None and is_presentation(obj):
        notice = layout.box()
        notice.label(text="Presentation copy", icon="INFO")
        notice.label(text="DAT export is refused.")
        warning = binding_warning(obj)
        if warning:
            notice.alert = True
            for index, line in enumerate(wrap(warning, width=30)):
                notice.label(text=line, icon="ERROR" if index == 0 else "NONE")
        else:
            notice.label(text="Mesh edits need new playback.")
            notice.label(text="Recreate it from source.")


def item_import_note(obj) -> str | None:
    """What the importer showed for an object imported by item, or None for any other object. The note says what the
    import showed, not what the object shows now, because the user can change the materials afterwards."""
    stored = None if obj is None else rs_layers.read_item_import(obj)
    if stored is None:
        return None
    body = "female" if stored.body == "FEMALE" else "male"
    return (
        f"Imported from item {stored.item_name} ({stored.item_id}), {body} body. "
        "Shown colours follow the item's recolours. Export writes the model's own colours."
    )


def draw_item_import_note(layout, obj) -> None:
    note = item_import_note(obj)
    if note is not None:
        box = layout.box()
        box.label(text="Imported by item", icon="INFO")
        for line in wrap(note, width=30):
            box.label(text=line)


# --- PANEL ---
class VIEW3D_PT_rsps_model_io(bpy.types.Panel):
    """The UI panel for model import/export in the 3D View."""

    bl_label = "Model Exporter and Model Importer"
    bl_idname = "VIEW3D_PT_rsps_model_io"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        draw_presentation_notice(layout, context.active_object)
        draw_item_import_note(layout, context.active_object)

        # --- EXPORT SECTION ---
        export_box = layout.box()
        export_box.label(text="Step 3: Export Model", icon="EXPORT")

        if context.mode == "OBJECT":
            export_box.prop(scene, "exporter_output_dir")
            export_box.separator()
            # --- TWO MAIN EXPORT BUTTONS ---
            col = export_box.column(align=True)
            col.label(text="Preserve Source Data (recommended):")
            op = col.operator("export.rsps_model", text="Export DAT (Preserve Source)", icon="EXPORT")
            op.export_preset = "PRESERVE_SOURCE"
            op.auto_detect = False
            col.label(text="Writes the model as imported:")
            col.label(text=" no presets, no drop model, nothing removed")
            export_box.separator()

            col = export_box.column(align=True)
            col.label(text="DAT Export (Auto-Detect & Drop):")

            # Button 1: Weight-Based Auto-Detect
            op = col.operator("export.rsps_model", text="Export DAT (Weight-Based)", icon="WPAINT_HLT")
            op.export_preset = "DEFAULT"
            op.auto_detect = True

            col.label(text="Needs: VSKIN weights only")
            col.label(text="Automatically creates: Priorities & TSKINs")
            col.label(text="Detects: Head, Body, Gloves, Pants, Boots,")
            col.label(text=" Sword, Shield, Necklace, Cape")
            col.label(text="Creates both normal and _drop.dat files")

            export_box.separator()

            # Button 2: Color-Based Custom
            col = export_box.column(align=True)
            col.label(text="DAT Export (Color Layers & Drop):")

            op = col.operator("export.rsps_model", text="Export DAT (Custom Color)", icon="BRUSH_DATA")
            op.export_preset = "CUSTOM_PRIORITY"
            op.auto_detect = True

            col.label(text="Needs: RSPRI (priorities), RSTSKIN (texture skins),")
            col.label(text=" VSKIN (vertex groups) vertex color layers")
            col.label(text="For: Shield, Cape, NPCs & custom models")
            col.label(text="Auto-detects model type for drop files")
            col.label(text="Creates both normal and _drop.dat files")
            # --- RS STYLE BUTTON ---
            export_box.separator()
            export_box.operator("rsps.setup_runescape_style", text="Make Render RS Style", icon="RENDER_STILL")
        else:
            box = export_box.box()
            box.label(text="Switch to Object Mode to export.", icon="INFO")
            box.operator("object.mode_set", text="Enter Object Mode").mode = "OBJECT"

        # --- IMPORT SECTION ---
        import_box = layout.box()
        import_box.label(text="Import Models", icon="IMPORT")

        import_box.operator("import_scene.rs_model", text="Import RS Model", icon="IMPORT")
        import_box.operator(
            "import_scene.rs_model", text="Import OSRS 149 Model", icon="IMPORT"
        ).model_profile = "OSRS149"
        import_box.operator("rsps.upgrade_materials", icon="MATERIAL")
        import_box.label(text="Upgrade materials from older versions before exporting.")


# A tuple containing all classes from this file for registration by __init__.py
classes = (VIEW3D_PT_rsps_model_io,)
