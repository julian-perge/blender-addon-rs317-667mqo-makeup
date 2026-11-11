# 03: Importer panel note for item imports

**What to build:** a modeller selecting an object that came from an import by item sees, in the Model Exporter and Model Importer panel, that it is shown with that item's recolours (naming the item and body) and that export writes the model's own colours. Each imported object stores its item id, item name and body. A plain RS Model import shows no such note. See the [spec](../spec.md) and issue 07's decisions 6 and 9.

**Blocked by:** 01 (Import an item's worn model with its recolours).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the function that gives the note's text for an object.
- [ ] Objects from an import by item store the item id, item name and body.
- [ ] The note names the item and body and says export writes the model's own colours.
- [ ] A plain import gets no note.
- [ ] The panel shows the note for the active object.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
