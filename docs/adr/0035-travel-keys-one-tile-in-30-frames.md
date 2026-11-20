# Travel keys one tile in 30 frames

A clip moves the body of a player and not its place. A script that shows a walk must key the place itself. [Issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170) asks for a function that keys an actor along tiles at walk or run speed.

## Decision

- **A walk takes 30 frames for one tile.** The owner states in issue 170 that a walk moves 1 tile of 128 game units in 0.6 seconds. A baked clip plays at 50 frames in a second (`appearance_clip.CLIP_FPS`).
- **A run takes 15 frames for one tile.** This is general knowledge of the game (2 tiles in 0.6 seconds), and it is not checked in the client.
- **A step to a diagonal tile takes the time of a straight step.** The time of a step comes from the longer of its x and y distances. This is general knowledge of the game too, and it is not checked in the client.
- **`scripting.key_travel` keys the location of the rig object** at each point, with linear interpolation, and returns the frame of the last point.
- **The points are the script's.** They are places in the space of the rig object, such as tile centres from `Regions.tile_point`. The function does not read the terrain.
- **The player does not turn toward the direction of travel.** The script sets the rotation.

The walk speed is the owner's statement. The other points are guesses of the Spec stage.

## Rejected options

- **The speed from the client's movement code.** The client moves an actor by 4 game units in each 20 ms cycle and speeds up when it is behind, so its speed is not one number. The script wants the speed of the game tick.
