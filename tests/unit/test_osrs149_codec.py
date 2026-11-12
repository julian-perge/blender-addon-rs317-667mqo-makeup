import json
import struct
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from rsps_toolkit.formats import (
    InvalidModelError,
    Model,
    ModelEncoding,
    NewFormatData,
    decode,
    encode,
    restore_faces,
    set_aside_faces,
)

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
    # Client rev 149, class dv, method j, offsets 1632 to 1665: a face's texture coordinate is one file byte that
    # holds the index plus 1. Class dv, method ae, offsets 428 to 436 and 449 to 459: file byte 0 means no texture
    # triangle, and any other byte is used as an unsigned index, so 254 is the highest index. The client has no check
    # of its own. We refuse 255 because it does not fit in the byte. A model has at most 255 texture triangles, so
    # index 255 is refused as a missing triangle, and a 256th triangle is refused by the count.
    # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 3.
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
    with pytest.raises(InvalidModelError, match="missing texture triangle 255"):
        encode(model)
    model.face_texture_triangles[face] = 0
    model.texture_triangles.append(model.texture_triangles[0])
    with pytest.raises(InvalidModelError, match="over 255"):
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


def _hand_built(priority=lambda i: 7, alpha=lambda i: 0, render_type=lambda i: 0):
    model = decode((FIXTURES / "28634.dat").read_bytes(), profile="osrs-149")
    assert model.new_data is not None
    faces = range(len(model.faces))
    return replace(
        model,
        render_priorities=[priority(i) for i in faces],
        face_alphas=[alpha(i) for i in faces],
        flat_shaded=[render_type(i) in (1, 3) for i in faces],
        new_data=replace(model.new_data, section_flags=None, face_render_types=tuple(render_type(i) for i in faces)),
    )


def _round_trip(model):
    """Encode a hand-built model, check that it decodes to itself, and return the bytes and the footer flags."""
    data = encode(model)
    again = decode(data, profile="osrs-149")
    assert again.new_data is not None
    assert replace(again, new_data=replace(again.new_data, section_flags=None)) == model
    assert again.new_data.section_flags is not None
    return data, again.new_data.section_flags


def test_hand_built_faces_with_one_priority_store_it_once_in_the_footer():
    # Client rev 149, class dv, method j, offsets 2235 to 2240 and 965 to 969: a footer priority byte of 255 means
    # that one priority byte follows for every face, and any other value is the one priority of all faces.
    # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 1.
    shared_data, (_, priority, *_) = _round_trip(_hand_built(priority=lambda i: 7))
    assert priority == 7
    mixed = _hand_built(priority=lambda i: 7 if i else 8)
    mixed_data, (_, mixed_priority, *_) = _round_trip(mixed)
    assert mixed_priority == 255
    assert len(mixed_data) == len(shared_data) + len(mixed.faces)
    all_255 = _hand_built(priority=lambda i: 255)
    all_255_data, (_, all_255_priority, *_) = _round_trip(all_255)
    assert all_255_priority == 255
    assert len(all_255_data) == len(shared_data) + len(all_255.faces)


def test_hand_built_model_without_faces_stores_priority_zero():
    # Client rev 149, class dv, method j, offsets 2235 to 2240 and 965 to 969: a footer priority byte of 255 means
    # that one priority byte follows for every face, and any other value is the one priority of all faces.
    # The client has no case for a model with no faces, so writing 0 there is our choice.
    # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 1.
    empty = Model(
        vertices=[(0, 0, 0), (1, 2, 3)],
        encoding=ModelEncoding.OSRS_FFFF,
        profile="osrs-149",
        new_data=NewFormatData(
            textured_face_colours=(), face_render_types=(), texture_render_types=(), texture_parameters=(), tail=b"\0"
        ),
    )
    _, (_, priority, *_) = _round_trip(empty)
    assert priority == 0


def test_hand_built_model_leaves_out_all_zero_render_type_and_alpha_sections():
    # Client rev 149, class dv, method ae, offsets 563 to 570, 1192 to 1199, 1488 to 1491 and 1706 to 1709: a missing
    # render type or alpha array reads as 0. Class dv, method j, offsets 1516 to 1522 and 1559 to 1562: each of those
    # sections is read only when its footer flag is 1.
    # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 2.
    plain_data, (render, _, alpha, *_) = _round_trip(_hand_built())
    assert (render, alpha) == (0, 0)
    alpha_model = _hand_built(alpha=lambda i: 9 if i == 0 else 0)
    alpha_data, (render, _, alpha, *_) = _round_trip(alpha_model)
    assert (render, alpha) == (0, 1)
    assert len(alpha_data) == len(plain_data) + len(alpha_model.faces)
    render_model = _hand_built(render_type=lambda i: 2 if i == 0 else 0)
    render_data, (render, _, alpha, *_) = _round_trip(render_model)
    assert (render, alpha) == (1, 0)
    assert len(render_data) == len(plain_data) + len(render_model.faces)


@pytest.mark.parametrize(
    ("tail", "accepted"),
    [
        (b"\x01" + bytes(9), False),
        (b"\x01" + bytes(10), True),
        (b"\x00", True),
        (b"\x00\x00\x00", True),
    ],
    ids=["nonzero-10-bytes", "nonzero-11-bytes", "zero-1-byte", "zero-3-bytes"],
)
def test_opaque_tail_with_a_nonzero_first_byte_needs_11_bytes(tail, accepted):
    # Client rev 149, class dv, method j, offsets 2689 to 2694, 1901 to 1903, 2709 to 2725, 2423 to 2431, 2740 to 2748
    # and 172 to 180: when the first tail byte is nonzero, the client reads 11 bytes (1, 2, 2, 2 and 4) and ignores
    # them. It checks no length, so a shorter tail makes it read the footer. The 11 is the client's number, and
    # refusing a shorter tail is our own stricter rule. The owner decided on 2026-11-11 to keep it (issue 17).
    # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 4.
    original = (FIXTURES / "28634.dat").read_bytes()
    model = decode(original, profile="osrs-149")
    assert model.new_data is not None
    footer_at = len(original) - 23
    data = original[: footer_at - len(model.new_data.tail)] + tail + original[footer_at:]
    model.new_data = replace(model.new_data, tail=tail)
    if accepted:
        for bytes_in in (data, encode(model)):
            decoded = decode(bytes_in, profile="osrs-149")
            assert decoded.new_data is not None
            assert decoded.new_data.tail == tail
    else:
        with pytest.raises(InvalidModelError, match="tail"):
            decode(data, profile="osrs-149")
        with pytest.raises(InvalidModelError, match="tail"):
            encode(model)


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
