# A saved region carries a key, and a stale file is imported again

The import of region 51_49 takes 6 to 9 seconds, and a script that renders one shot in each Blender run pays it every time. [Issue 170](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/170) asks to save an imported region to a .blend and append it later, with a key that detects a stale file. A probe on 2026-11-20 appended the saved region 51_49 in 1.2 seconds, with the same texture pixels.

## Decision

- **`region_files.save_region` writes the region collection to its own .blend**, as `save_player` writes a player.
- **The key is JSON text with every input of the import:** a SHA-256 of the files of the add-on (the code, the manifest with the version and the data tables), the Blender version, the size and the modified time of the cache data file and of the key file of the region, the region numbers, the brightness and the wall decoration clearance.
- **The file holds the key in a text datablock named `rs_region_key <the first 32 hex digits of the SHA-256 of the key>`.** Blender lists the names of a .blend without loading its data, so a stale file costs no append.
- **`region_files.append_region` returns None and changes nothing** when the file is missing, has another key or is not a .blend. `scripting.import_regions` then imports the region and writes the file again.
- **The saved region is as the import made it.** The region origin and the turn are applied after the import or the append, so one file serves every origin.
- **The hash of the files is part of the key** because the calling repo runs the add-on from a working tree, where the version does not change with the code.

The owner asked for the key and gave the add-on version and the import options as examples. The other parts of the key, the text datablock and the file name are guesses of the Spec stage.

## Rejected options

- **A custom property on the collection.** Blender reads it only after the append, so a stale file costs the append and a clean-up.
- **A second file beside the .blend.** The two files can go out of step.
- **The key in the file name.** Old files pile up in the folder.
