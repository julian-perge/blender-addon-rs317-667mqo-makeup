"""The editable player appearance on a scene, converted to and from the pure `AppearancePreset`."""

import functools

import bpy
from bpy.app.handlers import persistent

from ..formats.appearance import (
    ARMS_SLOT,
    BODY_PART_SLOTS,
    FEMALE_CATEGORY_OFFSET,
    HAIR_SLOT,
    HANDS_SLOT,
    HEAD_ITEM_SLOT,
    ITEM_OFFSET,
    JAW_SLOT,
    KIT_OFFSET,
    SHIELD_SLOT,
    TORSO_SLOT,
    WEAPON_SLOT,
    Palette,
    default_equipment,
    default_slot_value,
    load_palette,
)
from ..formats.appearance_colours import colour_choices
from ..formats.appearance_preset import AppearancePreset
from ..formats.cache_profile import PALETTE_PATH, REVISION, CacheProfile, MissingResourceError, shared_profile
from ..formats.item_wear import ItemWear, load_item_wear
from . import appearance_swatches, preferences

# OpenRS2 snapshot that the kit, item and model ids come from.
SNAPSHOT_ID = 430


# What each body part category dresses, in the order of BODY_PART_SLOTS.
BODY_PART_LABELS = ("Head", "Jaw", "Torso", "Arms", "Hands", "Legs", "Feet")
# Dropdown identifiers, which sit beside kit ids written as decimal strings.
NONE_KIT = "none"
OTHER = "other"
# The covers toggles: the property, the slot of the item that covers, the slot it empties, and the label. The
# emptied slot holds a kit, or for the shield an item.
COVERS = (
    ("covers_arms", TORSO_SLOT, ARMS_SLOT, "Covers arms"),
    ("covers_hair", HEAD_ITEM_SLOT, HAIR_SLOT, "Covers hair"),
    ("covers_jaw", HEAD_ITEM_SLOT, JAW_SLOT, "Covers jaw"),
    ("covers_hands", TORSO_SLOT, HANDS_SLOT, "Covers hands"),
    ("weapon_covers_hands", WEAPON_SLOT, HANDS_SLOT, "Covers hands"),
    ("covers_shield", WEAPON_SLOT, SHIELD_SLOT, "Covers shield"),
)
# How a baked clip advances its frames, chosen in the panel and passed to the bake.
PLAY_AS_ITEMS = (
    ("POSE", "Pose", "Stand, walk or run: loops from the first frame and ignores the loop offset"),
    ("ACTION", "Action", "Plays once, or repeats from its loop offset until its loop limit, then stops"),
)

# Why the dropdowns cannot list kits or names, shown by the panel. Empty when they can.
profile_error = ""
# Blender keeps only references to enum item strings, so the last lists are held here.
_kept_items: list[list[tuple]] = []


def profile() -> CacheProfile | None:
    """The shared cache profile for the preferences' dump folder, the one Create, Update and bakes also use."""
    folder = preferences.cache_dump_folder()
    if folder is None:
        return None
    return shared_profile(folder)


def kit_choices(props: "RsAppearanceProperties", part: int) -> list[tuple[str, str, str]]:
    """The selectable kits of one body part category for the chosen body type, then an entry for any other value.

    The client has no empty choice for a body part that has kits, so none is offered (an empty jaw slot would
    remove the jaw, where the client's clean-shaven choice is a kit). A category with no kits offers only None.
    The last entry stands for a slot that holds an item, nothing, or a kit of the other body type; picking it
    changes nothing.
    """
    global profile_error
    choices: list[tuple[str, str, str]] = []
    cache = profile()
    profile_error = "" if cache is not None else "Set the cache dump folder to list kits"
    if cache is not None:
        try:
            category = part + (FEMALE_CATEGORY_OFFSET if props.female else 0)
            names = _names(cache)
            choices = [
                (str(kit.id), names.get(kit.id, f"Kit {kit.id}"), f"Kit {kit.id}")
                for kit in sorted(cache.kits.values(), key=lambda k: k.id)
                if kit.body_part == category and not kit.non_selectable
            ]
        except MissingResourceError as error:
            profile_error = str(error)
    if not choices:
        choices = [(NONE_KIT, "None", "No kit exists for this body part")]
    choices.append((OTHER, "Other (see raw slots)", "The slot holds an item, nothing, or a kit of the other body type"))
    _kept_items.append(choices)
    del _kept_items[:-32]
    return choices


