# A chathead is an NPC collection lit with the widget light and posed with chat frames

A chathead is the head that the client shows in a dialogue box. Its models are the chathead models of the kits and the head models of the worn items of a player, or the chathead models of an NPC ([docs/research/chatheads.md](../research/chatheads.md)). The script of [issue 183](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/183) shows faces in close-up.

## Decision

- **A chathead is an NPC collection** ([ADR 0025](0025-an-npc-is-created-and-baked-only.md)), rigged for the frame map of a chat clip. Its record says that it is a chathead, and its NPC id is null, so the NPC panel gives it no Combat row.
- **The head model follows `hu.s` and `ip.e`.** For a player: each slot in order gives its kit chathead models or its item head models, the parts are joined, and the five colour choices recolour them as for the body. Nothing is moved by the item's body offset. For an NPC: its chathead models joined, recoloured and retextured, with no scale.
- **It is lit with the widget light** `(64, 768, -50, -10, -50)` of `hy.u`, for a player and for an NPC.
- **A chat clip poses with its chat frames.** For each step, `jg.p` applies the frame and then the chat frame to the same model. The bake of a chathead does both. A clip of an actor never uses the chat frames.
- **The rig is for the frame map of chatneu1 (588) by default**, which the human chat clips share (frame map 82). A script names another sequence for a goblin, an ent or a skull head.
- **The chat clip names come from `seq.sym`** of the osrs-dumps repo, under `"chat_clips"` in `data/animation_names.json`.

The models, the light and the chat frames are evidence from the client. The NPC collection, the default rig sequence and the name source are guesses of the Spec stage.

## Rejected options

- **The widget camera.** The client turns and zooms the head in the dialogue box. A script places its own camera.
- **The chat clip names in `"clips"`.** That list holds the clips that a player body can play, on frame map 0.
