import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from runelite_json import load_items, load_kits

from rsps_toolkit.animation.bundle import Frame, FrameMap
from rsps_toolkit.animation.clip import CacheClip, pose_vertices, read_sequence
from rsps_toolkit.animation.frames import decode_frame, decode_frame_map
from rsps_toolkit.animation.poses import evaluate_frame
from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import (
    assemble_body,
    assemble_slots,
    default_equipment,
    held_equipment,
    load_palette,
)
from rsps_toolkit.formats.js5 import Js5Store

APPEARANCE = Path(__file__).parents[1] / "fixtures/appearance"
CLIPS = Path(__file__).parents[1] / "fixtures/animation149"
# Player sequences 819 (walk), 808 (stand) and 824 (run), each exported by animation149/export_clip.py and recorded
# for both bodies, and sequence 1499 (a loop offset of 4 frames), recorded for the male body only.
CLIP_NAMES = ("walk", "idle", "run")
SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
BODIES = ("male", "female")
CASES = [(clip, body) for clip in CLIP_NAMES for body in BODIES] + [("loop", "male")]
# Three sequences picked with random.Random(149).sample from the 217 player clips that have a face alpha transform,
# exported the same way and recorded for both bodies, face alphas included.
ALPHA_CASES = [(f"alpha-{sequence}", body) for sequence in (1697, 1994, 3182) for body in BODIES]


def reference(clip: str, body: str) -> dict:
    return json.loads((CLIPS / clip / f"pose-{body}.json").read_text())


def manifest(clip: str) -> dict:
    return json.loads((CLIPS / clip / "manifest.json").read_text())


