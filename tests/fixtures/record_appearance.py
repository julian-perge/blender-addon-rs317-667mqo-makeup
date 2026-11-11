#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Record the unchanged revision-149 appearance pipeline with a read-only JVMTI observer."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

CLIENT_HASH = "19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd"
OBSERVER = r"""
#include <jni.h>
#include <jvmti.h>
#include <string.h>
#include <stdlib.h>

static jclass harness;
static jmethodID capture;
static jmethodID capture_merge;

static void JNICALL started(jvmtiEnv *ti, JNIEnv *env, jthread thread) {
    jclass local = (*env)->FindClass(env, "AppearanceReference");
    if (local == NULL) { (*env)->ExceptionDescribe(env); abort(); }
    harness = (*env)->NewGlobalRef(env, local);
    capture = (*env)->GetStaticMethodID(env, harness, "capture", "(Ljava/lang/Object;)V");
    capture_merge = (*env)->GetStaticMethodID(env, harness, "captureMerge", "(I)V");
    if (capture_merge == NULL) abort();
    if (capture == NULL) { (*env)->ExceptionDescribe(env); abort(); }
    (*ti)->SetEventNotificationMode(ti, JVMTI_ENABLE, JVMTI_EVENT_METHOD_ENTRY, NULL);
}

static void JNICALL entered(jvmtiEnv *ti, JNIEnv *env, jthread thread, jmethodID method) {
    char *name = NULL, *signature = NULL, *owner = NULL;
    jclass type;
    (*ti)->GetMethodName(ti, method, &name, &signature, NULL);
    if (strcmp(name, "ae") == 0 && strcmp(signature, "(IIIII)Lej;") == 0) {
        (*ti)->GetMethodDeclaringClass(ti, method, &type);
        (*ti)->GetClassSignature(ti, type, &owner, NULL);
        if (strcmp(owner, "Ldv;") == 0) {
            jint argument;
            const jint lighting[] = {64, 850, -30, -50, -30};
            for (int slot = 1; slot <= 5; slot++) {
                if ((*ti)->GetLocalInt(ti, thread, 0, slot, &argument) != JVMTI_ERROR_NONE
                    || argument != lighting[slot - 1]) abort();
            }
            jobject model;
            if ((*ti)->GetLocalObject(ti, thread, 0, 0, &model) != JVMTI_ERROR_NONE) abort();
            (*ti)->SetEventNotificationMode(ti, JVMTI_DISABLE, JVMTI_EVENT_METHOD_ENTRY, thread);
            (*env)->CallStaticVoidMethod(env, harness, capture, model);
            if ((*env)->ExceptionCheck(env)) { (*env)->ExceptionDescribe(env); abort(); }
            (*ti)->SetEventNotificationMode(ti, JVMTI_ENABLE, JVMTI_EVENT_METHOD_ENTRY, thread);
        }
        (*ti)->Deallocate(ti, (unsigned char *)owner);
    }
    if (strcmp(name, "<init>") == 0 && strcmp(signature, "([Ldv;I)V") == 0) {
        jmethodID caller;
        jlocation location;
        if ((*ti)->GetFrameLocation(ti, thread, 1, &caller, &location) == JVMTI_ERROR_NONE) {
            char *caller_name = NULL, *caller_owner = NULL;
            jclass caller_type;
            (*ti)->GetMethodName(ti, caller, &caller_name, NULL, NULL);
            (*ti)->GetMethodDeclaringClass(ti, caller, &caller_type);
            (*ti)->GetClassSignature(ti, caller_type, &caller_owner, NULL);
            if (strcmp(caller_name, "k") == 0 && strcmp(caller_owner, "Liz;") == 0) {
                jint count;
                if ((*ti)->GetLocalInt(ti, thread, 0, 2, &count) != JVMTI_ERROR_NONE) abort();
                (*ti)->SetEventNotificationMode(ti, JVMTI_DISABLE, JVMTI_EVENT_METHOD_ENTRY, thread);
                (*env)->CallStaticVoidMethod(env, harness, capture_merge, count);
                if ((*env)->ExceptionCheck(env)) { (*env)->ExceptionDescribe(env); abort(); }
                (*ti)->SetEventNotificationMode(ti, JVMTI_ENABLE, JVMTI_EVENT_METHOD_ENTRY, thread);
            }
            (*ti)->Deallocate(ti, (unsigned char *)caller_name);
            (*ti)->Deallocate(ti, (unsigned char *)caller_owner);
        }
    }
    (*ti)->Deallocate(ti, (unsigned char *)name);
    (*ti)->Deallocate(ti, (unsigned char *)signature);
}

JNIEXPORT jint JNICALL Agent_OnLoad(JavaVM *vm, char *options, void *reserved) {
    jvmtiEnv *ti;
    if ((*vm)->GetEnv(vm, (void **)&ti, JVMTI_VERSION_1_2) != JNI_OK) return JNI_ERR;
    jvmtiCapabilities capabilities = {0};
    capabilities.can_generate_method_entry_events = 1;
    capabilities.can_access_local_variables = 1;
    jvmtiEventCallbacks callbacks = {0};
    callbacks.MethodEntry = entered;
    callbacks.VMInit = started;
    if ((*ti)->AddCapabilities(ti, &capabilities) != JVMTI_ERROR_NONE) return JNI_ERR;
    if ((*ti)->SetEventCallbacks(ti, &callbacks, sizeof(callbacks)) != JVMTI_ERROR_NONE) return JNI_ERR;
    return (*ti)->SetEventNotificationMode(ti, JVMTI_ENABLE, JVMTI_EVENT_VM_INIT, NULL) == JVMTI_ERROR_NONE
        ? JNI_OK : JNI_ERR;
}
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> None:
    subprocess.run(args, check=True, timeout=120)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--kits", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "appearance")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if digest(args.client) != CLIENT_HASH:
        raise ValueError("Unrecognized revision-149 client")
    if args.output.exists():
        raise ValueError("Output must be a new file")
    source = Path(__file__).with_name("AppearanceReference.java")
    java_home = os.environ.get("JAVA_HOME") or subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="appearance149-") as temporary:
        work = Path(temporary)
        observer = work / "observer.c"
        observer.write_text(OBSERVER)
        agent = work / "observer.dylib"
        run(
            "cc",
            "-dynamiclib",
            "-Wall",
            "-Werror",
            f"-I{java_home}/include",
            f"-I{java_home}/include/darwin",
            str(observer),
            "-o",
            str(agent),
        )
        run(f"{java_home}/bin/javac", "-d", str(work), str(source))
        run(
            f"{java_home}/bin/java",
            f"-agentpath:{agent}",
            "-Djava.awt.headless=true",
            "-cp",
            str(work),
            "AppearanceReference",
            "worker",
            str(args.client.resolve()),
            str(args.input.resolve()),
            str(args.kits.resolve()),
            str(work),
        )
        raw = json.loads((work / "raw.json").read_text())
        lit = json.loads((work / "lit.json").read_text())
        palette = json.loads((work / "palette.json").read_text())
        decoded_kits = json.loads((work / "kits.json").read_text())
        items = json.loads((work / "items.json").read_text())
        settings = json.loads((work / "settings.json").read_text())
        defaults = json.loads((work / "defaults.json").read_text())
        catalog = json.loads((args.input / "KitDefinitions.json").read_text())
        if len(catalog) != 151 or len(decoded_kits) != 151:
            raise ValueError("Expected 151 kits")
        for kit_id, (row, client) in enumerate(zip(catalog, decoded_kits, strict=True)):
            if row["id"] != kit_id:
                raise ValueError("Kit catalog must be ordered by ID")
            expected = {
                "v": (row["bodyPartId"] * -1924753457) & 0xFFFFFFFF,
                "e": row.get("models"),
                "m": row["chatheadModels"],
                "u": row["nonSelectable"],
                "l": row.get("recolorToFind"),
                "s": row.get("recolorToReplace"),
                "w": row.get("retextureToFind"),
                "p": row.get("retextureToReplace"),
            }
            client["v"] &= 0xFFFFFFFF
            if client != expected:
                raise ValueError(f"Kit {row['id']} differs: {client} != {expected}")
        tables = json.loads((args.input / "revision149-palette.json").read_text())["tables"]
        for field, name in [
            ("a", "primary_sources"),
            ("j", "primary_choices"),
            ("n", "secondary_sources"),
            ("r", "secondary_choices"),
        ]:
            if palette[field] != tables[name]["signed_short"]:
                raise ValueError(f"Client palette differs: {name}")
        cases = []
        for setting, before, after in zip(settings, raw, lit, strict=True):
            female, colours = setting["female"], setting["colours"]
            vertices, faces = before["a"], before["v"]
            if before["c"] != 0 or before["k"] is not None or before["u"] is not None:
                raise ValueError("This reference closure must be untextured")
            assembled = {
                "vertex_count": vertices,
                "face_count": faces,
                "vertices": [
                    list(v)
                    for v in zip(before["j"][:vertices], before["n"][:vertices], before["r"][:vertices], strict=True)
                ],
                "faces": [list(f) for f in zip(before["e"], before["l"], before["s"], strict=True)],
                "face_colours": [v & 65535 for v in before["g"]],
                "face_alphas": [v & 255 for v in before["m"]] if before["m"] is not None else [0] * faces,
                "render_priorities": [v & 255 for v in before["p"]]
                if before["p"] is not None
                else [before["t"] & 255] * faces,
                "face_skins": before["au"],
                "vertex_skins": before["ae"][:vertices] if before["ae"] is not None else None,
                "face_textures": [None] * faces,
                "face_texture_triangles": [None] * faces,
                "texture_triangles": [],
                "flat_shaded": [v == 1 for v in before["w"]] if before["w"] is not None else [False] * faces,
            }
            if after["v"] != vertices or after["w"] != faces:
                raise ValueError("Lighting changed the model counts")
            cases.append(
                {
                    "colours": colours,
                    "female": female,
                    "before_lighting": assembled,
                    "client_raw": before,
                    "lit": {
                        "vertex_count": after["v"],
                        "face_count": after["w"],
                        "hidden_faces": sum(v == -2 for v in after["t"]),
                        "shade_a": after["g"],
                        "shade_b": after["k"],
                        "shade_c": after["t"],
                    },
                    "client_lit": after,
                }
            )
            cases[-1]["equipment"] = setting["equipment"]
            if "outfit" in setting:
                cases[-1]["outfit"] = setting["outfit"]
        inputs = {path.name: digest(path) for path in sorted(args.input.glob("*.dat"))}
        inputs.update({f"items/{path.name}": digest(path) for path in sorted((args.input / "items").glob("*.dat"))})
        for name in ["KitDefinitions.json", "revision149-palette.json"]:
            inputs[name] = digest(args.input / name)
        result = {
            "schema_version": 1,
            "client_revision": 149,
            "snapshot_id": 430,
            "client_sha256": CLIENT_HASH,
            "harness_sha256": digest(source),
            "runner_sha256": digest(Path(__file__)),
            "inputs_sha256": inputs,
            "raw_kits_sha256": {f"{i}.dat": digest(args.kits / f"{i}.dat") for i in range(151)},
            "equipment": [0, 0, 0, 0, 274, 0, 282, 292, 256, 289, 298, 266],
            "female_equipment": [0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0],
            "client_default_equipment": defaults,
            "lighting": [64, 850, -30, -50, -30],
            "cases": cases,
            "items": items,
        }
        args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
        for body_type, key in [("male", "equipment"), ("female", "female_equipment")]:
            status = "matches" if defaults[body_type] == result[key] else f"MISMATCH: supplied {result[key]}"
            print(f"Client default {body_type}: {defaults[body_type]} ({status})")
        print(f"Recorded {len(cases)} colour sets through the unchanged revision-149 client")


if __name__ == "__main__":
    main()
