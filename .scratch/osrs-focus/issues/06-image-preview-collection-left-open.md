# Blender warns that an image preview collection was left open

Status: resolved

Blender prints a `ResourceWarning` that an `ImagePreviewCollection` was left open (recorded 2026-11-05, with or without a reload). Reproduced on 2026-11-09 in headless Blender 5.2 with Python warnings shown: registering the add-on, unregistering it and registering it again prints `ResourceWarning: <ImagePreviewCollection ...>: left open, remove with 'bpy.utils.previews.remove()'`. Whether the original add-on printed it too is unchecked.

## Decisions

The user chose on 2026-11-10:

1. The test registers and unregisters the add-on twice in headless Blender, then checks that no preview collection was left open.

## Comments

- 2026-11-10, triage with the user: ready-for-agent. It reproduces headless, and the add-on makes preview collections in three places (`blender/__init__.py`, `pmn_texturing.py` and `appearance_swatches.py`).
- 2026-11-10, agent: done.
  - Cause: `unregister` freed the PMN texture list's preview collection only `if pcoll:`. A preview collection is a dict, so the empty one that `register` makes counted as false and was never freed. Garbage collection then raised Blender's "left open" warning, once per register cycle. It now tests `is not None`.
  - Test: `tests/blender/test_register.py` registers and unregisters the add-on twice, makes a colour swatch in each cycle, and checks that Blender's set of open preview collections is unchanged. It failed on the old check (two collections left open) and fails when the swatch cleanup is removed (one left open).
  - Not changed: `unregister` in `blender/__init__.py` still frees the texture list's collection for `pmn_texturing`, which the review noted as older Feature Envy.
  - prek and the Blender suite pass.