def _names(cache: CacheProfile) -> dict[int, str]:
    """Kit names from the cache's enums. Without the enums the dropdowns show kit ids and the panel says why."""
    global profile_error
    try:
        return cache.kit_names
    except MissingResourceError as error:
        profile_error = str(error)
        return {}


def _kit_property(part: int):
    slot = BODY_PART_SLOTS[part]

    def items(self, context):
        return kit_choices(self, part)

    def get(self):
        value = self.equipment[slot]
        names = [name for name, _, _ in kit_choices(self, part)]
        if value == 0:
            return names.index(NONE_KIT) if NONE_KIT in names else names.index(OTHER)
        kit = str(value - KIT_OFFSET)
        return names.index(kit) if KIT_OFFSET <= value < ITEM_OFFSET and kit in names else names.index(OTHER)

    def set(self, index):
        name = kit_choices(self, part)[index][0]
        if name != OTHER:
            self.equipment[slot] = 0 if name == NONE_KIT else int(name) + KIT_OFFSET

    return bpy.props.EnumProperty(name=BODY_PART_LABELS[part], items=items, get=get, set=set)


def set_covered(props: "RsAppearanceProperties", kit_slot: int, covered: bool) -> None:
    """Empty a slot that a worn item covers, or put back what it held before.

    What it held is kept per scene, not in presets. An item, such as a shield, comes back as it was. For a kit slot,
    when nothing was kept, or the kit belongs to the other body type, the body type's default kit comes back.
    """
    current = props.equipment[kit_slot]
    if covered:
        if current:
            props.covered_kits[kit_slot] = current
        props.equipment[kit_slot] = 0
        return
    if current:
        return
    kept, kits = props.covered_kits[kit_slot], _kits()
    props.covered_kits[kit_slot] = 0
    if kits is None or kept >= ITEM_OFFSET or kit_slot not in BODY_PART_SLOTS:
        props.equipment[kit_slot] = kept
        return
    part = BODY_PART_SLOTS.index(kit_slot)
    category = part + (FEMALE_CATEGORY_OFFSET if props.female else 0)
    kit = kits.get(kept - KIT_OFFSET)
    fits = kit is not None and kit.body_part == category
    props.equipment[kit_slot] = kept if fits else default_slot_value(kits, kit_slot, props.female)


def has_kits(props: "RsAppearanceProperties", kit_slot: int) -> bool:
    """False when the body type has no selectable kit for a body part slot, as the female body has none for the jaw.
    True for a slot that holds only items."""
    kits = _kits()
    if kits is None or kit_slot not in BODY_PART_SLOTS:
        return True
    category = BODY_PART_SLOTS.index(kit_slot) + (FEMALE_CATEGORY_OFFSET if props.female else 0)
    return any(kit.body_part == category and not kit.non_selectable for kit in kits.values())


@functools.cache
def item_wear() -> ItemWear:
    return load_item_wear()


def hides(props: "RsAppearanceProperties", item_slot: int, kit_slot: int) -> bool:
    """True when the item worn in `item_slot` empties `kit_slot` in the game, by the recent cache's wear positions."""
    item_id = props.equipment[item_slot] - ITEM_OFFSET
    return item_id >= 0 and kit_slot in item_wear().hides.get(item_id, ())


def locked(props: "RsAppearanceProperties", item_slot: int, kit_slot: int) -> bool:
    """True when the worn item hides the kit and kept its worn models since snapshot 430, so its toggle stays ticked.

    An item whose models changed keeps a free toggle, because the recent cache's rule was written for other models.
    """
    item_id = props.equipment[item_slot] - ITEM_OFFSET
    return hides(props, item_slot, kit_slot) and not item_wear().models_changed(item_id)


def covered(props: "RsAppearanceProperties", kit_slot: int) -> bool:
    """True when an item fills the kit slot, or a ticked covers toggle has emptied it."""
    if props.equipment[kit_slot] >= ITEM_OFFSET:
        return True
    return any(slot == kit_slot and getattr(props, name) for name, _, slot, _ in COVERS)


