# Cite the revision 149 client for the six OSRS-149 codec rules

Status: ready-for-agent

From [issue 17](../osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md), whose Decisions block (decisions 1 to 3, chosen by the user on 2026-11-10) this spec follows.

## Problem Statement

A modeller who builds or edits an Old School revision 149 model in the new model format (`FF FF`) and exports it relies on two writing rules nobody has checked against the client: a model whose faces share one render priority stores it once in the footer (0 when there are no faces), and the render-type and face alpha sections are left out when all their values are 0. If the client reads such a file differently, the exported model looks wrong or fails to load in game. Four more rules refuse unusual input, a texture index above 254, an opaque tail whose first byte is nonzero and that holds fewer than 11 bytes, texture kinds above 3, and footer flags other than 0 or 1, also without a client citation, so the add-on may refuse files the client reads or accept rules the client does not follow. The model formats note and the code mark all six "unverified", and the coding standards ask for a client citation or the owner's decision.

## Solution

Read the revision 149 client's new-format model decoder, from the client jar with the decompiler already on this machine, and settle each rule against it. Each rule the client confirms gets its citation (class, method and line or bytecode offset) in the model formats note, in the code comment that marks it, and in its test. Each rule the client contradicts goes back to the user before any code or test changes. The modeller then knows the export and the refusals follow the client.

## User Stories

1. As a modeller, I want the shared priority rule checked against the client, so that a model I build with one priority loads with that priority in game.
2. As a modeller, I want the rule that leaves out all-zero render-type and alpha sections checked, so that my exported model reads the same in the client as in the add-on.
3. As a modeller, I want the refusal of texture indices above 254 checked, so that I know whether 255 means something to the client.
4. As a modeller, I want the opaque tail refusal checked, so that a cache model with an unusual tail is not refused wrongly.
5. As a modeller, I want the refusal of texture kinds above 3 checked, so that no real kind is refused.
6. As a modeller, I want the refusal of footer flags other than 0 or 1 checked, so that no real flag value is refused.
7. As the owner, I want each confirmed rule's citation in the model formats note, so that the note no longer says "unverified" for it.
8. As the owner, I want the code comment that marks each rule to cite the client line, so that a reader of the code sees the source.
9. As the owner, I want each confirmed rule covered by a test whose comment cites the client, so that the expected value has an outside source.
10. As the owner, I want any rule the client contradicts brought to me before anything changes, so that I decide what the add-on does.
11. As the owner, I want the evidence (the decompiled method and the lines read) recorded where the earlier client findings are, so that it can be checked again.
12. As the owner, I want issue 17 closed with the results, so that the open-questions list shrinks.

## Implementation Decisions

- The work reads the new-format decoder of the unchanged revision 149 client jar named in the reference-source findings, decompiled with the decompiler already on this machine, as the earlier findings for the model conversion were read. It uses the research skill.
- For each of the six rules it records, in the reference-source findings, the method and the line or bytecode offset that shows how the client reads the field, and whether that matches the add-on's rule.
- A confirmed rule's "unverified" marks are replaced with the citation in the model formats note's "Old School revision 149 in this add-on" section and in the codec's code comments.
- A contradicted rule is reported to the user with the client's behaviour and options; nothing changes for it until the user decides.
- No change to the codec's behaviour is part of this spec.

## Testing Decisions

- One seam: the codec's public decode and encode, in the existing OSRS-149 codec unit tests, which already cover the refusals (malformed footers, invalid source fields) and the computed footer layout of hand-built models.
- A good test checks what decode accepts or refuses and what encode writes, never the codec's internals.
- For each confirmed rule, the test that covers it gets a comment citing the client's method and line as its expected-value source; a confirmed rule without a test gets one.
- Expected values come from the client's decoder (CODING_STANDARDS: "a line of a game client's code, named in a comment as file and line").
- Prior art: the OSRS-149 codec unit tests and the model formats note's existing client citations.

## Out of Scope

- Changing the codec for a rule the client contradicts (that waits for the user).
- The render-level Gate 0 comparison of plan 02.
- Other "unverified" claims in the model formats note, such as render types 1 and 3 being flat.
- 667 and 317 formats.

## Further Notes

- The client jar and the decompiler sit in the owner's local scratch folders, named in the reference-source findings; the spec does not repeat local paths, since the repo is public.
