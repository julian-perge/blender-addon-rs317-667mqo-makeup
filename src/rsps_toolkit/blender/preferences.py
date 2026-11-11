"""The add-on preferences, reading folder settings, and finding texture PNGs in the folders they point at."""

from pathlib import Path

import bpy

from .face_materials import DEFAULT_BRIGHTNESS

# Blender keys add-on preferences by the add-on's top package: rsps_toolkit when run from src/, and
# bl_ext.<repo>.rsps_toolkit when installed as an extension.
ADDON = __package__.rpartition(".")[0]


class RsToolkitPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON

    texture_folder: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Texture folder",
        description="Folder of <texture id>.png files, such as the unzipped texture_dump.zip",
        subtype="DIR_PATH",
    )
    cache_folder: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Cache folder",
        description="The js5 cache of OpenRS2 snapshot 430 (its cache/ folder, holding main_file_cache.dat2), which "
        "player kits, items, models and game clips are read from",
        subtype="DIR_PATH",
        update=lambda self, context: _fill_scenes(),
    )
    brightness: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Brightness",
        description="The client's brightness setting that imported face colours are shown at; export ignores it",
        items=[
            ("0.9", "0.9 (darkest)", ""),
            ("0.8", "0.8 (the client's default)", ""),
            ("0.7", "0.7", ""),
            ("0.6", "0.6 (brightest, as item icons)", ""),
        ],
        default=str(DEFAULT_BRIGHTNESS),
        update=lambda self, context: _redraw_3d_views(context),
    )

    def draw(self, context):
        self.layout.prop(self, "texture_folder")
        self.layout.prop(self, "cache_folder")
        self.layout.prop(self, "brightness")
        fallback = _user_texture_folder(create=False)
        if fallback is not None:
            self.layout.label(text=f"Also searched: {fallback}")


def brightness() -> float:
    """Return the brightness setting face colours are shown at, or the client's default when the add-on is not enabled."""
    addon = bpy.context.preferences.addons.get(ADDON)
    if addon is None:
        return DEFAULT_BRIGHTNESS
    return float(addon.preferences.brightness)


def cache_folder() -> Path | None:
    """Return the js5 cache folder from the preferences, or None when the add-on is not enabled or it is unset."""
    addon = bpy.context.preferences.addons.get(ADDON)
    if addon is None or not addon.preferences.cache_folder:
        return None
    return folder_in_setting(addon.preferences.cache_folder)


def find_texture(texture_id: int) -> Path | None:
    """Return the PNG for a texture ID from the preferences folder, then the extension's own texture_dump folder."""
    return first_texture(texture_folders(), texture_id)


def texture_folders() -> list[Path]:
    folders = []
    addon = bpy.context.preferences.addons.get(ADDON)
    if addon is not None and addon.preferences.texture_folder:
        folders.append(folder_in_setting(addon.preferences.texture_folder))
    fallback = _user_texture_folder()
    if fallback is not None:
        folders.append(fallback)
    return folders


def folder_in_setting(setting: str) -> Path:
    """Return the folder a path setting names, which may start with ~ or with Blender's // for the .blend's folder."""
    return Path(bpy.path.abspath(setting)).expanduser()


def first_texture(folders: list[Path], texture_id: int) -> Path | None:
    for folder in folders:
        path = folder / f"{texture_id}.png"
        if path.is_file():
            return path
    return None


def _redraw_3d_views(context: bpy.types.Context) -> None:
    """Redraw every 3D view in every window, so the Player Appearance panel draws its colour swatches again at the new
    Brightness at once. Brightness is set in the Preferences window, whose own screen holds no 3D view (issue 16, decision 1)."""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _fill_scenes() -> None:
    # appearance_props imports this module, so it is imported here, when the folder setting changes.
    from . import appearance_props

    appearance_props.fill_scenes()


def _user_texture_folder(create: bool = True) -> Path | None:
    # Only an installed extension has a user folder; running from src/ in tests raises ValueError.
    try:
        return Path(bpy.utils.extension_path_user(ADDON, path="texture_dump", create=create))
    except ValueError:
        return None


classes = (RsToolkitPreferences,)
