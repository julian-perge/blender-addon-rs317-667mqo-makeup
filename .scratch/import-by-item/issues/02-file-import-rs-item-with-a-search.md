# 02: File > Import > RS Item (from dump) with a search

**What to build:** a modeller finds the item to import by typing part of its name or its id, from File > Import > RS Item (from dump), with the body choice beside it. The search lists only items with a worn model for the chosen body, and picking one runs the import from ticket 01. See the [spec](../spec.md) and issue 07's decisions 3, 5 and 7.

**Blocked by:** 01 (Import an item's worn model with its recolours).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first.
- [ ] File > Import lists "RS Item (from dump)".
- [ ] The search matches item names and ids, and lists only items with a worn model for the chosen body.
- [ ] Picking an item imports it as ticket 01 does.
- [ ] The user checks the entry and the search in Blender.
- [ ] prek and the Blender suite pass; the work gets the two-axis review before its commit.
