# Export warns about moved texture triangles instead of giving vertices stable IDs

Texture triangles name vertices by number, so deleting or merging vertices in Blender can leave a triangle on the wrong vertices. On 2026-11-05 the owner chose a warning over stable vertex IDs. Import and `texture_triangles.add` record each triangle's game positions in the mesh property `rs_texture_triangle_corners`, and export counts the triangles faces use whose vertices are no longer at those positions. The file is still written, unless a triangle names a vertex past the last, which export refuses.

The owner confirmed these warning rules the same day:

- Moving a vertex on purpose warns too, as for set-aside faces, because positions cannot tell a move from renumbering, and it keeps warning until the triangle is set again. So Apply Scale warns on every triangle.
- A triangle used only by set-aside faces does not count, since those faces have no area.
- Setting a triangle that already exists accepts its current positions, which also quiets other faces using it.
- Files saved before the positions were recorded never warn until their triangles are set again.

On 2026-11-05 the owner also deferred repairing the storage. Edit Mode Undo restores vertices but not the mesh's properties, so the Texture Tool warns that Edit Mode Undo does not restore triangle records and tells the user to set triangles again after undoing Apply or Fit, and the export warning explains the same limit. Object Mode Undo restores the records.

Accepted gaps: the warning gives a count and does not name the faces. Fit clears it only in part: after deleting vertex 0, 13 of the 1,010 affected models keep warning, because Fit refuses triangles with no area or with UVs on one line (seen on models 528, 3153 and 6822). Fit with all of 5452's faces selected clears the warning by collapsing its 58 triangles to 1, and Fit per triangle leaves 4 of its 128 textured faces on positions different from the original. Joining objects is untested. A move of less than half a game unit does not count, since positions are compared as game integers.

Measured on 2026-11-05: deleting vertex 14 of model 5452 moves 40 of its 58 triangles, the same count as comparing the exported and original models; none of the 7,456 models of the 317 cache warns as imported, and all still round-trip exactly.
