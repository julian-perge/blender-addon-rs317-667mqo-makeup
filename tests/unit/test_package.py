import importlib


def test_package_imports_without_bpy():
    importlib.import_module("rsps_toolkit")
