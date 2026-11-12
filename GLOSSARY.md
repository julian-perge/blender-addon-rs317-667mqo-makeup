# RSPS Toolkit

Vocabulary for editing RuneScape client models in Blender: reading them from a game cache, painting their game-specific data, and writing them back in the game's binary format.

## Formats and versions

**Revision**:
The build number of a RuneScape client and its cache, such as 317 (RuneScape 2, 2005) or 667 (2011). Old School RuneScape restarted the count at 1 in February 2013.
_Avoid_: version, build

**Model**:
One mesh as the game client stores it: vertices, triangle faces and per-face and per-vertex game data, with no skeleton and no UVs.
_Avoid_: mesh (reserve for the Blender object), object, .dat

**Model encoding**:
The binary layout used to store one model. A cache snapshot can contain models using different encodings, so a model encoding is distinct from the client revision.
_Avoid_: cache format, client revision

**Old model format**:
The model encoding used by revision 317 and early Old School, identified by an 18-byte footer of counts and section flags at the end of the file.
_Avoid_: 317 format, OSRS format, decode1

**New model format**:
A family of later model encodings whose footer ends in `FF FF`, used in both RuneScape 2 and OSRS. A shared marker does not establish that different client revisions interpret every field the same way.
_Avoid_: 667 format, versioned format

**Cache**:
The client's packed game data store, holding models, textures, animations and maps as numbered files in numbered indexes.
_Avoid_: dump, archive

**Cache snapshot**:
A particular archived copy of a game's cache. An OpenRS2 snapshot ID identifies the archived copy, while a client revision identifies the game build.
_Avoid_: revision (when referring to the archived copy)

**OpenRS2 snapshot ID**:
The catalog identifier of a cache snapshot in the OpenRS2 Archive. Snapshot 430 contains an OSRS revision 149 cache; the two numbers identify different things.
_Avoid_: client revision, JS5 archive ID

**Texture dump**:
A folder of texture images extracted from a cache, one file per texture ID.
_Avoid_: texture cache, texture pack

## Faces

**Face**:
One triangular surface element of a model. Its stored data can include a face colour, texture reference, alpha, render priority and face skin.
_Avoid_: triangle, polygon, tri

**Face colour**:
A 16-bit packed colour value with 6 bits of hue, 3 bits of saturation and 7 bits of lightness, used to colour untextured faces.
_Avoid_: HSL16, RGB, colour value

**Texture ID**:
The number of a texture in the cache. The old model encoding uses a textured face's colour slot for this ID; newer encodings can store the colour and texture ID separately.
_Avoid_: texture index, material ID

**Flat shading**:
A per-face flag that lights the face with one colour instead of blending across its vertices.
_Avoid_: face render type, face type, draw type

**Face alpha**:
A byte of transparency per face, where 0 is opaque and 255 is fully transparent.
_Avoid_: opacity, transparency

**Fade group**:
The faces of a player that every baked clip fades alike on every frame, starting from the same face alpha, so one opacity serves them all.
_Avoid_: fade label, alpha group

**Render priority**:
A number from 0 to 11 per face that decides which faces of one model are drawn over which, : the client sorts faces into depth buckets, then draws priorities 0 to 9 in ascending order, so a higher priority paints over a lower one whatever their depth (see docs/research/render-priority.md). A model either carries a priority per face or one priority for all faces.
_Avoid_: RSPRI, priority layer, draw order, z-index

**Stacked faces**:
Two or more textured faces whose corners are at the same three positions, in any order and whichever vertices they name. A material with any such face draws blended and culled.
_Avoid_: overlapping faces, coplanar faces, z-fighting

## Texturing

**Texture triangle**:
Three vertices of the model, named P, M and N, that define the plane and orientation a texture is projected from onto every face that references it.
_Avoid_: PMN triangle, texture coordinates, UV triangle

**PMN**:
The point P (texture origin), M (end of the U axis) and N (end of the V axis) of a texture triangle.
_Avoid_: UV, texture space

**Texture render type**:
The kind of texture record stored in a model: type 0 names a texture triangle, while other types carry additional data. Its effect on the rendered mapping depends on the client; the numeric value alone does not establish a projection shape.
_Avoid_: texture mode, mapping type

