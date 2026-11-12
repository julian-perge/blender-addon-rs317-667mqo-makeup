Spec: spec/old/play-as-from-clip.md

# Implementation Plan: Picking a clip sets Play As

Branch: `feat/play-as-from-clip`. One commit per task. Tasks are in `tasks/old/play-as-from-clip/todo.md`. Issue: issue 21 of `.scratch/osrs-focus/`.

## Overview

`rsps.pick_clip` sets only `clip_sequence`. After this change it also sets `clip_play_as`: Pose when the picked clip is a stance clip in the weapon clip table, Action for every other clip. The panel, the bake operator and the Stance and Attack buttons stay as they are.

## What the code reading found

- The whole change is in `RSPS_OT_pick_clip.execute` ([appearance_clip.py:443](src/rsps_toolkit/blender/appearance_clip.py:443)). It runs `context.scene.rs_appearance.clip_sequence = int(self.clip)` and stops. `RSPS_OT_pick_weapon_clip.execute` already sets both properties, so the new code follows that pattern.
- `WeaponClipTable` ([formats/weapon_clips.py:29](src/rsps_toolkit/formats/weapon_clips.py:29)) holds `unarmed` and `items` (item id to `WeaponClips`). It has no set of all stance clips. `weapon_clip_table()` in `appearance_clip.py` already caches the loaded table, so the picker reads the same table as the buttons (spec: "the rule follows the table if it is regenerated").
- Checked against `data/weapon_clips.json` on 2026-11-11 (evidence, not a guess):
  - All 110 sets are used by an item or are the unarmed set. Reading `unarmed` plus every `items` value therefore gives the same stance clips as reading every set: 138 distinct ids.
  - No id is in both a stance list and an attack list, so "stance clip" and "attack clip" never conflict.
  - 808 is a stance clip. 1365 and the attack clips are not.
  - The table has `-1` for a missing clip. A picked clip is never -1, but the lookup must not be fooled by it.
- The `disagreements` block lists the plugin's clips for some items. It is not part of any set, so the rule ignores it. The whip's plugin stance clips (1660 and 1661) are also in the whip's own set, so 1660 stays a Pose.
- The panel reads `clip_play_as` on every redraw (the held-items hint). No panel change is needed: the hint already shows when a held-item clip is switched back to Pose (user story 8).
- The test seam is agreed: the spec names the picker operator, and the issue 21 comment records that the user agreed it on 2026-11-10. The existing picker test is `test_picking_a_clip_stores_its_sequence_and_the_panel_names_it` (tests/blender/test_appearance_clip.py:676). The picker reads clip names from the add-on data, not the cache, but the existing tests use the `cache` fixture, so the new ones do too.

## Dependency graph

```
T1 pick sets Play As (lookup + picker + tests)
 └─ T2 wording, glossary, close issues, archive plan
```

There is one behavior, so T1 is one slice. A separate task for the lookup would be a horizontal layer with no seam of its own: the spec allows one seam, the picker.

## Architecture decisions

- Add a stance-clip lookup to `WeaponClipTable` (pure, in `formats/`, no bpy): `is_stance_clip(sequence_id)`, which scans the stance lists of `unarmed` and `items` on each call (about 56 microseconds, measured in review, so no cached set). It has no `-1` guard: no stance list holds -1 and `clip_sequence` has `min=0`. The picker calls it. Reason: `formats/weapon_clips.py` owns the table shape, and the rule must follow the table.
- The lookup has no test of its own. Its behavior is tested through the picker (spec "Testing Decisions": one seam). If a coverage gap shows, say so in the task result and ask the user before adding a seam.
- No new property and no new operator. `PLAY_AS_ITEMS` stays.

## Task list

See `tasks/old/play-as-from-clip/todo.md`. Two tasks, one checkpoint.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| A test passes because Play As was already Pose or Action (the default is Pose) | High | Each case sets Play As to the opposite value first, then picks. |
| An emote id picked for the test is really in a stance list | Med | Look it up in `weapon_clips.json` when the test is written, and cite it in the test comment. |
| The picker overwrites a user's change on a later pick | Low | By the spec this is intended: "the user's later change is kept until the next pick". A test covers the change after a pick. |
| Held-item hint hidden after a pick | Low | Hint logic is unchanged and is covered by `test_..._holds_items` at line 1234. Check by eye once in Blender (`docs/agents/blender.md`) if the user wants it. |

## Open questions

- None blocking. One for the user at the commit review: the spec adds no ADR. Issue 21 and ADR 0014 hold the decisions. T2 adds one sentence to ADR 0014 only if the user agrees.
