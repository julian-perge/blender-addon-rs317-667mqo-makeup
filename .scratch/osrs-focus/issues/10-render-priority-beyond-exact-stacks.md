# Render priority: overlaps that are not exact stacks, and priorities 10 and 11

Status: ready-for-human

`formats/face_order.visible_faces` leaves out a face that an exactly stacked face of the same winding paints over, as the client does ([research](../../../docs/research/render-priority.md)), and the preview mesh uses it. Not done: overlaps that are not exact stacks (the research note's Geometry Nodes normal-offset idea is a guess, never built), and priorities 10 and 11, which float with view depth. Whether this removed the torso speckle and the cape clipping was not checked by eye. Recorded 2026-11-07.

## Comments

- 2026-11-10, triage with the user: ready-for-human. The first step is the owner's look at whether the exact-stack rule removed the torso speckle and the cape clipping. The rest depends on it.