**Own-face mapping**:
A texture mapping whose reference points are the face's own three corners, rather than a separately retained texture triangle.
_Avoid_: cylindrical fallback, cube fallback

## Animation labels

**Spot effect**:
A game effect definition that selects a model, an optional animation sequence and display settings, such as scale and recoloring.
_Avoid_: animation file, keyframes, item animation

**Animation sequence**:
An ordered set of game animation frames and their durations, with playback settings.
_Avoid_: spot effect, model animation

**Stance clips**:
The seven animation sequences a player's appearance block names: stand, turn, walk, walk back, walk left, walk right and run. The game server picks them for the worn weapon; the revision 149 client has no defaults.
_Avoid_: render animations, base animation set, BAS

**Weapon clips**:
A weapon's stance clips plus the attack clip for each of its combat style buttons and its block clip, as an open table gives them (`data/weapon_clips.json`).
_Avoid_: stance set, which leaves out the attack and block clips

**Play as**:
How a bake advances a clip's frames. A Pose starts at frame 0 and ignores the loop offset. An Action plays once, or loops by its loop offset. Picking a clip by name sets Pose for a stance clip in the weapon clips table and Action for any other clip. The Stance and Attack buttons set it for their own clips, and the animator can change it after.
_Avoid_: play mode, loop mode

**Frame map**:
In legacy game animation, a set of transform types and the skin labels each transform affects.
_Avoid_: bone hierarchy, armature

**Vertex skin**:
An integer label per vertex naming the body part or animation group that vertex belongs to. Animation frames move, rotate and scale all vertices sharing a label together.
_Avoid_: VSKIN, weight, vertex group, bone

**Face skin**:
An integer label per face naming the group whose alpha an animation can change together. In the 2018 client, animation transform type 5 changes the alpha of the listed face skins (`Model.java` line 869), and no transform that changes colour was found ([Model format references](docs/research/model-formats.md)).
_Avoid_: TSKIN, RSTSKIN, triangle skin

**Body-part label**:
A conventional vertex skin value for a part of the player body, such as 8 for torso or 28 for gloves, which worn equipment must match to animate with the player.
_Avoid_: preset weight, weight value

**Joint**:
One of the 15 bones of a player's rig that the user animates, such as `spine` or `hand`. Each comes from a rotate transform of frame map 0 with its pivot (`data/player_joints.json`), and moves the vertices of the vertex skin labels under it rigidly.
_Avoid_: bone (the rig also has hidden label bones), control

**Your motion**:
The NLA track of a player's rig that holds the user's own keys on the joints, layered over the baked clips on the "RS clips" track.
_Avoid_: user track, custom animation

**Contact sheet**:
One image of one player on several frames of a motion, with one column per frame and one row per view. Each row has one camera for all its frames, so a change between two cells is a pose change.
_Avoid_: storyboard, sprite sheet, thumbnail grid

**Export preset**:
A named mapping, per kind of equipment, from body-part labels to the render priorities and face skins that faces carrying those labels receive on export.
_Avoid_: model type, template

**Identity kit**:
A body part model set from the game cache (config group 3) that a player wears as skin, hair, torso, arms, hands, legs or feet. A kit has a body part category, one or more models and optional recolours. Equipment stores a kit as `kit id + 256`.
_Avoid_: body kit, appearance model

**Equipment slot**:
One of the twelve entries of a player's equipment array. A value of 0 is empty, 256 to 511 is an identity kit, and 512 or more is a worn item.
_Avoid_: kit slot

**Body palette**:
The client's tables mapping a player's five colour choices to the colours that replace each kit colour. Revision 149 has its own tables.
_Avoid_: skin colours, preset

**Worn model**:
The model files an item shows on a player's body, up to three per body type, separate from its inventory model. Several items can share one worn model.
_Avoid_: equip model, wear model

**Recolour**:
A pair of face colours, one to find and one to show in its place, that an item or identity kit applies to its models. The model file keeps the colour that is found.
_Avoid_: colour swap, tint
