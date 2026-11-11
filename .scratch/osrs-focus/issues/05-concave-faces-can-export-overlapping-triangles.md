# Concave faces can export as overlapping triangles

Status: resolved

`bmesh.ops.triangulate` never returns on model 6658 (faces with a repeated vertex), with or without faces to split, so export splits faces with more than 3 corners into fans with `bmesh.utils.face_split` (`blender/export_model.py`). The fan of a concave face can come out with overlapping triangles. Recorded 2026-11-05; the fan split is still in place on 2026-11-09.

## Decisions

The user chose on 2026-11-10:

1. Export splits a face with more than 3 corners into triangles that all face the same way as the face and cover it exactly once. The test exports a dented pentagon through the RS Model exporter and checks that the triangles' areas add up to the face's area, from the shoelace formula on the test's own corners.

After the review, the user chose on 2026-11-10:

2. When several corners can be cut cleanly, the first in corner order goes first, so faces that were already convex export as before.
3. A face with no corner that can be cut cleanly (a self-crossing face, one with no area, or one that repeats a vertex) is still split in the old corner order, and the export reports a warning saying how many cuts may have made overlapping triangles.

## Comments

- 2026-11-10, triage with the user: ready-for-agent. The bug is clear, and an export of a concave face can be tested for triangles that overlap.
- 2026-11-10, agent: done.
  - Code: `_split_off_corner` in `blender/export_model.py` cuts the first corner, in corner order, whose triangle lies inside the face (`_is_ear`: the corner turns the face's way and no other corner lies in or on the triangle). A face with no such corner is cut in the old order, and export warns how many such cuts each object needed.
  - Tests: a dented pentagon exports as 3 triangles that face one way and add up to its area (red before the fix, with a triangle facing the other way). A quad with its corners on one line exports with the warning.
  - Not covered, from the review: the area test compares the triangles with each other, not with the face's own direction. On a face that repeats a vertex, `face_split` cuts at the first loop holding the chosen vertex, which may differ from the corner that was checked, as before this change.
  - prek and the Blender suite pass.
