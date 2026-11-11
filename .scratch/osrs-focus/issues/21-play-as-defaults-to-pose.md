# Play As defaults to Pose

Status: ready-for-agent

The bake's Play As setting (`clip_play_as`) defaults to Pose. That is an agent choice: neither the cache nor a clip says whether the server plays a sequence as the pose or as the action. A pose sequence starts at frame 0 and ignores the loop offset, and an action plays once or loops by its loop offset ([clip coverage](../../../docs/research/osrs-149-animation.md#clip-coverage-2026-11-07)). Recorded 2026-11-07.

## Decisions

The user chose on 2026-11-10, in a design interview:

1. Picking a clip by name sets Play As: Pose when the clip is one of the stance clips in the weapon clip table (the unarmed set or any weapon's stand, turn, walk or run clips), Action for every other clip. The user can still change it after picking.
2. Before any clip is picked, Play As stays Pose. The Stance and Attack buttons keep setting it as ADR 0014 says.

## Task

- [ ] Agree the test seam with the user first.
- [ ] Picking a stance clip by name sets Play As to Pose, and picking any other clip sets it to Action.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.

## Comments

- 2026-11-10, design interview with the user: decisions 1 and 2, ready-for-agent.
- 2026-11-10, agent: the spec is [.scratch/play-as-from-clip/spec.md](../../play-as-from-clip/spec.md) (ready-for-agent). The user agreed one test seam, the clip picker operator.
