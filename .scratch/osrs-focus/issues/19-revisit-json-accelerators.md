# Revisit JSON accelerators when a loader for the large catalogs exists

Status: resolved

The benchmark of [plan 02](../plans/02-toolkit.md), Task 5, kept JSON loading on the standard library: msgspec and orjson are slower once the required duplicate-key rejection is kept, and the only real loading path costs about 0.3 ms ([results](../../../docs/osrs-cache-workflow.md#json-loading-benchmark)). Revisit only if a loader for the large cache 430 catalogs is added and a decoder that rejects duplicate keys itself is available. The owner decides then.

## Decisions

The user chose on 2026-11-10, in a design interview:

1. JSON loading stays on the standard library. (Facts: the loader for the large cache 430 catalogs now exists, in Player Appearance, and parses the 28.9 MB item catalog in about 160 ms without needing duplicate-key rejection; a compiled accelerator such as orjson would have to ship as wheels for each platform in the extension.)
2. Create, Update and held-item bakes, which each parse the catalog again, share the panel's parsed copy instead, reloaded when a catalog file changes ([issue 29](29-reuse-the-parsed-cache-catalogs.md)).

## Comments

- 2026-11-10, design interview with the user: resolved by decisions 1 and 2; the caching work is issue 29.