def _covers_property(item_slot: int, kit_slot: int, label: str):
    def get(self):
        worn = self.equipment[item_slot] >= ITEM_OFFSET
        return worn and self.equipment[kit_slot] == 0 and has_kits(self, kit_slot)

    def set(self, value):
        if not value and locked(self, item_slot, kit_slot):
            return
        set_covered(self, kit_slot, value)

    description = "The worn item hides this part, so its slot is emptied, as the game server does"
    return bpy.props.BoolProperty(name=label, description=description, get=get, set=set)


# The five colour dropdowns, by colour slot, with the panel's label for each.
COLOUR_LABELS = ("Hair colour", "Torso colour", "Legs colour", "Shoe colour", "Skin")


def colour_items(slot: int) -> list[tuple[str, str, str, int, int]]:
    """The dropdown entries of a colour slot: client choice number, name, hex colour, swatch icon and number."""
    choices = [
        (str(c.index), c.name, appearance_swatches.hex_code(c.colour), appearance_swatches.icon(c.colour), c.index)
        for c in colour_choices(palette(), slot)
    ]
    _kept_items.append(choices)
    del _kept_items[:-32]
    return choices


def _colour_property(slot: int):
    def items(self, context):
        return colour_items(slot)

    def get(self):
        return self.colours[slot]

    def set(self, value):
        self.colours[slot] = value

    # The stubs leave out the icon value Blender accepts in the fourth place of an item.
    return bpy.props.EnumProperty(name=COLOUR_LABELS[slot], items=items, get=get, set=set)  # pyrefly: ignore[bad-argument-type]


def fill_default_kits(props: "RsAppearanceProperties") -> None:
    """Give an appearance whose slots are all empty the client's default look for its body type.

    A new scene holds no kits, so without this Create Player has nothing to assemble until every kit is picked. The
    slots stay empty when the dump folder is unset or has no kits.
    """
    if any(props.equipment):
        return
    kits = _kits()
    if kits is not None:
        props.equipment = default_equipment(kits, female=props.female)


def _female_changed(self, context) -> None:
    """Give the chosen body type its default look when the slots are empty or hold the other body type's default.

    The other body type's kits do not apply to this one, so its default look would show as Other in every dropdown.
    A look the user chose is left alone.
    """
    kits = _kits()
    if kits is not None and list(self.equipment) in (
        [0] * len(self.equipment),
        default_equipment(kits, female=not self.female),
    ):
        self.equipment = default_equipment(kits, female=self.female)


def _kits():
    cache = profile()
    if cache is None:
        return None
    try:
        return cache.kits
    except MissingResourceError:
        return None


@persistent
def fill_scenes(*_args) -> None:
    """Fill every scene's empty appearance with the default look. Blender calls this after it loads a file."""
    for scene in bpy.data.scenes:
        fill_default_kits(scene.rs_appearance)  # pyrefly: ignore[missing-attribute]


@functools.cache
def palette() -> Palette:
    return load_palette(PALETTE_PATH)


def colour_limits() -> tuple[int, ...]:
    """The highest choice each colour slot has in the shipped palette, which differs by slot."""
    return tuple(len(row) - 1 for row in palette().primary_choices)


def _clamp_colours(self, context) -> None:
    limits = colour_limits()
    for slot, limit in enumerate(limits):
        if self.colours[slot] > limit:
            self.colours[slot] = limit


