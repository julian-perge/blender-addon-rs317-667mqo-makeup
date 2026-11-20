# The wall decoration offset moves objects along their mean face normal

The client draws a wall decoration (loc types 4 to 8) after the wall that it hangs on, so the decoration always shows. Blender has only the depth test. A decoration is about 0.8 game units in front of its wall, and in EEVEE the wall showed through in other pixels on each frame. In the calling repo, a move of 2 game units along the mean face normal fixed it for the 290 wall decoration objects of region 51_49, and back-face culling, a larger near clip and priority offsets did not ([issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170), gap i).

## Decision

- **`import_region` takes `decoration_offset`, in game units, with the default 0.** The operator does not pass it, so an import by the user is as before.
- **Each object of a placement with loc type 4 to 8 moves by the offset along the mean of its face normals,** weighted by face area, in the space of the region. A wall decoration of type 8 has two objects, and each moves along its own mean.
- **The move changes the location of the object only.** The mesh, its stored model data and the shared meshes stay as they are.
- **An object whose normals sum to zero does not move.**
- **The offset is not what the client does.** The glTF export and any other reader of the scenery see the moved objects. A scene for the page of [ADR 0026](0026-the-gltf-page-draws-the-baked-client-light.md) imports without the offset.

The owner chose the mean face normal and the option in issue 170. The default of 0 and the zero-sum rule are guesses of the Spec stage.

## Rejected options

- **The direction that the client moves a decoration from its wall.** It needs the facing of each of the five types, and the measured fix used the face normals.
- **A fixed offset that is always on.** It changes the place of scenery for every user.
