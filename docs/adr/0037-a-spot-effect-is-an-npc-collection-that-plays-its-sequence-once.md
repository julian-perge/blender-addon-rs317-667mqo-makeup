# A spot effect is an NPC collection that plays its sequence once

A spot effect (spotanim) is a model with recolours, a sequence, a scale, a turn and light values ([docs/research/spot-effects.md](../research/spot-effects.md)). The script of [issue 183](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/183) shows smoke, steam and splashes on players.

## Decision

- **A spot effect is an NPC collection** ([ADR 0025](0025-an-npc-is-created-and-baked-only.md)): a lit mesh and a rig for the frame map of its sequence, created and baked only. Its record names the spot effect id.
- **It is lit with the light of `ii.v`:** `(64 + ambient, 850 + contrast, -30, -50, -30)`, with the ambient and the contrast as unsigned bytes with no factor.
- **The scale and the turn go on the rig object.** The client scales and turns the posed model (`ii.v` offsets 351 to 510), so the clip moves the vertices first.
- **It plays its sequence once.** The bake plays one cycle as a Pose from the start frame, and the mesh is hidden from the frame after the last tick, as `ap.fb` ends the graphic. The frame step and the loop count of the sequence do not count.
- **The anchor is a point or a joint.** At a point, the height lifts it as the client does. On a joint, `attach_to_joint` puts it there. The client has no joint anchor: it follows the actor's place. The joint anchor is the owner's wish of the package prompt.
- **Timing is the script's.** The server sends the delay of a spot effect, so the script gives the start frame.

The light, the order of the steps and the end are evidence from the client. The NPC collection, the joint anchor and the turn with the joint are guesses of the Spec stage.

## Rejected options

- **A shape key bake of the posed vertices.** The NPC bake already fits the client's posed vertices with joints and label bones, and Your motion can key over it.
- **A spot effect joined into the player's mesh, as the client joins it.** A player is rebuilt by Update Player, and the effect would go with it.
