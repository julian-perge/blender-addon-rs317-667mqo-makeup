# Preserve model encodings with standalone Python import and export

For OSRS cache support, imported models retain their original encoding and all
decoded game data, including fields that do not affect the Blender preview. The
Blender extension reads and writes models in Python without requiring Java or a
local server; the dumper prepares source assets and cache identity. The user
selected this over presentation-only import or a mandatory prepared-bundle
workflow during the cache-430 design interview (Q2, Q4, Q5 and Q7).

This requires richer model records and codecs instead of normalizing every
model to the currently supported old format. Retain unresolved data unchanged
and visibly refuse exports after edits that could invalidate it. This preserves
the standalone workflow and avoids silent data loss, at the cost of maintaining
Python format handling alongside the dumper's Java implementation. Byte-identical
file layout is not required; this decision does not authorize new-format
conversion or waive independent reference checks.
