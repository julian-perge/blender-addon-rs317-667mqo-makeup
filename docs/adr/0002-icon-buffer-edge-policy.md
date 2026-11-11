# Sample transparent zero beyond the inventory-icon framebuffer

The identified OSRS revision149 client and RuneLite cache1.13.6 both read the
next pixel in the alpha254 flat-span path, including past the end of a36x32
icon buffer. The original operation throws and supplies no reference colour.
The user approved transparent zero only for an out-of-buffer neighboring read;
all valid reads, viewport dimensions, camera values and source data remain.

This is a repair policy, not a claim about original game output. Capture its
expected pixels using the unchanged reference renderer with one zero-valued
guard cell. The production correction can then be compared against that separate
reference rather than generating expectations from the patched renderer.
