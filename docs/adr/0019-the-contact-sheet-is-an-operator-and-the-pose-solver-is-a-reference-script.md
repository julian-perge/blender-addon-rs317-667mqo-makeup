# The contact sheet is an operator, and the pose solver is a reference script

On 2026-11-12 the sword flourish test of issue 12 passed on the first review ([ADR 0018](0018-a-claude-made-motion-is-tested-before-toolkit-code.md)). The owner then settled what the pass turns into toolkit code and what it does not. The spec is `spec/12-contact-sheet-and-runbook.md`.

- Only the contact sheet becomes an operator, `rsps.contact_sheet`. The review video stays a script in `docs/research/sword-flourish-test/feedback.py`. The alternative was to ship both as operators. The owner rejected it: Claude needs the sheet after every round of keys, and the video only once for each review.
- The operator has no panel button. Claude calls it through the Blender MCP, and a user finds it in the operator search. The alternative was a button in the player panel with fields for the frames and the views. [ADR 0020](0020-the-contact-sheet-operator-is-hidden-from-the-operator-search.md) replaces the part about the operator search.
- The operator writes a PNG at a path that the caller gives and leaves nothing in the .blend. The alternative was to keep the sheet as an image datablock also.
- The caller gives the frames as an explicit list. The alternative was to take the first frame of each held pose from the keys on the Your motion track by default. That needs a rule for what counts as the start of a pose, and the test did not need one.
- The defaults are the layout that the owner accepted in the test: the front view and the right view, and cells of 320 x 480.
- The pose solver is not toolkit code. A cleaned copy of the test's pose script goes in `docs/research/sword-flourish-test/flourish.py`, with the solver, the builder of the action and its strip, and the scene checks. Claude copies it and changes the pose list. The alternatives were runbook text only, which makes Claude write the solver in each session, and a tested helper under `src/`, which fixes the form of a pose description before the Design stage of step 2.
- The runbook is `docs/hand-made-motion.md`, a user doc that a user gives to Claude. The alternatives were `docs/agents/`, which holds the docs for work on the toolkit, and a file inside the extension.
- The automated tests of the operator render with Workbench. The first test run also renders one sheet with EEVEE in headless Blender, and the pull request records the time and the result of both, because the owner wants the comparison.
- The automated tests run on the installed Blender only. The test of issue 12 ran on Blender 5.3.0, and Blender 5.2 is not checked.
