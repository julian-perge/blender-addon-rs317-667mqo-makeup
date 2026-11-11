"""Names for the player's five colour choices in revision 149, in the order the appearance panel lists them.

The names come from the Old School wiki: the Hairstyles page for hair, and the body type section's clothing and shoe
colour tables that the user supplied. The wiki names none of the normal skin tones, so they are numbered.
"""

from dataclasses import dataclass

from .appearance import Palette

# The wiki's Hairstyles page lists 30; its last five (Navy blue to Aqua) came on 18 April 2023, after revision 149.
HAIR_NAMES = (
    "Dark brown",
    "White",
    "Light grey",
    "Dark grey",
    "Apricot",
    "Straw",
    "Light brown",
    "Brown",
    "Turquoise",
    "Green",
    "Ginger",
    "Magenta",
    "Black",
    "Grey",
    "Beige",
    "Peach",
    "Light blue",
    "Royal blue",
    "Pale pink",
    "Intense pink",
    "Maroon",
    "Light green",
    "Dark green",
    "Purple",
    "Light purple",
)
CLOTHING_NAMES = (
    "Khaki",
    "Charcoal",
    "Crimson",
    "Navy",
    "Straw",
    "White",
    "Red",
    "Blue",
    "Green",
    "Yellow",
    "Purple",
    "Orange",
    "Rose",
    "Lime",
    "Cyan",
    "Emerald",
    "Black",
    "Grey",
    "Onion",
    "Peach",
    "Lumbridge Blue",
    "Deep Blue",
    "Light Pink",
    "Cadmium Red",
    "Maroon",
    "Pale Green",
    "Turquoise",
    "Deep Purple",
    "Light Purple",
)
# The client's legs row starts with Emerald and then repeats the torso row from Khaki to Cyan, so the first sixteen
# entries are the torso's first sixteen rotated by one; the rest are in the torso's order.
LEGS_NAMES = (CLOTHING_NAMES[15], *CLOTHING_NAMES[:15], *CLOTHING_NAMES[16:])
SHOE_NAMES = ("Brown", "Khaki", "Ashen", "Dark", "Terracotta", "Grey")
# The skin row holds the normal tones first and then the event colours, in this order.
NORMAL_TONES = 8
SKIN_EXTRA_NAMES = ("Green", "Black", "White")

SLOT_NAMES = (HAIR_NAMES, CLOTHING_NAMES, LEGS_NAMES, SHOE_NAMES)
SKIN_SLOT = 4


@dataclass(frozen=True)
class ColourChoice:
    """One entry of a colour dropdown: the client's choice number, its name and its packed HSL colour."""

    index: int
    name: str
    colour: int


def colour_choices(palette: Palette, slot: int) -> list[ColourChoice]:
    """The choices of one colour slot in the order the panel lists them.

    Skin lists its normal tones from lightest to darkest, because the client's own order is not sorted, and numbers
    them in that order. Every other slot keeps the client's order.
    """
    row = palette.primary_choices[slot]
    if slot == SKIN_SLOT:
        if len(row) != NORMAL_TONES + len(SKIN_EXTRA_NAMES):
            raise ValueError(
                f"Expected {NORMAL_TONES + len(SKIN_EXTRA_NAMES)} skin colours, the palette has {len(row)}"
            )
        tones = sorted(range(NORMAL_TONES), key=lambda i: (-_lightness(row[i]), i))
        choices = [ColourChoice(i, f"Tone {n}", row[i]) for n, i in enumerate(tones, start=1)]
        extras = range(NORMAL_TONES, len(row))
        return choices + [ColourChoice(i, name, row[i]) for i, name in zip(extras, SKIN_EXTRA_NAMES, strict=True)]
    names = SLOT_NAMES[slot]
    if len(row) != len(names):
        raise ValueError(f"Colour slot {slot} has {len(row)} choices in the palette and {len(names)} names")
    return [ColourChoice(i, name, colour) for i, (name, colour) in enumerate(zip(names, row, strict=True))]


def _lightness(colour: int) -> int:
    return colour & 127
