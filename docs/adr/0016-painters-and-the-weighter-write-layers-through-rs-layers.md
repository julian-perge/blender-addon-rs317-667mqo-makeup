# The painters and the weighter write the Blender layers only through rs_layers

In the architecture review of 2026-11-05 the owner decided candidates 2 and 6:

- `priorities.py` and `tskins.py` merged into one painter module, `blender/painter.py`, used for `RSPRI` and `RSTSKIN`, which reads and writes only through `rs_layers`, rounding instead of truncating.
- The per-value display layers (`RSPRI_<n>`, `RSTSKIN_<n>`) are dropped in favour of the GPU overlay, and old ones in .blend files are ignored. Writing a layer again overwrites it instead of creating `RSPRI.001`.
- The weighter assigns integer labels through `rs_layers`. The VSKIN1/2/3 split and the `vskin_layer` selector are gone, and Assign Custom takes a label from 0 to 255.
- `presets.py` holds one body-part label table, with each label, its button name and its left or right mirror partner. The weighter builds its buttons from it, with the original names and order, and mirroring uses its label pairs.

A layer the painter creates starts every face at the value export uses without the layer (priority 1, face skin 0), where Blender would fill it with 255.
