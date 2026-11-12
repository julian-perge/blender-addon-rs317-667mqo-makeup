# Weapon clips come from Alter's table, and the plugin fills only the weapons Alter lacks

The revision 149 client reads a player's stand, walk and run clips from the appearance block the server sends, and neither snapshot 430 nor a 2026 cache holds a weapon to clip table ([research](../research/weapon-stance-sets.md), sections 1 and 3). On 2026-11-09 the owner chose:

- Under Bake clip, a Stance row (Stand, Walk, Run) and an Attack row (1, 2, 3, 4, Block) choose the clip the tables give the active player's weapon. A stance button sets Play As to Pose, an attack button to Action.
- Alter's table (`9ddbbbe`, 2024) is the table: an item it lists takes its set, gaps included. The Weapon Animation Replacer plugin (`504f6bd`, 2026) fills only the weapons Alter does not list. A weapon neither lists gets the unarmed clips, and the panel names it in a note.
- Where Alter gives no block clip, the Block button stays greyed out, also for the 12 weapons where the plugin gives one, all seven scimitars among them. The plugin's block data has a clear error elsewhere: its Tzhaar-ket-om block is the whip's run clip 1661.
- The 14 weapons only the plugin lists keep attack buttons 1 to 4 greyed out, since no source says which button each of the plugin's attack types belongs to.

`scripts/generate-weapon-clips.py` writes `data/weapon_clips.json` from both tables, which are BSD 2-Clause, with their notices and file hashes. The attack buttons are numbered because Alter's field names do not name the weapons' styles; reading its four fields as the style buttons in order fits the whip and the 2h sword, an inference not checked against the client. On 2026-11-10 the owner kept this as it is (issue 15 (`git show 2a78edd:.scratch/osrs-focus/issues/15-weapons-neither-clip-table-lists.md`)): no third table for the 185 weapons neither lists, Alter winning on the 64 items where the tables disagree, and the sets unverified for July 2017.
