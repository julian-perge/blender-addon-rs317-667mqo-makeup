import importlib
import sys


def _blender_layer():
    # This package must import without bpy so that plain pytest can test the pure modules,
    # so the Blender layer is only imported here. Blender's Reload Scripts re-runs this file
    # but keeps submodules cached, so they are dropped first to make it load the edited code.
    for name in [n for n in sys.modules if n.startswith(f"{__package__}.")]:
        del sys.modules[name]
    return importlib.import_module(f"{__package__}.blender")


_registered = None


def register():
    global _registered
    _registered = _blender_layer()
    _registered.register()


def unregister():
    global _registered
    if _registered is not None:
        _registered.unregister()
        _registered = None
