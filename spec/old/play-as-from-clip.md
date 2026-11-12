# Picking a clip sets Play As

Status: done (picking a clip sets Play As; see tasks/old/play-as-from-clip/).

From issue 21 (`git show 2a78edd:.scratch/osrs-focus/issues/21-play-as-defaults-to-pose.md`), whose Decisions block (decisions 1 and 2, chosen by the user on 2026-11-10) this spec follows, and [ADR 0014](../../docs/adr/0014-weapon-clips-come-from-alter-then-the-plugin.md).

## Problem Statement

An animator who picks a clip by name in Player Appearance's clip search keeps whatever Play As was set before. Play As defaults to Pose, so picking an emote, a skilling clip or an attack by name bakes it as a looping pose that ignores its loop offset, and a clip that holds items does not show them, unless the animator remembers to switch to Action. Neither the cache nor a clip says how the server plays a sequence, but the weapon clip table lists every stance clip, which is what Pose is for.

## Solution

Picking a clip by name sets Play As from the weapon clip table: Pose when the clip is a stance clip (one of the unarmed set or any weapon's stand, turn, walk or run clips), Action for every other clip. The animator can still change Play As after picking. Before any pick, Play As stays Pose, and the Stance and Attack buttons keep setting it as they do.

## User Stories

1. As an animator, I want picking a stance clip such as stand 808 to set Play As to Pose, so that it loops as the game shows a stance.
2. As an animator, I want picking a weapon's walk or run to set Pose, so that weapon stances loop too.
3. As an animator, I want picking an emote to set Action, so that it plays once or loops by its own loop offset.
4. As an animator, I want picking a skilling clip that holds items, such as woodcutting 1365, to set Action, so that the held items show.
5. As an animator, I want to change Play As after picking, so that I can bake a clip the other way on purpose.
6. As an animator, I want Play As to stay Pose before I pick anything, so that a new scene starts as today.
7. As an animator, I want the Stance and Attack buttons to keep setting Play As as they do, so that those rows behave as before.
8. As an animator, I want the held-items hint to still show when I switch a held-item clip back to Pose, so that I know the items will not show.

## Implementation Decisions

- The clip picker sets the panel's Play As after it sets the picked clip: Pose when the clip's sequence id is in any stance list of the weapon clip table (the unarmed set or any set's stance clips), Action otherwise.
- The stance clips are read from the weapon clip table the Stance and Attack buttons already use, so the rule follows the table if it is regenerated.
- Nothing else sets Play As; the user's later change is kept until the next pick.

## Testing Decisions

- One seam: the clip picker operator, run headless with the clip set, as the existing clip-picker test runs it; the test reads the panel's Play As afterwards.
- Expected values come from the weapon clip table (which clips are stance clips) and the user's decisions in issue 21; test comments cite them.
- Cases: stand 808 gives Pose; a weapon set's walk from the table gives Pose; an emote gives Action; held-item clip 1365 gives Action; changing Play As after a pick is kept.
- Prior art: the clip picker and weapon clip button tests in the clip tests.

## Out of Scope

- Changing Play As's default before any pick.
- Reading a play mode from the cache or the clip.
- The Stance and Attack buttons.

## Further Notes

- The held-items hint under Play As already warns when a clip that holds items is set to Pose.
