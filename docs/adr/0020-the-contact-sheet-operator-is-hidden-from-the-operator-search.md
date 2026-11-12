# The contact sheet operator is hidden from the operator search

[ADR 0019](0019-the-contact-sheet-is-an-operator-and-the-pose-solver-is-a-reference-script.md) said that a user finds `rsps.contact_sheet` in the operator search. The commit review of issue 19 found that this path fails: the operator has no `invoke`, so a call from the search runs with empty `frames` and `filepath` and reports "The frames are empty" (issue 24). On 2026-11-12 the owner settled it. This record replaces that one sentence of ADR 0019. The rest of ADR 0019 stands.

- Only Claude calls the operator, with a Python call through the Blender MCP. The owner does not make a contact sheet by hand, and no other user is expected to.
- The operator carries the `INTERNAL` option, so it is not in the operator search. A Python call still works, and its arguments do not change. The alternatives were to keep the operator in the search with the report it gives today, or with a clearer report. The owner rejected both: a search entry that can only fail has no use.
- The operator gets no `invoke` and no dialog. The alternative was a file browser with the properties `frames`, `views`, `cell_width` and `cell_height`. Nobody would use it.
