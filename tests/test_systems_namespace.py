import importlib
import warnings

from gdm.distribution import DistributionSystem as LegacyDistributionSystem
from gdm.distribution.components import DistributionBus as LegacyDistributionBus
from gdm.distribution.components.distribution_bus import (
    DistributionBus as LegacyDeepDistributionBus,
)
from gdm.distribution.model_reduction import (
    reduce_to_three_phase_system as legacy_reduce_to_three_phase_system,
)
from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components import DistributionBus
from gdm.systems.distribution.components.distribution_bus import (
    DistributionBus as DeepDistributionBus,
)
from gdm.systems.distribution.model_reduction import (
    reduce_to_three_phase_system,
)


def test_legacy_distribution_namespace_warns_on_import():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(importlib.import_module("gdm.distribution"))

    deprecation_warnings = [
        warning for warning in caught if warning.category is DeprecationWarning
    ]
    assert len(deprecation_warnings) == 1
    assert str(deprecation_warnings[0].message) == (
        "gdm.distribution is deprecated and will be removed in a future release; "
        "use gdm.systems.distribution instead."
    )


def test_legacy_distribution_namespace_aliases_canonical_namespace():
    assert LegacyDistributionSystem is DistributionSystem
    assert LegacyDistributionBus is DistributionBus
    assert LegacyDeepDistributionBus is DeepDistributionBus
    assert legacy_reduce_to_three_phase_system is reduce_to_three_phase_system