class RsAppearanceProperties(bpy.types.PropertyGroup):
    female: bpy.props.BoolProperty(name="Female", default=False, update=_female_changed)  # pyrefly: ignore[bad-assignment]
    equipment: bpy.props.IntVectorProperty(  # pyrefly: ignore[bad-assignment]
        name="Equipment",
        description="Twelve slots as the client stores them: 0 empty, kit id + 256, or item id + 512",
        size=12,
        min=0,
    )
    source_player: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Player",
        description="The player collection these settings belong to, or empty when they came from a preset file",
    )
    clip_sequence: bpy.props.IntProperty(  # pyrefly: ignore[bad-assignment]
        name="Clip",
        description="The sequence id of the game clip the bake buttons read from the cache",
        default=819,
        min=0,
    )
    clip_smooth: bpy.props.BoolProperty(  # pyrefly: ignore[bad-assignment]
        name="Smooth bone clips",
        description="Blend bone clips from each game frame to the next. The game itself holds each frame for its "
        "ticks, which is how clips bake when this is off",
    )
    clip_play_as: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Play As",
        description="How the client advances the clip's frames. It changes only clips with a loop offset",
        items=PLAY_AS_ITEMS,
        default="POSE",
    )
    last_error: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Last error", description="The message of the last failed preview operation, shown in the panel"
    )
    kit_head: _kit_property(0)  # pyrefly: ignore[bad-assignment]
    kit_jaw: _kit_property(1)  # pyrefly: ignore[bad-assignment]
    kit_torso: _kit_property(2)  # pyrefly: ignore[bad-assignment]
    kit_arms: _kit_property(3)  # pyrefly: ignore[bad-assignment]
    kit_hands: _kit_property(4)  # pyrefly: ignore[bad-assignment]
    kit_legs: _kit_property(5)  # pyrefly: ignore[bad-assignment]
    kit_feet: _kit_property(6)  # pyrefly: ignore[bad-assignment]
    covers_arms: _covers_property(*COVERS[0][1:])  # pyrefly: ignore[bad-assignment]
    covers_hair: _covers_property(*COVERS[1][1:])  # pyrefly: ignore[bad-assignment]
    covers_jaw: _covers_property(*COVERS[2][1:])  # pyrefly: ignore[bad-assignment]
    covers_hands: _covers_property(*COVERS[3][1:])  # pyrefly: ignore[bad-assignment]
    weapon_covers_hands: _covers_property(*COVERS[4][1:])  # pyrefly: ignore[bad-assignment]
    covers_shield: _covers_property(*COVERS[5][1:])  # pyrefly: ignore[bad-assignment]
    covered_kits: bpy.props.IntVectorProperty(  # pyrefly: ignore[bad-assignment]
        name="Covered kits",
        description="Per slot, the kit a covers toggle emptied, put back when the toggle is cleared",
        size=12,
        min=0,
        options={"HIDDEN"},
    )
    colour_hair: _colour_property(0)  # pyrefly: ignore[bad-assignment]
    colour_torso: _colour_property(1)  # pyrefly: ignore[bad-assignment]
    colour_legs: _colour_property(2)  # pyrefly: ignore[bad-assignment]
    colour_feet: _colour_property(3)  # pyrefly: ignore[bad-assignment]
    colour_skin: _colour_property(4)  # pyrefly: ignore[bad-assignment]
    colours: bpy.props.IntVectorProperty(  # pyrefly: ignore[bad-assignment]
        name="Colours",
        description="One palette choice per colour slot, limited to the choices the client has for that slot",
        size=5,
        min=0,
        update=_clamp_colours,
    )


def to_preset(props: RsAppearanceProperties) -> AppearancePreset:
    return AppearancePreset(
        client_revision=REVISION,
        snapshot_id=SNAPSHOT_ID,
        female=props.female,
        equipment=tuple(props.equipment),
        colours=tuple(props.colours),
    )


def from_preset(props: RsAppearanceProperties, preset: AppearancePreset) -> None:
    """Copy a preset into the properties, refusing one made for another revision."""
    if preset.client_revision != REVISION:
        raise ValueError(f"The preset is for client revision {preset.client_revision}, this panel supports {REVISION}")
    for slot, (choice, limit) in enumerate(zip(preset.colours, colour_limits(), strict=True)):
        if choice > limit:
            raise ValueError(f"Colour slot {slot} has choices 0 to {limit}, the preset asks for {choice}")
    props.equipment = preset.equipment
    props.colours = preset.colours
    props.female = preset.female


def register_properties() -> None:
    bpy.types.Scene.rs_appearance = bpy.props.PointerProperty(type=RsAppearanceProperties)


def unregister_properties() -> None:
    if hasattr(bpy.types.Scene, "rs_appearance"):
        del bpy.types.Scene.rs_appearance


classes = (RsAppearanceProperties,)
