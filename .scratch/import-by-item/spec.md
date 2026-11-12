# Import worn models by item

Status: done

From [issue 07](../osrs-focus/issues/07-imported-worn-items-show-stored-colours.md), whose Decisions block (decisions 1 to 11, chosen by the user on 2026-11-10) this spec follows.

## Problem Statement

A modeller who imports an Old School worn model with File > Import > RS Model sees the model file's stored colours, such as grey and tan on a rune armour set, not the colours the item shows in game. The game shows an item's worn model with the item's recolours applied, but a model file alone cannot say which item it belongs to: 468 worn models are used by more than one item, and for 274 of them those items recolour the model differently. So the modeller cannot see the piece they are editing as players see it, while export must keep writing the model as the game stores it, since every item that shares the model recolours it its own way.

## Solution

A new import, File > Import > RS Item (from dump), opens a search of the items in the cache dump folder (the one Player Appearance uses) that have a worn model for the chosen body. Picking an item imports each model file of its worn model as its own object, named by its model id, showing the item's recolours. Each face still stores the model file's own colour as its game value, so export writes the model back as the game stores it. The importer panel tells the modeller, for such an object, that it is shown with the item's recolours and that export writes the model's own colours. File > Import > RS Model stays a plain model-file import.

## User Stories

1. As a modeller, I want to import a worn item by searching its name, so that I do not have to know which model files it uses.
2. As a modeller, I want to search by item id too, so that I can pick one of several items with the same name.
3. As a modeller, I want the search to list only items with a worn model for the body I chose, so that every entry I can pick imports something.
4. As a modeller, I want to choose Male or Female before searching, so that I get the worn model for the body I am editing.
5. As a modeller, I want Male to be the default body, so that the common case needs no extra step.
6. As a modeller, I want the imported item to show its in-game colours, so that I see the piece as players do.
7. As a modeller, I want the colours shown at the add-on's Brightness setting, so that an item import looks like my other imports.
8. As a modeller, I want each model file of the item's worn model as its own object, so that each one exports back to its own file.
9. As a modeller, I want each object named by its model id, so that export writes it under the same file name.
10. As a modeller, I want the objects at their stored positions, so that what I export is what the game loads.
11. As a modeller, I want the pieces of a male worn model to line up as in game, since they are stored to fit together.
12. As a modeller, I want export of an item import to write the model file's own colours, so that every other item that shares the model keeps its own colours in game.
13. As a modeller, I want to export an item import I did not edit and get the model's original colours, so that a round trip does not recolour the model.
14. As a modeller, I want faces I add or repaint to export with the game values I give them, as for any import, so that item imports are edited like other imports.
15. As a modeller, I want an item import's materials kept apart from those of a plain import of the same model, so that importing one never changes how the other looks.
16. As a modeller, I want the importer panel to tell me an object is shown with an item's recolours and name the item, so that I do not mistake the shown colours for the model's own.
17. As a modeller, I want the panel to say export writes the model's own colours, so that I know what the exported file will hold.
18. As a modeller, I want the item and body stored on each object, so that the panel and later tools know where its colours came from.
19. As a modeller, I want a clear message when the cache dump folder is not set or lacks the item data, so that I know what to fix.
20. As a modeller, I want a clear message when the dump lacks one of the item's model files, so that I know which file is missing.
21. As a modeller, I want an item that lists retextures refused with a message, since no worn item in snapshot 430 has them and how they show cannot be checked.
22. As a modeller, I want a failed item import to add nothing to the file, so that a refusal leaves no half-made objects.
23. As a modeller, I want the imported objects selected and the last one active, as File > Import > RS Model leaves them, so that I can start editing at once.
24. As a modeller, I want File > Import > RS Model to keep importing plain model files unchanged, so that my existing workflow is not affected.

## Implementation Decisions

- A new import operator, listed under File > Import as "RS Item (from dump)". It has a body choice (Male or Female, Male by default) and an item property filled from a search popup by name or id, in the style of Player Appearance's worn item search. It reads the cache dump folder add-on preference and the dump's item definitions and model files, through the same data loading that Player Appearance uses (the cache profile and the worn item records, which already carry each item's male and female model ids, offsets, recolours and retextures).
- The search lists only items whose worn model for the chosen body has at least one model file.
- Each model file of the chosen body's worn model is decoded as the plain import decodes it, with the Old School revision 149 profile, and becomes its own object named by its model id, at its stored position. The body's offset is not applied, and the pieces are not joined.
- Faces keep the model file's own colour, texture and alpha as their stored game values, the values export writes (ADR 0006). Only the shown colour of a face whose stored colour an item recolour finds changes to the recolour's replacement, at the Brightness setting. Recolours apply in the item definition's order, as the game's assembly applies them.
- Materials are made per imported object, keyed by the stored game values, as the plain import already does, so an item import and a plain import of the same model never share a material, and a material's stored values stay the model file's own while its shown colour is the recoloured one.
- Each object stores the item id, the item name and the body. The importer panel shows, for the active object when these are set, that it is shown with that item's recolours and that export writes the model's own colours. The note's text comes from a function that takes the object, so it can be tested without drawing the panel.
- An item that lists retextures is refused with a message naming the item. A missing dump folder, missing item data, or a model file missing from the dump is refused with a message naming what is missing. A refused or failed import removes any objects and meshes it made.
- The new import selects the imported objects and makes the last one active, like the plain import.
- The recolour arithmetic is the existing one used for worn items and kits. No new colour conversion is introduced.

## Testing Decisions

- A good test drives the feature where a modeller does, through the import operator, and checks what ends up in the file and what export writes, never the internals.
- Seam 1, the new import operator, run headless with the item and body set, against the test dump fixtures (the appearance fixtures and the held-item clip fixtures already provide item definitions with recolours and their model files). It checks:
  - one object per model file of the worn model, named by model id;
  - the shown colours equal the item definition's recolour replacements for the faces whose stored colour they find, at the Brightness setting, and other faces show their stored colour;
  - the stored game values equal the decoded model file's own;
  - exporting the imported object writes the model file's own colours;
  - an item with retextures, an item with no worn model for the body, and a missing model file are refused and add nothing;
  - the female choice imports the female worn model.
- Seam 2, the function that gives the importer panel's note for an object: the note names the item and says export writes the model's own colours for an item import, and there is no note for a plain import.
- Expected values come from outside the code under test: the dump's item definitions and model files (cache data) and the user's decisions in issue 07. Test comments cite issue 07's decision numbers, as other tests cite their tickets.
- Prior art: the plain import tests (several files, selection, skipped files), the export tests that export an imported object and decode the written file, and the Player Appearance worn item tests that assemble recoloured worn models from the same dump fixtures.

## Out of Scope

- Changing File > Import > RS Model.
- Joining an item's worn model files into one object, or applying the female offset.
- Showing retextures (refused while no snapshot 430 worn item has one).
- Inventory models, head models and drop models.
- Writing recoloured colours into exported model files.
- Picking an item for an object that was imported as a plain model file.
- 317 and 667 items (ADR 0003: Old School caches come first).

## Further Notes

- In the design interview the agent said imported materials are shared by game values. That was wrong: each import makes its own materials per object. Decision 8 (a recoloured face gets its own material) therefore holds with the existing material building, as long as the shown colour is set from the recolour and the stored values from the file.
- Whether the shown colours match the game is checked through the cache's item definitions, not against a client rendering of a worn item on its own. Player Appearance's worn item colours, which use the same recolour arithmetic, are checked against the unchanged revision 149 client (`tests/fixtures/appearance/reference.json`).
