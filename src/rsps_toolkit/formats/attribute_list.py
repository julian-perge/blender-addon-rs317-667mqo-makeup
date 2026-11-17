"""The parse and the checks of the attribute fields of the RS Scene export. Nothing here imports bpy."""

from collections import Counter
from collections.abc import Sequence


def attribute_names(text: str) -> tuple[str, ...]:
    """The names in the comma-separated `text`, in the order of the text, without the spaces around each name. Text
    with no names gives none."""
    names = (name.strip() for name in text.split(","))
    return tuple(name for name in names if name)


def naming_problems(colour: str, extras: Sequence[str]) -> list[str]:
    """One sentence for each reason why `colour` and `extras` cannot name the colour attributes of one file. The file
    writes each extra as its own `COLOR_n`, so a name can be there only once."""
    if not colour:
        return ["Set the colour attribute."]
    problems = [f"Extra attributes name {name} twice." for name, count in Counter(extras).items() if count > 1]
    if colour in extras:
        problems.append(f"{colour} is the colour attribute, so it cannot be an extra attribute.")
    return problems
