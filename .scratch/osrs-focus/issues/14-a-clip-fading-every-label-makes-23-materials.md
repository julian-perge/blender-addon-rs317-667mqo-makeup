# A clip that fades every label makes 23 fade materials

Status: resolved

A bake groups the faces a clip fades by skin label and rest alpha, and each group gets its own material with an opacity driver ([plan 10](../plans/10-animate-the-player.md)). A clip that fades every label therefore makes one material per label, 23 in all. Recorded 2026-11-07.

## Decisions

The user chose on 2026-11-10, in a design interview:

1. Faces that fade alike share one fade material and one keyed property: same rest alpha and the same alpha on every frame. (Fact: sequence 1994 makes 23 fade groups on both bodies, all with the same alpha on every frame, so it would make 1 material; sequences 1697 and 3182 make none.)
2. A bone bake merges only faces that fade alike in every clip on the rig, and works this out again on each bake. A shape-key bake, which holds one clip, merges within that clip.
3. When a new bone clip splits a shared group, each earlier clip's action gets the split-off property keyed with the shared property's curve, and its stored key hash is updated, so the player stays unedited and no clip is baked again.
4. A shared property and material are named after the group's lowest label and its rest alpha (`rs_fade_<label>_<rest>`, "<mesh> fade <label>"), so a group of one label keeps today's name.
5. Players baked before this change keep one fade material per label until their next bake or Update.

## Comments

- 2026-11-10, triage with the user: needs-info. Whether labels with identical fades should share one material is the owner's call.
- 2026-11-10, design interview with the user: decisions 1 to 5, ready-for-agent. GLOSSARY.md gained Fade group. The implementation agrees its test seams with the user first.
- 2026-11-10, agent: the spec is the scratch spec (deleted after the merge) (ready-for-agent). The user agreed one test seam, the two bake functions, plus a newly recorded clip fixture with label-specific fades for the split case.
- 2026-11-12, agent: resolved. The three tickets of the scratch folder (deleted after the merge) were built and merged (pull request 7). The plan is in `tasks/done/shared-fade-groups/`.
