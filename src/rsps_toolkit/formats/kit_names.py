"""Display names for identity kits, taken from the style lists in the cache's own enums. Nothing here imports bpy.

The client's makeover and character creation interfaces list each body part's styles as a pair of enums: one of style
names and one of the models that realise them, sharing keys. A kit takes the name of the style whose model it uses.
This was matched by comparing the enums of OpenRS2 snapshot 430 with the kits' models, so the enum ids below are
snapshot data and not part of the revision 149 client. Hands and feet have no such enums and use WIKI_NAMES.
"""

from collections.abc import Mapping

from .appearance import Kit
from .enum_definition import EnumDefinition

# Body part category -> (enum of style names, enum of style models). Hair and jaw enums list chathead models, the
# others list body models.
STYLE_ENUMS = {
    0: (881, 882),
    1: (884, 886),
    2: (771, 772),
    3: (775, 776),
    5: (778, 779),
    7: (888, 889),
    9: (781, 782),
    10: (784, 785),
    12: (787, 788),
}


# Hands and feet have no style enums. The user took these names from the OSRS wiki makeover interface images (shoes
# "Basic" and "Elven", wristwear "Basic" and "Plain") and assigned them to the two selectable kits of each category in
# ascending kit id order. The cache does not confirm which kit is which, so this order is unverified.
WIKI_NAMES = {4: ("Basic", "Plain"), 6: ("Basic", "Elven"), 11: ("Basic", "Plain"), 13: ("Basic", "Elven")}


def load_kit_names(enums: Mapping[int, EnumDefinition], kits: Mapping[int, Kit]) -> dict[int, str]:
    """Name each kit that a style list covers.

    A kit takes the name of the style whose model it uses, when only one style lists that model. Kits and styles
    left over are paired in ascending order, kit id against style key; this holds for every kit that the first rule
    also names, and it is what names the clean-shaven jaw (the one style with no model) and the torsos that share one
    base model. The order rule is unverified against the client: its only check is that it agrees with the model rule
    for every kit that both rules name. A category whose leftover kits and styles differ in number is left unnamed.
    """
    names: dict[int, str] = {}
    for category, (names_id, models_id) in STYLE_ENUMS.items():
        if names_id not in enums or models_id not in enums:
            raise ValueError(f"Enums {names_id} and {models_id} are missing for body part category {category}")
        names_enum, models_enum = enums[names_id], enums[models_id]
        style_names = dict(zip(names_enum.keys, names_enum.string_values, strict=True))
        models = models_enum.int_values
        style_of_model = dict(zip(models, models_enum.keys, strict=True))
        claimed: set[int] = set()
        unmatched: list[Kit] = []
        for kit in sorted(kits.values(), key=lambda k: k.id):
            if kit.body_part != category:
                continue
            candidates = (*kit.model_ids[:1], *kit.chathead_models[:1])
            style = next((style_of_model[m] for m in candidates if m in style_of_model and models.count(m) == 1), None)
            if style is None:
                unmatched.append(kit)
            else:
                names[kit.id] = style_names[style]
                claimed.add(style)
        left = sorted(key for key in style_names if key not in claimed)
        if len(unmatched) == len(left):
            for kit, key in zip(unmatched, left, strict=True):
                names[kit.id] = style_names[key]
    for category, wiki_names in WIKI_NAMES.items():
        selectable = [
            k for k in sorted(kits.values(), key=lambda k: k.id) if k.body_part == category and not k.non_selectable
        ]
        if len(selectable) != len(wiki_names):
            raise ValueError(f"Body part {category} has {len(selectable)} selectable kits, expected {len(wiki_names)}")
        names.update({kit.id: name for kit, name in zip(selectable, wiki_names, strict=True)})
    return names
