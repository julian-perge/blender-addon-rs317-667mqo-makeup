# Materials with stacked textured faces blend and cull back faces

Textured faces stacked on the same corners showed black in Material Preview with the imported `DITHERED` render method. On tree 5452 all 40 faces of texture 17 sit on faces of texture 8, and the canopy went black, though each layer looks right on its own. Blender issue 136453, closed as a known issue, says Dithered draws only the last of such coplanar triangles correctly, which matches the black (evidence for the limit; that it is the whole cause is a guess). [The fork comparison](../research/fork-or-own-copy.md) rendered the options and ruled out `BLENDED` on all textured materials, and culling alone.

The owner chose on 2026-11-05: import gives a material `BLENDED` and backface culling when any of its faces has the same corner positions as another textured face (`mesh._stacked_textured_faces`, `face_materials.show_stacked`), and every other material keeps its render method. The Aether tint and reset keep such a material blended, through the material property `rs_stacked`. 77 models of the 317 cache get the state, and trees 5452, 5457 and 1650 show green canopies with no black.

Accepted gaps:

- The rule is per material, so faces of such a material that are not stacked also blend and cull (1,637 of the 3,166 faces in those materials, on 53 of the 77 models).
- The state never clears, so a material stays blended and culled after its stack is edited away.
- Detection runs only at import, so stacks made later with the texture tool or the mirror, materials from Upgrade RS Materials and 667 imports were not covered. The 667 importer was removed on 2026-11-11 ([ADR 0017](0017-read-caches-directly-without-317-and-667-code.md)).
- `BLENDED` layer order was not compared with the client's priorities, and tree 1571 shows wrong layering where it showed black before.
- Five models with two textures on one face (2007, 2008, 2021, 3449 and 5775) gained nothing at the angle the fork comparison rendered.
- Culling hides a stacked face from behind, which matches the client's winding test on the path read (`ZKARKDQW.java` line 4455).
