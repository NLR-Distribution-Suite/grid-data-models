"""Compatibility namespace for the former ``gdm.distribution`` package.

The implementation now lives under :mod:`gdm.systems.distribution`. Legacy imports and
serialized component module paths are mapped to the canonical modules so
classes are not duplicated during a migration.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import warnings


_CANONICAL_PACKAGE = "gdm.systems.distribution"
warnings.warn(
    "gdm.distribution is deprecated and will be removed in a future release; "
    "use gdm.systems.distribution instead.",
    DeprecationWarning,
    stacklevel=2,
)
_canonical_package = importlib.import_module(_CANONICAL_PACKAGE)

for name, value in vars(_canonical_package).items():
    if not name.startswith("__") or name in {"__version__"}:
        globals()[name] = value

_module_names = [
    module_info.name
    for module_info in pkgutil.walk_packages(
        _canonical_package.__path__, prefix=f"{_CANONICAL_PACKAGE}."
    )
]

for canonical_name in sorted(_module_names, key=lambda name: (name.count("."), name)):
    legacy_name = f"{__name__}{canonical_name[len(_CANONICAL_PACKAGE) :]}"
    module = importlib.import_module(canonical_name)
    sys.modules[legacy_name] = module

    parent_name, child_name = legacy_name.rsplit(".", 1)
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, child_name, module)
