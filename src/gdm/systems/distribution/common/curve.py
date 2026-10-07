"""This module contains curve interface."""

from typing import Annotated

from pydantic import model_validator, Field
from infrasys import Component
from infrasys.quantities import Time, Current
from infrasys.base_quantity import BaseQuantity
from gdm.constants import PINT_SCHEMA


class Curve(Component):
    """An interface for representing a curve using x and y points. e.g for volt-var and volt-watt curves.

    Examples
    --------

    Example of a Curve (Volt-Var IEEE-1547 standard).

    >>> Curve(
            curve_x=[0.5, 0.92, 0.98, 1.02, 1.08, 1.5], curve_y=[1.0, 1.0, 0.0, 0.0, -1.0, -1.0]
        )

    Example of a Curve (Volt-Var Volt-Watt IEEE-1547 standard)

    >>> Curve(curve_x=[0.5, 1.06, 1.1, 1.5], curve_y=[1.0, 1.0, 0.0, 0.0])
    """

    name: Annotated[str, Field("", description="Name of the curve.")]
    curve_x: Annotated[
        list[float] | BaseQuantity, Field(..., description="The x values of the curve")
    ]

    curve_y: Annotated[
        list[float] | BaseQuantity, Field(..., description="The y values of the curve")
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "Curve":
        if len(self.curve_x) != len(self.curve_y):
            msg = f"curve_x ({self.curve_x=}) and curve_y ({self.curve_y=}) have different lengths"
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "Curve":
        """Example of a Curve (Volt-Var IEEE-1547 standard)."""
        return Curve(
            curve_x=[0.5, 0.92, 0.98, 1.02, 1.08, 1.5], curve_y=[1.0, 1.0, 0.0, 0.0, -1.0, -1.0]
        )


class TimeCurrentCurve(Component):
    """An interface for time current curve."""

    name: Annotated[str, Field("", description="Name of the curve.")]
    curve_x: Annotated[Current, PINT_SCHEMA, Field(..., description="Array of time values.")]
    curve_y: Annotated[Time, PINT_SCHEMA, Field(..., description="Array of current values.")]

    @model_validator(mode="after")
    def validate_fields(self) -> "Curve":
        if len(self.curve_x) != len(self.curve_y):
            msg = f"curve_x ({self.curve_x=}) and curve_y ({self.curve_y=}) have different lengths"
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "TimeCurrentCurve":
        """Example time current curve."""
        return TimeCurrentCurve(
            curve_x=Current([100, 200, 300, 400, 500, 600, 800, 1000, 2000, 5000], "ampere"),
            curve_y=Time([2.5, 0.6, 0.3, 0.2, 0.15, 0.1, 0.06, 0.04, 0.018, 0.012], "second"),
        )
