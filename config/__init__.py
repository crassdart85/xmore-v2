"""
config/__init__.py

The config/ package directory shadows the root config.py module.
This file loads root config.py explicitly via importlib and re-exports
all its public attributes so that `import config; config.ALL_STOCKS`
works identically whether Python resolves config as the package or the file.
"""
import os
import importlib.util
import sys

# Load root-level config.py by absolute path
_root_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
_spec = importlib.util.spec_from_file_location("_xmore_root_config", _root_config_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export every public name from root config.py into this package namespace
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)
