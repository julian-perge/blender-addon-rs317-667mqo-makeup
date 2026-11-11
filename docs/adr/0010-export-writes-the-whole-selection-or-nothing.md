# Export writes the whole selection as it is now, or nothing

The owner chose on 2026-11-05 that export includes the current Edit Mode edits. `model_files` calls `obj.update_from_editmode()` before evaluating the mesh, its modifiers and drop transforms, export stays in Edit Mode, and its moved-triangle and set-aside-face checks read the synchronized mesh.

Every export preset is also all-or-nothing for the selection: one invalid object writes no files. This was agreed with the owner in the cache-430 static support work (plan 02, Task 4), following the approved design's rule that an invalid selected batch writes nothing.
