from types import SimpleNamespace

from rsps_toolkit.blender import preferences


def test_changing_brightness_asks_every_3d_view_in_every_window_to_redraw():
    # Stand-in windows record the redraw requests, since headless Blender has no windows (issue 16, decision 1,
    # 2026-11-10).
    redrawn = []

    def area(kind, name):
        return SimpleNamespace(type=kind, tag_redraw=lambda: redrawn.append(name))

    windows = [
        SimpleNamespace(screen=SimpleNamespace(areas=[area("VIEW_3D", "main view"), area("PROPERTIES", "properties")])),
        SimpleNamespace(
            screen=SimpleNamespace(areas=[area("PREFERENCES", "preferences"), area("VIEW_3D", "side view")])
        ),
    ]
    update = preferences.RsToolkitPreferences.__annotations__["brightness"].keywords["update"]
    update(None, SimpleNamespace(window_manager=SimpleNamespace(windows=windows)))
    assert redrawn == ["main view", "side view"]
