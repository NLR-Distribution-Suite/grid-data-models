"""This module contains interface for distribution transformer."""

import math
from typing import Annotated
from abc import ABC

from infrasys.quantities import Voltage
from pydantic import Field, model_validator

from gdm.distribution.enums import Phase, VoltageTypes
from gdm.distribution.components.distribution_bus import DistributionBus
from gdm.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.distribution.equipment.distribution_transformer_equipment import (
    DistributionTransformerEquipment,
)


def get_phase_voltage_in_kv(
    voltage: Voltage, voltage_type: VoltageTypes, split_phase_secondary: bool = False
) -> Voltage:
    """Function to return phase voltage"""
    kv_voltage = voltage.to("kilovolt")
    factor = math.sqrt(3) if not split_phase_secondary else 2
    return kv_voltage / factor if voltage_type == VoltageTypes.LINE_TO_LINE else kv_voltage


class DistributionTransformerBase(InServiceDistributionComponentBase, ABC):
    """Data model for distribution transformer."""

    buses: Annotated[
        list[DistributionBus],
        Field(
            ...,
            description="List of distribution buses in the same order as windings. ",
        ),
    ]
    winding_phases: Annotated[
        list[list[Phase]],
        Field(
            ...,
            description="""List of phases for each winding, using the winding
            order defined in the DistributionTransformerModel""",
        ),
    ]
    tap_positions: Annotated[
        list[list[float]] | None,
        Field(
            default=None,
            description="Current tap position (per-unit) for each phase in each winding, "
            "matching the order of winding_phases. Defaults to 1.0 for all phases.",
        ),
    ]

    equipment: Annotated[
        DistributionTransformerEquipment,
        Field(..., description="Transformer info object."),
    ]

    def _check_if_voltage_is_on_split_side(self, voltage: Voltage) -> bool:
        """Internal method to check if winding is on split side."""
        if not self.equipment.is_center_tapped:
            return False

        all_voltages = [item.rated_voltage for item in self.equipment.windings]
        return voltage < max(all_voltages)

    def _split_phase_validation(self):
        if self.equipment.is_center_tapped:
            if len(self.buses) != 3:
                raise ValueError("Center tapped transformer must have 3 buses.")
            if self.buses[1] != self.buses[2]:
                raise ValueError(
                    "Center tapped transformer must have same bus on the secondary side (bus 2 and 3)."
                )

    def _validate_tap_positions(self) -> None:
        """Validate and default tap_positions field."""
        if self.tap_positions is None:
            self.tap_positions = [[1.0] * len(phases) for phases in self.winding_phases]

        if len(self.tap_positions) != len(self.winding_phases):
            msg = (
                f"Number of tap_positions entries {len(self.tap_positions)} must equal "
                f"number of windings {len(self.winding_phases)}"
            )
            raise ValueError(msg)

        for i, (taps, phases) in enumerate(zip(self.tap_positions, self.winding_phases)):
            if len(taps) != len(phases):
                msg = (
                    f"tap_positions[{i}] has {len(taps)} entries but "
                    f"winding_phases[{i}] has {len(phases)} phases"
                )
                raise ValueError(msg)

    @model_validator(mode="after")
    def validate_fields_base(self) -> "DistributionTransformerBase":
        """Custom validator for distribution transformer."""
        if len(self.winding_phases) != len(self.equipment.windings):
            msg = (
                f"Number of windings {len(self.equipment.windings)} must be equal to "
                f"number of winding phases {len(self.winding_phases)}"
            )
            raise ValueError(msg)

        self._validate_tap_positions()

        for wdg, pw_phases in zip(self.equipment.windings, self.winding_phases):
            pw_phases_length = len(pw_phases) - 1 if Phase.N in pw_phases else len(pw_phases)

            if pw_phases_length > wdg.num_phases and pw_phases_length != 2:
                msg = (
                    f"More phases {pw_phases=} specified in winding phases for the winding {wdg=}"
                    f" which is allowed only for delta connected configuration i.e. phase length =2."
                )
                raise ValueError(msg)
            elif pw_phases_length == 2 and wdg.num_phases != 1 and "DELTA" in wdg.connection_type:
                msg = (
                    f"For a single phase delta connected transformer, {pw_phases=}"
                    f" inconsistant number of phases provided for winding {wdg.num_phases=}"
                )
                raise ValueError(msg)

        for bus, pw_phases in zip(self.buses, self.winding_phases):
            if not (set(pw_phases) - set(Phase.N)).issubset(bus.phases):
                msg = f"Winding phases {pw_phases=} must be subset of bus phases ({bus.phases=})."
                raise ValueError(msg)

        for bus, wdg in zip(self.buses, self.equipment.windings):
            bus_phase_voltage = get_phase_voltage_in_kv(
                bus.rated_voltage,
                bus.voltage_type,
                split_phase_secondary=self._check_if_voltage_is_on_split_side(bus.rated_voltage),
            )
            wdg_phase_voltage = get_phase_voltage_in_kv(
                wdg.rated_voltage,
                wdg.voltage_type,
                split_phase_secondary=self._check_if_voltage_is_on_split_side(wdg.rated_voltage),
            )
            if not (0.85 * bus_phase_voltage <= wdg_phase_voltage <= 1.15 * bus_phase_voltage):
                msg = (
                    f"rated line to ground voltage of transformer {wdg_phase_voltage}"
                    f" must be within 15% range of"
                    f" bus rated line to ground voltage {bus_phase_voltage}"
                )
                raise ValueError(msg)

        self._split_phase_validation()

        return self
