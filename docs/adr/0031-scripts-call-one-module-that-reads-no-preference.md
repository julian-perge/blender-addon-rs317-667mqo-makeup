# Scripts call one module that reads no preference and no panel state

A script of another repo builds scenes with the add-on in headless Blender. Until [issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170) it had to enable the add-on, set the Cache folder and Brightness preferences, fill `scene.rs_appearance` in a fixed order and call operators. Each of those steps is state that the script does not own. The owner's rule in the issue: whatever is generic to scripted use is fixed in the add-on.

## Decision

- **One module is the public surface for scripts: `rsps_toolkit.blender.scripting`.** Its functions are `import_region`, `import_regions`, `create_player`, `import_item`, `attach_to_joint`, `bake_clip` and `key_travel` ([spec 170](../../spec/170-scripted-use.md)).
- **Every input is an argument.** No function of the module reads the add-on preferences or a scene property of the panel, and none registers a class. The cache folder is a `Path`. The brightness is a float with no default, because the preference has one and a script must not get it by accident.
- **The module works with the add-on not enabled.** A script puts `src/` on `sys.path` and imports the module.
- **The operators and the panel stay as they are.** They read the preferences for the user, and they call the same lower functions.
- **A look is plain data.** `formats.appearance_look.Look` holds the body type, the kits by body part, the five colour choices and the item ids. `look_preset` turns it into an appearance preset with the rules of the panel: the default look, then the kits, then each item in its slot with the slots that it hides emptied.
- **`create_player` puts the rig where the script says.** The 32 game units to the right of the last player are a rule of the Create Player button only.
- **Scene timing is the script's.** `scripting.bake_clip` leaves the frame rate and the frame range of the scene alone unless the script asks.

The owner stated the wanted behaviour of each function in issue 170. The module name, the names of the functions and of their arguments are guesses of the Spec stage.

## Rejected options

- **Hidden operator properties for every input.** An operator still needs the add-on enabled, returns no object and reports errors as text.
- **Functions spread over the modules of each feature.** A script then has to know the module design, and a refactor breaks it.
- **A default brightness.** A script that forgets it gets the client's default of 0.8 and a scene that does not match its other parts.
