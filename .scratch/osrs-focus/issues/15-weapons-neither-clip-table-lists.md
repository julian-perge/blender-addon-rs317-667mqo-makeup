# Weapons neither clip table lists get the unarmed clips

Status: wontfix

185 weapon-slot items are in neither Alter's table nor the plugin's, so they get the unarmed clips with a note ([ADR 0014](../../../docs/adr/0014-weapon-clips-come-from-alter-then-the-plugin.md)). Among them are weapons that RSMod gives a set: the eleven Crystal halberds, Boxing gloves 7673 and Crate with zanik ([research](../../../docs/research/weapon-stance-sets.md)). Also open: which set each weapon had in July 2017, since both tables are newer, and which table is right for the 64 items where they disagree. Recorded 2026-11-09 ([plan 13](../plans/13-weapon-stances.md)).

## Decisions

The user chose on 2026-11-10, in a design interview, to keep ADR 0014 as it is:

1. The 185 weapons neither table lists keep the unarmed clips and the panel's note. RSMod v1, which gives 13 of them a set (the eleven Crystal halberds the staff set, Boxing gloves their own stand and walk), is not added as a third source: it is the least reliable table read, with known errors elsewhere.
2. Alter's table keeps winning on the 64 items where the two tables disagree (57 differ only in the block clip, 7 in the stance clips), and `data/weapon_clips.json` keeps the plugin's set for each of them.
3. The sets stay unverified for July 2017, as ADR 0014 and the research note say, since no 2017 source holds up.

(Fact checked for this: every clip id in `data/weapon_clips.json` exists in snapshot 430's sequences.)

## Comments

- 2026-11-10, triage with the user: needs-info. Which source wins (RSMod's sets, and the 64 items where the two tables disagree) is the owner's call.
- 2026-11-10, design interview with the user: wontfix, decisions 1 to 3. ADR 0014 stands.
