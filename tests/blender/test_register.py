import bpy.utils.previews

import rsps_toolkit.blender as addon
from rsps_toolkit.blender import appearance_swatches
from rsps_toolkit.formats import cache_profile


def test_registering_the_add_on_again_leaves_no_image_preview_collection_open():
    # The user chose that registering and unregistering the add-on twice leaves no preview collection open (issue 06,
    # decision 1, 2026-11-10). Blender 5.2 keeps every open collection in the private set `_uuid_open`, and only
    # `bpy.utils.previews.remove()` takes one out, so a leaked collection stays there even after garbage collection
    # (scripts/modules/bpy/utils/previews.py).
    before = set(bpy.utils.previews._uuid_open)  # pyrefly: ignore[missing-attribute]
    for _ in range(2):
        addon.register()
        # The colour swatches make their own collection the first time a colour dropdown draws, which registering
        # alone never does.
        appearance_swatches.icon(0)
        addon.unregister()
    assert set(bpy.utils.previews._uuid_open) == before  # pyrefly: ignore[missing-attribute]


def test_unregistering_the_add_on_drops_the_shared_cache_profiles(tmp_path):
    # The user chose on 2026-11-10 that unregistering the add-on clears the shared store of parsed catalogs (spec of the
    # shared catalog cache, Implementation Decisions, and ticket 01's Comments).
    addon.register()
    kept = cache_profile.shared_profile(tmp_path)
    addon.unregister()
    assert cache_profile.shared_profile(tmp_path) is not kept
