# 01: Import an item's worn model with its recolours

**What to build:** a modeller imports an item's worn model from the cache dump and sees it in the item's in-game colours, while export still writes the model as the game stores it. The new import operator, given an item id and a body (Male by default, or Female), brings in each model file of that body's worn model as its own object, named by its model id, at its stored position. Faces whose stored colour an item recolour finds show the replacement colour, at the Brightness setting; every face keeps the model file's own colour, texture and alpha as its stored game values. The imported objects are selected and the last is active. See the [spec](../spec.md) and issue 07's decisions 1 to 4, 6, 8 and 10.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the import operator run headless with the item and body set, against the test dump fixtures.
- [ ] One object per model file of the chosen body's worn model, named by model id, at its stored position, with no body offset and no joining.
- [ ] Faces a recolour finds show the recolour's replacement at the Brightness setting; other faces show their stored colour.
- [ ] Every face's stored game values equal the decoded model file's own.
- [ ] Exporting an imported object writes the model file's own colours.
- [ ] The Female body imports the female worn model.
- [ ] An item that lists retextures, an item with no worn model for the body, a missing dump folder or item data, and a model file missing from the dump are each refused with a message naming the cause, and add nothing to the file.
- [ ] The imported objects are selected and the last one is active.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