def load_model(model_id: int) -> Model:
    return decode((APPEARANCE / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def body(clip: str, kind: str) -> Model:
    kits = load_kits(APPEARANCE / "KitDefinitions.json")
    palette = load_palette(APPEARANCE / "revision149-palette.json")
    female = kind == "female"
    equipment = default_equipment(kits, female=female)
    expected = reference(clip, kind)
    assert equipment == expected["equipment"] and expected["female"] == female
    return assemble_body(equipment, kits, load_model, expected["colours"], palette, female=female)


def frames_of(clip: str) -> tuple[FrameMap, tuple[Frame, ...]]:
    entries = manifest(clip)["frames"]
    assert {entry["map"] for entry in entries} == {0}, "every clip here uses the player frame map 0"
    frame_map = decode_frame_map((CLIPS / clip / "maps/0.dat").read_bytes())
    frames = tuple(
        decode_frame((CLIPS / clip / f"frames/{e['group']}_{e['file']}.dat").read_bytes(), frame_map) for e in entries
    )
    return frame_map, frames


def axes(vertices) -> tuple[list[int], list[int], list[int]]:
    return [v[0] for v in vertices], [v[1] for v in vertices], [v[2] for v in vertices]


@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_the_rest_vertices_equal_the_clients(clip, kind):
    rest = reference(clip, kind)["rest"]
    assert axes(body(clip, kind).vertices) == (rest["e"], rest["l"], rest["s"])


@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_every_frame_poses_the_vertices_as_the_client_does(clip, kind):
    model = body(clip, kind)
    assert model.vertex_skins is not None
    frame_map, frames = frames_of(clip)
    expected = reference(clip, kind)["frames"]
    assert len(frames) == len(expected)
    for frame, client in zip(frames, expected, strict=True):
        vertices, _ = evaluate_frame(
            tuple(model.vertices),
            tuple(model.vertex_skins),
            tuple(model.face_alphas),
            tuple(model.face_skins) if model.face_skins is not None else None,
            frame,
            frame_map,
        )
        assert axes(vertices) == (client["e"], client["l"], client["s"])


@pytest.mark.parametrize(("clip", "kind"), ALPHA_CASES)
def test_alpha_clips_pose_vertices_and_face_alphas_as_the_client_does(clip, kind):
    model = body(clip, kind)
    assert model.vertex_skins is not None and model.face_skins is not None
    assert set(model.face_alphas) == {0}
    frame_map, frames = frames_of(clip)
    expected = reference(clip, kind)["frames"]
    for frame, client in zip(frames, expected, strict=True):
        vertices, alphas = evaluate_frame(
            tuple(model.vertices),
            tuple(model.vertex_skins),
            tuple(model.face_alphas),
            tuple(model.face_skins),
            frame,
            frame_map,
        )
        assert axes(vertices) == (client["e"], client["l"], client["s"])
        # The client keeps face alphas in a signed byte array, so 176 is recorded as -80.
        assert list(alphas) == ([alpha & 255 for alpha in client["o"]] if client["o"] else model.face_alphas)


@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_the_client_changes_no_face_alpha_in_these_clips(clip, kind):
    recorded = reference(clip, kind)
    assert recorded["rest"]["o"] is None
    assert all(frame["o"] is None for frame in recorded["frames"])


def posed_body(model, clip):
    assert model.vertex_skins is not None
    return pose_vertices(tuple(model.vertices), tuple(model.vertex_skins), clip)


@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_posing_from_the_clip_folder_equals_the_clients_frames(clip, kind):
    posed = posed_body(body(clip, kind), CLIPS / clip)
    assert [p.ticks for p in posed] == manifest(clip)["durations"]
    for p, expected in zip(posed, reference(clip, kind)["frames"], strict=True):
        assert axes(p.vertices) == (expected["e"], expected["l"], expected["s"])


@pytest.mark.skipif(not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder")
@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_posing_from_the_cache_equals_the_clients_frames(clip, kind):
    posed = posed_body(body(clip, kind), CacheClip(Js5Store(SNAPSHOT_430), manifest(clip)["sequence"]))
    for p, expected in zip(posed, reference(clip, kind)["frames"], strict=True):
        assert axes(p.vertices) == (expected["e"], expected["l"], expected["s"])


def test_a_clip_folder_with_a_missing_file_is_named(tmp_path):
    with pytest.raises(FileNotFoundError, match="sequence.dat"):
        posed_body(body("walk", "male"), tmp_path)


@pytest.mark.parametrize(("clip", "kind"), CASES)
def test_each_recording_was_made_from_the_clip_files_beside_it(clip, kind):
    recorded = reference(clip, kind)["clip_manifest_sha256"]
    assert recorded == hashlib.sha256((CLIPS / clip / "manifest.json").read_bytes()).hexdigest()


@pytest.mark.parametrize("kind", BODIES)
def test_pose_vertices_returns_the_clients_face_alphas_when_given_face_labels(kind):
    model = body("alpha-1994", kind)
    assert model.vertex_skins is not None and model.face_skins is not None
    posed = pose_vertices(
        tuple(model.vertices),
        tuple(model.vertex_skins),
        CLIPS / "alpha-1994",
        tuple(model.face_skins),
        tuple(model.face_alphas),
    )
    for frame, client in zip(posed, reference("alpha-1994", kind)["frames"], strict=True):
        assert list(frame.alphas or ()) == ([a & 255 for a in client["o"]] if client["o"] else model.face_alphas)
    assert posed_body(model, CLIPS / "alpha-1994")[0].alphas is None


# Sequences that set held items, recorded with a worn Rune scimitar (1333) and Rune kiteshield (1201): 717 empties both
# hands, 1365 holds the Steel axe in the shield hand and empties the weapon hand, 909 holds Charcoal and Papyrus.
HELD_CLIPS = ("held-717", "held-1365", "held-909")


def worn(clip: str) -> tuple[list[int], Callable[[list[int]], tuple[Model, dict[int, range]]]]:
    kits = load_kits(APPEARANCE / "KitDefinitions.json")
    palette = load_palette(APPEARANCE / "revision149-palette.json")
    items = load_items(CLIPS / clip / "ItemDefinitions.json")
    expected = reference(clip, "male")

    def load(model_id: int) -> Model:
        path = CLIPS / clip / f"models/{model_id}.dat"
        return decode(path.read_bytes(), profile="osrs-149") if path.exists() else load_model(model_id)

    def assemble(equipment: list[int]) -> tuple[Model, dict[int, range]]:
        return assemble_slots(equipment, kits, load, expected["colours"], palette, items)

    return expected["equipment"], assemble


@pytest.mark.parametrize("clip", HELD_CLIPS)
def test_the_worn_weapon_and_shield_rest_as_the_client_builds_them(clip):
    equipment, assemble = worn(clip)
    model, _ = assemble(equipment)
    rest = reference(clip, "male")["rest"]
    assert axes(model.vertices) == (rest["e"], rest["l"], rest["s"])


@pytest.mark.parametrize("clip", HELD_CLIPS)
def test_a_clips_held_items_replace_the_worn_weapon_and_shield_on_every_frame(clip):
    equipment, assemble = worn(clip)
    sequence = read_sequence(CLIPS / clip)
    model, _ = assemble(held_equipment(equipment, sequence.left_hand_item, sequence.right_hand_item))
    assert model.vertex_skins is not None
    frame_map, frames = frames_of(clip)
    for frame, client in zip(frames, reference(clip, "male")["frames"], strict=True):
        assert len(model.faces) == client["face_count"]
        vertices, _ = evaluate_frame(
            tuple(model.vertices),
            tuple(model.vertex_skins),
            tuple(model.face_alphas),
            tuple(model.face_skins) if model.face_skins is not None else None,
            frame,
            frame_map,
        )
        assert axes(vertices) == (client["e"], client["l"], client["s"])


def test_held_equipment_puts_the_shield_hand_in_slot_5_and_the_weapon_hand_in_slot_3():
    worn_items = [0, 0, 0, 1845, 274, 1713, 282, 292, 256, 289, 298, 266]
    assert held_equipment(worn_items, 1865, 0) == [0, 0, 0, 0, 274, 1865, 282, 292, 256, 289, 298, 266]
    assert held_equipment(worn_items, -1, 1464)[3:6] == [1464, 274, 1713]
    assert held_equipment(worn_items, -1, -1) == worn_items


def test_each_slot_owns_its_faces_of_the_merged_model():
    equipment, assemble = worn("held-1365")
    model, faces = assemble(equipment)
    assert sorted(faces) == [slot for slot, value in enumerate(equipment) if value]
    assert [faces[slot] for slot in sorted(faces)][0].start == 0
    assert sum(len(r) for r in faces.values()) == len(model.faces)
    held, held_faces = assemble(held_equipment(equipment, 1865, 0))
    assert 3 not in held_faces
    assert len(held_faces[5]) == 40 == len(held.faces) - 476
