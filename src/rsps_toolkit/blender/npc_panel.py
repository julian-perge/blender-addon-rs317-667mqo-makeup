"""The View3D sidebar panel for NPCs, below Player Appearance (spec 13, Panel)."""

import bpy

from . import npc_collection, preferences


class VIEW3D_PT_rsps_npc(bpy.types.Panel):
    bl_label = "NPC"
    bl_idname = "VIEW3D_PT_rsps_npc"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RSPS ADDON"

    def draw(self, context):
        layout = self.layout
        addon = context.preferences.addons.get(preferences.ADDON)
        if addon is not None:
            layout.prop(addon.preferences, "cache_folder")
        else:
            layout.label(text="Enable the RSPS Toolkit add-on to set the cache folder", icon="ERROR")
        row = layout.row()
        row.prop(context.scene, "rs_npc_id")
        row.operator(npc_collection.RSPS_OT_create_npc.bl_idname, icon="ADD").npc_id = context.scene.rs_npc_id


classes = (VIEW3D_PT_rsps_npc,)
