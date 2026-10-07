"""This module contains all custom quantities for this package."""

# pylint:disable=unused-argument
# pylint:disable=super-init-not-called

from infrasys.base_quantity import BaseQuantity, ureg
from infrasys.quantities import Resistance, Current, Distance, Voltage, ActivePower  # noqa

ureg.define("var = ampere * volt")
ureg.define("va = ampere * volt")


class Weight(BaseQuantity):
    """Quantity representing weight."""

    __base_unit__ = "gram"


class ResistancePULength(BaseQuantity):
    """Quantity representing per unit length power system resistance."""

    __base_unit__ = "ohm/m"


class Angle(BaseQuantity):
    """Quantity representing angle."""

    __base_unit__ = "degree"


class Reactance(Resistance):
    """Quantity representing power system reactance."""


class ReactancePULength(BaseQuantity):
    """Quantity representing per unit length power system reactance."""

    __base_unit__ = "ohm/m"


class Capacitance(BaseQuantity):
    """Quantity representing power system capacitance."""

    __base_unit__ = "farad"


class CapacitancePULength(BaseQuantity):
    """Quantity representing per unit length power system capacitance."""

    __base_unit__ = "farad/m"


class ReactivePower(BaseQuantity):
    """Quantity representing reactive power."""

    __base_unit__ = "var"


class ApparentPower(BaseQuantity):
    """Quantity representing apparent power."""

    __base_unit__ = "va"


class ActivePowerOverTime(BaseQuantity):
    """Quantity representing active power per unit of time"""

    __base_unit__ = "watt/minute"


class EnergyDC(BaseQuantity):
    """Quantity representing DC energy of a storage device"""

    __base_unit__ = "kilowatt*hour"


class EnergyAC(BaseQuantity):
    """Quantity representing AC energy of a storage device"""

    __base_unit__ = "kilova*hour"


class Irradiance(BaseQuantity):
    """Quantity representing irradiance in kilowatt per meter**2"""

    __base_unit__ = "kilowatt/meter**2"


class Frequency(BaseQuantity):
    """Quantity representing frequency."""

    __base_unit__ = "hertz"
