from rsps_toolkit.formats.attribute_list import attribute_names, naming_problems

# The owner chose on 2026-11-17 that "Extra attributes" is one comma-separated text field, that the order of the names
# is the order of COLOR_1 and up, and that empty text means none (spec 140, decision 7 and rule 3). In the build of
# issue 141 on 2026-11-17 the owner chose that the spaces around a name are not part of it, that an empty item is
# skipped, that a repeated name or the colour attribute in the list stops the export, and the wording of the messages.


def test_the_names_keep_the_order_of_the_text():
    assert attribute_names("fire_strength,wind") == ("fire_strength", "wind")


def test_empty_text_gives_no_names():
    assert attribute_names("") == ()


def test_the_spaces_around_a_name_are_not_part_of_it_and_an_empty_item_is_skipped():
    assert attribute_names(" fire_strength , ,wind ") == ("fire_strength", "wind")


def test_distinct_names_have_no_problem():
    assert naming_problems("scene_lit", ("fire_strength", "wind")) == []


def test_a_repeated_extra_attribute_is_a_problem():
    assert naming_problems("scene_lit", ("wind", "fire_strength", "wind")) == ["Extra attributes name wind twice."]


def test_the_colour_attribute_in_the_extra_attributes_is_a_problem():
    assert naming_problems("scene_lit", ("scene_lit",)) == [
        "scene_lit is the colour attribute, so it cannot be an extra attribute."
    ]


def test_an_empty_colour_attribute_is_a_problem():
    assert naming_problems("", ()) == ["Set the colour attribute."]
