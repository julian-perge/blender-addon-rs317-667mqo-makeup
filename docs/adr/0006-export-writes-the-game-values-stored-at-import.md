# What Blender shows is separate from the game values export writes

Import stores each material's game values (its face colour or texture ID, and its alpha) as `rs_` properties, and export reads only those. The owner decided on 2026-11-05 that recolouring a material in Blender therefore does not change the export, and that a material the add-on did not create makes export fail with a message pointing to Upgrade RS Materials. The owner does not plan to recolour imports; converting the visible colour to the nearest palette colour is the fix if that changes.

What Blender shows follows the owner's other choices:

- Imports show face colours at the add-on preference Brightness, one of the client's settings 0.9 to 0.6, default 0.8, the 317 client's starting value (`client.java` line 15624; chosen 2026-11-04, changed 2026-11-05 after item icons rendered at 0.6 matched imports at 0.6 and not at 0.9). It changes only how new imports look: existing materials keep their colour, and textures show their stored palette at every setting.
- A textured face whose PNG is missing shows flat magenta, so missing textures stand out (2026-11-05).
- Upgrade RS Materials, a one-off operator, writes the `rs_` properties from the names older add-on versions gave materials (`RS_Color_<colour>`, `Texture_<id>`, `PMN_<id>`), and export stays strict. Both original importers switched every face of a model with face alphas to blending except faces at 255, so an importer material without an alpha reads as 255 (a face the client does not draw) on an object where any material has one, and as 0 otherwise (the owner's choice, 2026-11-05).
- The Aether panel is preview-only and says so: its copies keep the imported game values, so export ignores its colours.
