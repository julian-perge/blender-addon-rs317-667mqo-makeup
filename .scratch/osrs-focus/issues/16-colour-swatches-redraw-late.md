# Colour swatches redraw only when the panel next draws

Status: resolved

After a Brightness change, the swatch icons of the colour dropdowns are drawn again only when the panel next draws ([plan 08](../plans/08-appearance-panel-steps.md)). Recorded 2026-11-07.

## Decisions

The user chose on 2026-11-10:

1. Changing Brightness asks every 3D view in every window to redraw, so the panel draws its colour swatches again at once. A test calls the Brightness setting's update with stand-in windows that record the redraw requests, since headless Blender has no windows, and the user then looks at the swatches in Blender.

## Comments

- 2026-11-10, triage with the user: ready-for-agent. A small UI fix. The redraw can only be checked live, so it ends with a look in Blender.
- 2026-11-10, agent: done. The Brightness preference's update callback (`preferences._redraw_3d_views`) asks every 3D view in every window to redraw, since Brightness is set in the Preferences window, whose screen holds no 3D view. `tests/blender/test_preferences.py` calls that update with stand-in windows (red before the fix, as the setting had no update). prek and the Blender suite pass.
- 2026-11-10, user: checked in Blender, with the add-on loaded from `src` and Brightness set from the Python console (an add-on loaded from `src` shows under Missing Add-ons in Preferences, without its settings). The swatches changed straight away.
