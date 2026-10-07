"""This module contains matrix impedance branch equipment."""

import numpy as np

from gdm.systems.distribution.equipment.base.matrix_impedance_branch_equipment_base import (
    MatrixImpedanceBranchEquipmentBase,
)
from gdm.systems.distribution.enums import Phase
from gdm.quantities import (
    CapacitancePULength,
    ResistancePULength,
    ReactancePULength,
    Current,
)


class MatrixImpedanceBranchEquipment(MatrixImpedanceBranchEquipmentBase):
    @staticmethod
    def _reduce(h: np.ndarray, keep_idx: list[Phase], elim_idx: list[Phase]) -> np.ndarray:
        h_aa = h[np.ix_(keep_idx, keep_idx)]
        h_an = h[np.ix_(keep_idx, elim_idx)]
        h_na = h[np.ix_(elim_idx, keep_idx)]
        h_nn = h[np.ix_(elim_idx, elim_idx)]

        h_reduced = np.squeeze(h_aa - h_an @ np.linalg.inv(h_nn) @ h_na)

        if np.prod(h_reduced.shape) == 1:
            h_reduced = np.array([[h_reduced]])
        return h_reduced

    def kron_reduce(self, phases: list[Phase]) -> "MatrixImpedanceBranchEquipment":
        z = (self.r_matrix + 1j * self.x_matrix).magnitude

        keep = [p for p in phases if p != Phase.N]
        keep_idx = [phases.index(p) for p in keep]
        elim_idx = [i for i in range(len(phases)) if i not in keep_idx]

        z = self._reduce(z, keep_idx, elim_idx)
        c = self._reduce(self.c_matrix.magnitude, keep_idx, elim_idx)

        object.__setattr__(self, "r_matrix", ResistancePULength(np.real(z), self.r_matrix.units))
        object.__setattr__(self, "x_matrix", ReactancePULength(np.imag(z), self.x_matrix.units))
        object.__setattr__(self, "c_matrix", CapacitancePULength(c, self.c_matrix.units))

    @classmethod
    def example(cls) -> "MatrixImpedanceBranchEquipment":
        """Example for matrix impedance model."""
        return MatrixImpedanceBranchEquipment(
            name="matrix-impedance-branch-1",
            r_matrix=ResistancePULength(
                [
                    [0.08820, 0.0312137, 0.0306264],
                    [0.0312137, 0.0901946, 0.0316143],
                    [0.0306264, 0.0316143, 0.0889665],
                ],
                "ohm/mi",
            ),
            x_matrix=ReactancePULength(
                [
                    [0.20744, 0.0935314, 0.0760312],
                    [0.0935314, 0.200783, 0.0855879],
                    [0.0760312, 0.0855879, 0.204877],
                ],
                "ohm/mi",
            ),
            c_matrix=CapacitancePULength(
                [
                    [2.90301, -0.679335, -0.22313],
                    [-0.679335, 3.15896, -0.481416],
                    [-0.22313, -0.481416, 2.8965],
                ],
                "nanofarad/mi",
            ),
            ampacity=Current(90, "ampere"),
        )
