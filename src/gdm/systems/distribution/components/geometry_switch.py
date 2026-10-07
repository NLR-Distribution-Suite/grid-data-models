"""This module contains geometry branch."""

from typing import Annotated

from pydantic import Field

from gdm.systems.distribution.components.base.distribution_switch_base import (
    DistributionSwitchBase,
)
from gdm.systems.distribution.equipment.geometry_branch_equipment import (
    GeometryBranchEquipment,
)
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import (
    DistributionSubstation,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import Phase
from gdm.quantities import Voltage, Distance

from gdm.systems.distribution.components.matrix_impedance_switch import MatrixImpedanceSwitch
from gdm.systems.distribution.equipment import (
    ConcentricCableEquipment,
)
from gdm.systems.distribution.equipment.matrix_impedance_switch_equipment import (
    MatrixImpedanceSwitchEquipment,
)


class GeometrySwitch(DistributionSwitchBase):
    """Data model for distribution branches based on line geometry."""

    equipment: Annotated[
        GeometryBranchEquipment,
        Field(..., description="Geometry branch equipment."),
    ]

    def validate_fields(self) -> "GeometrySwitch":
        """Custom validator for geometry branch fields."""
        if len(self.phases) != len(self.equipment.conductors):
            msg = "Number of phases is not equal to number of wires."
            raise ValueError(msg)
        return self

    def to_matrix_representation(
        self, frequency_hz: float = 60, soil_resistivity_ohm_m: float = 100
    ) -> MatrixImpedanceSwitch:
        """
        Converts the geometry-based branch model to a matrix impedance representation.

        This method transforms the current `GeometryBranch` instance into a `MatrixImpedanceBranch`
        by calculating the impedance matrix based on the specified frequency and soil resistivity.
        The conversion process involves using the equipment's matrix representation method to obtain
        the necessary impedance data.

        Parameters
        ----------
        frequency_hz : float, optional
            The frequency in hertz used for impedance calculations. Defaults to 60 Hz.
        soil_resistivity_ohm_m : float, optional
            The soil resistivity in ohm-meters used for impedance calculations. Defaults to 100 ohm-m.

        Returns
        -------
        MatrixImpedanceBranch
            A new instance of `MatrixImpedanceBranch` representing the converted geometry branch.

        Notes
        -----
        - The method uses the number of neutral phases to assist in the impedance calculation.
        - This conversion is essential for systems that require matrix impedance representations
            for detailed electrical analysis.

        """
        equipment = self.equipment.to_matrix_representation(
            frequency_hz,
            soil_resistivity_ohm_m,
            n_neutrals=len([phs for phs in self.phases if phs == Phase.N]),
        )
        if isinstance(self.equipment.conductors[0], ConcentricCableEquipment):
            phases = self.phases + [Phase.N for _ in self.phases]
            equipment.kron_reduce(phases)

        switch_equipment = MatrixImpedanceSwitchEquipment(
            **equipment.model_dump(exclude_none=True)
        )

        return MatrixImpedanceSwitch(
            buses=self.buses,
            length=self.length,
            phases=self.phases,
            substation=self.substation,
            feeder=self.feeder,
            name=self.name,
            equipment=switch_equipment,
            is_closed=self.is_closed,
        )

    @classmethod
    def example(cls) -> "GeometrySwitch":
        """Example for geometry branch."""
        buses = [
            DistributionBus(
                voltage_type="line-to-ground",
                phases=[Phase.A, Phase.B, Phase.C],
                rated_voltage=Voltage(400, "volt"),
                substation=DistributionSubstation.example(),
                feeder=DistributionFeeder.example(),
                name=bus_name,
            )
            for bus_name in ["Branch-DistBus1", "Branch-DistBus2"]
        ]
        return GeometrySwitch(
            buses=buses,
            length=Distance(130.2, "meter"),
            phases=[Phase.A, Phase.B, Phase.C],
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            name="DistBranch1",
            is_closed=[True, True, True],
            equipment=GeometryBranchEquipment.example(),
        )
