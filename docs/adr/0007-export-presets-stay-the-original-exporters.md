# Export presets stay the original exporter's

In the architecture review of 2026-11-05 the owner chose to pin the original exporter's behaviour. `presets.py` keeps its render priority and face skin tables unchanged, and export keeps the legacy options and their meanings: `DEFAULT` gives every face priority 1, `CUSTOM_PRIORITY` exports the painted layers, the body-part presets apply their tables, and auto-detect writes a second `_drop.dat`. They go through `presets.apply_preset` and are pinned by the fixtures in `tests/fixtures/presets/`.

The tables are rules of thumb. Measured on 865 Old School worn models, they reproduce Jagex's real priorities on SWORD 87%, BOOTS 89%, GLOVES 74%, PANTS 73%, BODY 64%, SHIELD 25%, HEAD 24% and NECKLACE 9% of faces, and CAPE has no preset. Rebuilding the tables from game data would be a separate decision.
