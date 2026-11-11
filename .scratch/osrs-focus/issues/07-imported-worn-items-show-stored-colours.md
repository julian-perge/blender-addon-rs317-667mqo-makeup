# Imported worn items show their stored colours, not the item's recolours

Status: needs-info

Old School worn models imported with File > Import > RS Model show the models' stored colours, grey and tan on a rune armour set, because the importer does not apply the `colorFind` and `colorReplace` that `ItemDefinitions.json` holds for such items (evidence: in `src/`, only `formats/appearance.py` and the animation modules read recolours). Seen 2026-11-05 on a rune full helm, platebody and platelegs, gloves, boots, cape, amulet of glory, kiteshield and scimitar; the recolour lists were read for the platebody and cape. That applying them gives the real colours is unchecked.

## Decisions

The user chose on 2026-11-10, in a design interview:

1. A new import by item brings in an item's worn model from the cache dump with that item's recolours. File > Import > RS Model stays a plain model-file import. (Facts: 468 worn models are used by more than one item, and for 274 of them those items recolour the model differently, so a model file alone cannot say which recolours apply.)
2. Blender shows the item's recolours, but each face keeps the model file's own colour as its game value, so export writes the model as the game stores it and every item sharing it keeps its own colours (as ADR 0006 separates what Blender shows from what export writes).
3. The import asks for the body, Male or Female, with Male the default.
4. Each model file of the worn model is its own object at its stored position, so each exports back to its own file. The female body's offset is not applied.
5. It is a File > Import entry, RS Item (from dump), that opens an item search by name or id, using the cache dump folder that Player Appearance uses.
6. Each object is named by its model id, so it exports back to that file name. The item and body are stored on the object.
7. The search lists only items with a worn model for the chosen body.
8. A recoloured face gets its own material, holding both its stored game values and the colour it shows, so a plain import and a recoloured import of the same model never share a material.
9. The importer panel shows, for such an object, that it is shown with the item's recolours and that export writes the model's own colours.
10. An item that lists retextures is refused with a message. No worn item in snapshot 430 has retextures (2093 have recolours), so how they show cannot be checked.
11. The user writes a spec for this with /to-spec before implementation.

## Comments

- 2026-11-10, triage with the user: needs-info. A model file alone does not say which item's recolours apply, so how the importer picks the item is the owner's call.
- 2026-11-10, design interview with the user: decisions 1 to 11 above. Next step: the user runs /to-spec. GLOSSARY.md gained Worn model and Recolour.
- 2026-11-10, agent: the spec is [.scratch/import-by-item/spec.md](../../import-by-item/spec.md) (ready-for-agent). The user agreed two test seams: the new import operator, and the function that gives the importer panel's note.
