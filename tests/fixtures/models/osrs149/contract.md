# osrs149-static-v1

This contract records OpenRS2 snapshot 430 (OSRS revision 149), not RS2 revision
430. Encoding is independent of provenance: `old` has an 18-byte footer;
`osrs-ffff` has a 23-byte footer ending FF FF. Declaring the `osrs-149` profile
selects verified behavior; the marker alone does not identify a cache.

## Raw model reference

Each numbered JSON has `id`, `encoding`, DAT `source_sha256`, and the pinned
`client_sha256`. `vertices` and `faces` are ordered integer triples from the
unmodified RuneLite loader. Coordinates are original game coordinates; indices
are zero-based. No Blender coordinate transform or face removal is applied.

`raw` is recorded before renderer normalization:

| Field | Representation and normalization |
| --- | --- |
| `section_flags` | Original footer bytes: render section, global priority or 255, alpha section, face skins, textures (new only), vertex skins. |
| `face_colours` | Every original unsigned 16-bit face-colour slot. In old files a textured slot encodes its texture ID; in new files colour and texture ID are independent. |
| `face_textures` | Texture ID, or -1 when absent. New slots are unsigned 16-bit minus one; old packed flags identify textured slots. |
| `face_texture_indices` | Source record index, or -1. New textured entries are unsigned byte minus one; untextured entries are normalized to -1. Old entries come from packed flags shifted right two. |
| `face_render_types` | New original unsigned byte, or zero for a missing section. Old packed flags contribute bit zero only. |
| `render_priorities` | Unsigned per-face bytes, or the footer priority repeated for every face. Section presence remains in `section_flags`. |
| `face_alphas` | Unsigned bytes, or zero for a missing section. |
| `face_skins`, `vertex_skins` | Unsigned labels, or null when their section is absent. No groups are merged. |
| `texture_records` | Every record in original order, including unused records. Each has `kind`, three unsigned 16-bit `words`, and `parameters_hex`. Old records are kind zero. |
| `tail_hex` | Every byte between the final known section and footer, including the new format's zero marker. Old files have an empty tail. |

Only kind-zero words are vertex indices. For kinds 1 and 3, parameters contain
six scale bytes, two rotation bytes, one direction byte and two speed bytes.
Kind 2 adds two bytes after speed. Their lengths are therefore 11 and 13 bytes;
kind zero has no parameters. These names describe the source reader's sections,
not a verified Blender projection or the meanings of individual values.

## Client preview reference

`client_raw` captures all non-static primitive/array fields of the identified
revision-149 `dv` immediately after its byte-array constructor. `client_lit`
captures `ej` returned by the actual `dv.ae(64,768,-50,-10,-50)` lighting path.
Arrays preserve Java signedness; null remains null. These snapshots are retained
alongside canonical fields so corrections can be checked against the original
implementation without rerunning our own codec.

Verified field correspondences in this artifact:

| Client field | Meaning |
| --- | --- |
| `dv.j/n/r`, `dv.e/l/s` | Vertex XYZ and face ABC arrays, respectively. |
| `dv.g/k/w/m/p/t` | Face colours, texture IDs, render bytes, alpha bytes, per-face priorities, global priority. |
| `dv.au/ae/u` | Face labels, vertex labels, texture-coordinate indices. Untextured entries in `u` can contain unused zeroes. |
| `ej.t` | Third shade array: -2 means hidden, -1 flat, other values shaded. |
| `ej.x`, `ej.i/d/b` | Face mapping into retained texture records, and retained triangle corners. A null array or mapping -1 selects the face's own corners. |

The conversion retains referenced kind-zero records only. References to other
kinds become -1 and use own-face mapping in `ej.au`. Complex words must survive
export but must never be dereferenced as mesh vertices for this profile.

Stored render type 2 is hidden unless alpha overrides it. Alpha 255 forces
effective type 2; alpha 254 forces effective type 3. Effective type 3 is flat
when untextured and hidden when textured. The selected real files capture 33
type-2 hidden faces, six alpha-255 hidden faces and 52 alpha-254 flat faces.
The textured type-3 rule is bytecode evidence, not an observed snapshot-430 case.
See the pinned method offsets in the linked source findings in README.

The tail meanings remain unresolved. Exact bytes and record order are required.
Until a safe transformation is established, nonzero opaque tails and complex
parameters permit unchanged semantic export only; changes to final geometry or
other source fields must visibly refuse export. A zero tail marker alone does
not introduce this restriction. Specialized complex-projection editing is
deferred; operations unable to preserve these bindings must refuse before
mutation. Type-zero tools continue to use actual vertex references.

## Icon policy reference

`icons/coverage.json` identifies original raw item/model/texture resources,
render arguments, hashes, and three expected PNGs. Item 8283's unchanged factory
throws at neighbor index 1152 in its 1152-element framebuffer. Its expected PNG
implements the user's transparent-zero decision, not a recovered original game
pixel. The separate reference changes only factory class naming and allocation
to a 1153-element zero-filled array while retaining the 36 by 32 viewport.
The rasterizer is unchanged. Control icons 4151 and 995 are pixel-identical to
the original factory's successful results. Replay requires no full cache.
