# Worn items that hide the hands or the shield still show them

Status: resolved
Type: task

## Report (2026-11-07)

The user found slight clipping in the live Blender:
- Boxing gloves: a skin-coloured patch shows through the back of the glove, and a grey cuff pokes out at the wrist.
- Plague jacket (284): grey and black cuffs show at both wrists below the sleeves.

## Evidence

`data/item_wear.json` (cache 2757) says these items hide the hands slot (9), which the panel cannot empty yet:
- 284 Plague jacket and 6657 Camo top hide the arms and the hands.
- Four boxing glove ids hide the shield and the hands.
- Two-handed weapons hide the shield (`wearPos2` or `wearPos3` is 5).

Guess, not checked: the patches are the hands kit (slot 9) drawn under the item, as the arms kit was under platebodies before Covers arms.

## Task

- Add a "Covers hands" toggle, driven from the wear data like Covers arms, for any worn item that hides slot 9 (torso and weapon items). Show it under the item line that hides it.
- Picking an item that hides the shield (slot 5) takes off the worn shield, or decide with the user whether a toggle fits better, since slot 5 holds items, not kits.
- Check both cases again in the live Blender against the screenshots.

## Comments

- 2026-11-07, agent: added Covers hands under the Torso item and under the Weapon item, and Covers shield under the Weapon item, set from `data/item_wear.json` when an item is picked and locked like the others. In that data, 284 Plague jacket and 6657 Camo top hide the arms and hands, and the boxing gloves 7671, 7673, 11705 and 11706 hide the shield and hands. A covered shield is kept and comes back on untick or Take Off. Waiting for the user's look in Blender.
- 2026-11-07, user: checked in Blender with the Plague jacket and boxing gloves 7671; the clipping is gone.
