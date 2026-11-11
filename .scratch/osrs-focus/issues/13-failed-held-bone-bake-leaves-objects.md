# A failed bone bake of a held clip leaves its new objects behind

Status: resolved

A bone bake of a held clip that fails after `ensure_parts()`, in `_bone_rows` or while filling the action, leaves the new held item objects and label bones in the file, though `bake_clip_to_rig` says a failure adds nothing. `_bone_rows` needs those label bones, so the order cannot simply be swapped. Found in review on 2026-11-09 ([plan 12](../plans/12-held-items.md)); the behaviour is older than the posing change.

## Decisions

The user chose on 2026-11-10:

1. A bone bake that fails after it made the held items leaves the file's objects, meshes, bones and actions as they were.
2. The test forces the failure in the step after the held items are made (`appearance_bone_action.write`, through pytest's monkeypatch), since no real input is known to fail there.

After the review, the user chose on 2026-11-10:

3. A clip baked to end exactly where another strip on RS clips starts bakes fine. The review found that Blender refused that strip, because the baked action is keyed from frame 0 and Blender first sizes a new strip from the action's keys, one frame longer than the add-on's overlap check. The baked action gets its own frame range (Manual Frame Range, 1 to the clip's end) before the strip is added. The cleanup also covers adding the strip, and then removes the new action too. Steps after the strip is added (fades, visibility keys) stay outside it, and the docstring says so.
4. The shape-key bake gets the same cleanup of the held items it made, with a forced-failure test like the bone bake's.
5. A lit material that a failed bake made, because the file had none under that name, stays behind unused. Decision 1 does not list materials, and Blender drops unused data when the file is saved.
6. The cleanup through adding the strip is tested by forcing a failure at a small helper that adds the strip (`_add_clip_strip`), through pytest's monkeypatch, like decision 2.

## Comments

- 2026-11-10, triage with the user: ready-for-agent. `bake_clip_to_rig` promises that a failure adds nothing, and a forced failure after `ensure_parts()` can test it.
- 2026-11-10, agent: done.
  - Code: both bakes make the held items inside `appearance_held.held_items_undone_on_failure`, which removes the held objects and label bones a failed bake made. The bone bake also removes its new action when adding the strip fails. `_add_clip_strip` gives the action a Manual Frame Range of 1 to 1 + the clip's length before adding the strip, so a strip fits where it ends at the next strip's start.
  - Tests: one test with three cases forces the failure after the held items are made (at `appearance_bone_action.write`, `_add_clip_strip` and `appearance_shape_keys.write`). The test gives the Steel axe a label the player lacks, so the bake also adds a label bone; none of the held fixtures adds one by itself. A temporary break turned each case red. A second test bakes a clip that ends where the next strip starts; it was red before the fix, with "Unable to add strip".
  - Not undone, as decided: a track the bake made, a strip it replaced, the steps after the strip is in place (fades, visibility keys), and a lit material it made (decision 5).
  - Found while testing: when a test failed with an exception raised inside a bake that had removed its action, pytest's long traceback format crashed Blender (segmentation fault). `--tb=line` avoids it. Not investigated.
  - prek and the Blender suite (754 passed) pass. The first review round's findings were applied. The changes from decisions 3 to 6 were checked by rereading the diff, not by a second review round.
