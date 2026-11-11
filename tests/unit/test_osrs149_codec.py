import json
import struct
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from rsps_toolkit.formats import InvalidModelError, ModelEncoding, decode, encode, restore_faces, set_aside_faces

FIXTURES = Path(__file__).parents[1] / "fixtures/models/osrs149"
MODEL_IDS = sorted(int(model_id) for model_id in json.loads((FIXTURES / "coverage.json").read_text())["models"])


def test_old_model_keeps_legacy_calls_and_explicit_profile():
    reference = json.loads((FIXTURES / "96.json").read_text())
    data = (FIXTURES / "96.dat").read_bytes()
    legacy = decode(data)
    contextual = decode(data, profile="osrs-149")
    assert legacy.encoding == contextual.encoding == ModelEncoding(reference["encoding"])
    assert legacy.profile is None
    assert contextual.profile == "osrs-149"
    assert contextual.vertices == legacy.vertices == [tuple(vertex) for vertex in reference["vertices"]]
    assert contextual.faces == legacy.faces == [tuple(face) for face in reference["faces"]]


def assert_reference(model, reference):
    raw = reference["raw"]
    assert model.encoding == ModelEncoding(reference["encoding"])
    assert model.profile == "osrs-149"
    assert model.vertices == [tuple(vertex) for vertex in reference["vertices"]]
    assert model.faces == [tuple(face) for face in reference["faces"]]
    assert model.face_textures == [None if value == -1 else value for value in raw["face_textures"]]
    assert model.face_colours == [
        colour if texture == -1 else None
        for colour, texture in zip(raw["face_colours"], raw["face_textures"], strict=True)
    ]
    assert model.render_priorities == raw["render_priorities"]
    assert model.face_alphas == raw["face_alphas"]
    assert model.face_skins == raw["face_skins"]
    assert model.vertex_skins == raw["vertex_skins"]
    assert model.texture_triangles == [tuple(record["words"]) for record in raw["texture_records"]]
    assert model.face_texture_triangles == [None if value == -1 else value for value in raw["face_texture_indices"]]
    if model.encoding is ModelEncoding.OLD:
        assert model.new_data is None
        assert model.flat_shaded == [bool(value) for value in raw["face_render_types"]]
        return
    assert model.new_data is not None
    assert model.new_data.textured_face_colours == tuple(
        colour if texture != -1 else None
        for colour, texture in zip(raw["face_colours"], raw["face_textures"], strict=True)
    )
    assert model.new_data.face_render_types == tuple(raw["face_render_types"])
    assert model.new_data.texture_render_types == tuple(record["kind"] for record in raw["texture_records"])
    assert model.new_data.texture_parameters == tuple(
        bytes.fromhex(record["parameters_hex"]) for record in raw["texture_records"]
    )
    assert model.new_data.tail == bytes.fromhex(raw["tail_hex"])


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_new_model_matches_independent_fields(model_id):
    reference = json.loads((FIXTURES / f"{model_id}.json").read_text())
    assert_reference(decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149"), reference)


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_new_model_roundtrip_preserves_encoding_and_all_source_fields(model_id):
    model = decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")
    encoded = encode(model)
    assert (encoded[-2:] == b"\xff\xff") == (model.encoding is ModelEncoding.OSRS_FFFF)
    assert decode(encoded, profile="osrs-149") == model


@pytest.mark.parametrize(
    "model_id", [3676, 5452, 5454, 8791, 10468, 11064, 28630, 28643, 28714, 32181, 32814, 33113, 33114, 33144]
)
def test_set_aside_roundtrip_keeps_new_fields(model_id):
    model = decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")
    visible, aside = set_aside_faces(model)
    assert aside
    restored = restore_faces(visible, aside)
    assert restored == model
    assert decode(encode(restored), profile="osrs-149") == model


@pytest.mark.parametrize("case", ["no-profile", "wrong-profile", "fffd", "fffe", "short-new", "short-old"])
def test_unsupported_profiles_markers_and_truncated_inputs_are_refused(case):
    data = (FIXTURES / "32971.dat").read_bytes()
    profile: Any = "osrs-149"
    if case == "no-profile":
        profile = None
    elif case == "wrong-profile":
        profile = "osrs-170"
    elif case in ("fffd", "fffe"):
        data = data[:-2] + bytes.fromhex(case)
    elif case == "short-new":
        data = b"\xff\xff"
    else:
        data = b""
    with pytest.raises(InvalidModelError):
        decode(data, profile=profile)


@pytest.mark.parametrize(
    "case",
    [
        "float-vertex",
        "float-alpha",
        "parameter-type",
        "empty-tail",
        "short-tail",
        "independent-colour",
        "kind",
        "render-byte",
        "flat-view",
        "missing-source",
        "profile",
        "encoding",
    ],
)
def test_encode_refuses_invalid_or_unrepresentable_source_fields(case):
    model: Any = decode((FIXTURES / "28634.dat").read_bytes(), profile="osrs-149")
    source: Any = model.new_data
    assert source is not None
    if case == "float-vertex":
        x, y, z = model.vertices[0]
        model.vertices[0] = (x + 0.5, y, z)
    elif case == "float-alpha":
        model.face_alphas[0] = 0.5
    elif case == "parameter-type":
        model.new_data = replace(source, texture_parameters=("x" * 13, *source.texture_parameters[1:]))
    elif case == "empty-tail":
        model.new_data = replace(source, tail=b"")
    elif case == "short-tail":
        model.new_data = replace(source, tail=b"\x01")
    elif case == "independent-colour":
        model.new_data = replace(source, textured_face_colours=(None,) * len(model.faces))
    elif case == "kind":
        model.new_data = replace(source, texture_render_types=(4, *source.texture_render_types[1:]))
    elif case == "render-byte":
        model.new_data = replace(source, face_render_types=(256, *source.face_render_types[1:]))
    elif case == "flat-view":
        model.flat_shaded[0] = not model.flat_shaded[0]
    elif case == "missing-source":
        model.new_data = None
    elif case == "profile":
        model.profile = None
    else:
        model.encoding = "unknown"
    with pytest.raises(InvalidModelError):
        encode(model)


def test_old_decoder_cannot_consume_the_footer_as_missing_vertex_data():
    header_only = struct.pack(">HHBBBBBBHHHH", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(InvalidModelError):
        decode(header_only)


def large_vertex_model():
    model = decode((FIXTURES / "32971.dat").read_bytes(), profile="osrs-149")
    extra = 20001 - len(model.vertices)
    model.vertices.extend([model.vertices[0]] * extra)
    if model.vertex_skins is not None:
        model.vertex_skins.extend([model.vertex_skins[0]] * extra)
    return model


def test_new_encoding_allows_vertex_counts_beyond_legacy_limit():
    model = large_vertex_model()
    assert decode(encode(model), profile="osrs-149") == model
    with pytest.raises(InvalidModelError, match="20001 vertices"):
        replace(model, encoding=ModelEncoding.OLD, profile=None, new_data=None)


def test_new_encoding_still_refuses_unrepresentable_face_index_deltas():
    model = large_vertex_model()
    model.faces[0] = (20000, 1, 2)
    with pytest.raises(InvalidModelError, match="smart"):
        encode(model)


def test_encoder_rule_for_texture_coordinate_byte_limit():
    # Unverified: this pins our own encoder rule that index 254 is storable and 255 is not. No client or reference
    # output has confirmed the limit.
    model = decode((FIXTURES / "28954.dat").read_bytes(), profile="osrs-149")
    source = model.new_data
    assert source is not None
    extra = 255 - len(model.texture_triangles)
    model.texture_triangles.extend([model.texture_triangles[0]] * extra)
    model.new_data = replace(
        source,
        texture_render_types=source.texture_render_types + (source.texture_render_types[0],) * extra,
        texture_parameters=source.texture_parameters + (source.texture_parameters[0],) * extra,
    )
    face = next(i for i, texture in enumerate(model.face_textures) if texture is not None)
    model.face_texture_triangles[face] = 254
    assert decode(encode(model), profile="osrs-149") == model
    with pytest.raises(InvalidModelError, match="over 63"):
        replace(model, encoding=ModelEncoding.OLD, new_data=None)
    model.face_texture_triangles[face] = 255
    with pytest.raises(InvalidModelError):
        encode(model)


def test_encode_refuses_a_stream_exceeding_its_unsigned_short_length():
    model = decode((FIXTURES / "32971.dat").read_bytes(), profile="osrs-149")
    source = model.new_data
    assert source is not None
    face = next(i for i, corners in enumerate(model.faces) if len(set(corners)) == 3)
    count = 25000
    changes: dict[str, Any] = {
        name: [getattr(model, name)[face]] * count
        for name in (
            "faces",
            "face_colours",
            "face_textures",
            "face_alphas",
            "render_priorities",
            "face_texture_triangles",
            "flat_shaded",
        )
    }
    changes["face_skins"] = None if model.face_skins is None else [model.face_skins[face]] * count
    changes["new_data"] = replace(
        source,
        textured_face_colours=(source.textured_face_colours[face],) * count,
        face_render_types=(source.face_render_types[face],) * count,
    )
    with pytest.raises(InvalidModelError, match="stream"):
        encode(replace(model, **changes))


def _reference(model_id):
    return json.loads((FIXTURES / f"{model_id}.json").read_text())


def test_index_89_fixture_is_representable_only_in_its_source_encoding():
    model = decode((FIXTURES / "28954.dat").read_bytes(), profile="osrs-149")
    assert max(i for i in _reference(28954)["raw"]["face_texture_indices"]) == 89
    assert decode(encode(model), profile="osrs-149") == model
    with pytest.raises(InvalidModelError, match="over 63"):
        replace(model, encoding=ModelEncoding.OLD, new_data=None)


def test_fixtures_include_unused_texture_records_and_nonzero_tails_that_survive():
    unused = nonzero_tail = 0
    for model_id in MODEL_IDS:
        raw = _reference(model_id)["raw"]
        if raw["tail_hex"] and int(raw["tail_hex"][:2], 16) != 0:
            nonzero_tail += 1
        used = {i for i in raw["face_texture_indices"] if i != -1}
        if raw["texture_records"] and len(used) < len(raw["texture_records"]):
            unused += 1
    assert unused > 0
    assert nonzero_tail > 0


def test_old_encoder_refuses_a_new_format_model():
    from rsps_toolkit.formats import old_format

    model = decode((FIXTURES / "28634.dat").read_bytes(), profile="osrs-149")
    with pytest.raises(InvalidModelError):
        old_format.encode(model)


@pytest.mark.parametrize("case", ["section-overrun", "bad-footer-flag", "truncated-body"])
def test_malformed_new_format_footers_are_refused(case):
    data = bytearray((FIXTURES / "32971.dat").read_bytes())
    footer = len(data) - 23
    if case == "section-overrun":
        data[footer + 12 : footer + 14] = b"\xff\xff"
    elif case == "bad-footer-flag":
        data[footer + 6] = 2
    else:
        data = data[:20] + data[-23:]
    with pytest.raises(InvalidModelError):
        decode(bytes(data), profile="osrs-149")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_unedited_model_keeps_its_source_section_flags(model_id):
    reference = _reference(model_id)
    if reference["encoding"] != ModelEncoding.OSRS_FFFF.value:
        pytest.skip("old format has no section flags")
    model = decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")
    assert model.new_data is not None
    assert list(model.new_data.section_flags or ()) == reference["raw"]["section_flags"]
    assert list(encode(model)[-18:-12]) == reference["raw"]["section_flags"]


def test_edit_that_contradicts_a_source_flag_falls_back_to_computed_layout():
    model = decode((FIXTURES / "28954.dat").read_bytes(), profile="osrs-149")
    assert model.new_data is not None
    assert model.new_data.section_flags is not None
    assert model.new_data.section_flags[2] == 0
    model.face_alphas[0] = 7
    encoded = encode(model)
    assert encoded[-18 + 2] == 1
    again = decode(encoded, profile="osrs-149")
    assert again.face_alphas[0] == 7
    assert again.new_data is not None
    assert again.new_data.section_flags is not None
    assert again.new_data.section_flags[2] == 1


def test_hand_built_model_without_section_flags_encodes_and_gains_flags():
    model = decode((FIXTURES / "28634.dat").read_bytes(), profile="osrs-149")
    assert model.new_data is not None
    built = replace(model, new_data=replace(model.new_data, section_flags=None))
    again = decode(encode(built), profile="osrs-149")
    assert again.new_data is not None
    assert again.new_data.section_flags is not None
    assert replace(again, new_data=replace(again.new_data, section_flags=None)) == built


def test_restoring_a_set_aside_face_without_source_fields_is_refused():
    model = decode((FIXTURES / "3676.dat").read_bytes(), profile="osrs-149")
    reduced, aside = set_aside_faces(model)
    assert aside
    aside[0] = replace(aside[0], render_type=None)
    with pytest.raises(InvalidModelError, match="lacks OSRS-149 source fields"):
        restore_faces(reduced, aside)


def _mutated(model_id, mutate):
    data = bytearray((FIXTURES / f"{model_id}.dat").read_bytes())
    footer = len(data) - 23
    vertex_count, face_count, texture_count, render = struct.unpack_from(">HHBB", data, footer)
    mutate(data, vertex_count, face_count, texture_count, render)
    return bytes(data)


def _set_vertex_flag(data, vertex_count, face_count, texture_count, render):
    data[texture_count] = 8


def _set_face_kind(value):
    def mutate(data, vertex_count, face_count, texture_count, render):
        data[texture_count + vertex_count + (face_count if render else 0)] = value

    return mutate


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        ("vertex-flag-8", _set_vertex_flag),
        ("face-kind-0", _set_face_kind(0)),
        ("face-kind-5", _set_face_kind(5)),
        ("texture-kind-4", lambda data, v, f, texture_count, r: data.__setitem__(0, 4) if texture_count else None),
    ],
)
def test_decode_refuses_mutated_source_bytes(name, mutate):
    model_id = 28634
    data = _mutated(model_id, mutate)
    assert data != (FIXTURES / f"{model_id}.dat").read_bytes(), "mutation did not apply"
    with pytest.raises(InvalidModelError):
        decode(data, profile="osrs-149")


def test_decode_refuses_a_face_index_past_the_vertex_count_and_unused_coordinate_bytes():
    model = decode((FIXTURES / "28634.dat").read_bytes(), profile="osrs-149")
    with pytest.raises(InvalidModelError, match="does not exist"):
        replace(model, faces=[(0, 1, len(model.vertices))] + model.faces[1:])
    data = bytearray((FIXTURES / "28634.dat").read_bytes())
    footer = len(data) - 23
    coord_length = struct.unpack_from(">H", data, footer + 19)[0]
    struct.pack_into(">H", data, footer + 19, coord_length + 1)
    with pytest.raises(InvalidModelError):
        decode(bytes(data), profile="osrs-149")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_unused_texture_records_and_tails_survive_decode_and_encode(model_id):
    raw = _reference(model_id)["raw"]
    if _reference(model_id)["encoding"] != ModelEncoding.OSRS_FFFF.value:
        pytest.skip("old format has no opaque tail")
    again = decode(encode(decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")), profile="osrs-149")
    assert again.new_data is not None
    assert again.new_data.tail.hex() == raw["tail_hex"]
    assert len(again.texture_triangles) == len(raw["texture_records"])
