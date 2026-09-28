"""Station power-transformer equipment definitions."""

from gdm.systems.distribution.equipment.distribution_transformer_equipment import (
    DistributionTransformerEquipment,
)


class PowerTransformerEquipment(DistributionTransformerEquipment):
    """Reusable electrical and nameplate data for a station transformer."""

    vector_group: str | None = None
    cooling_class: str | None = None
    fluid_type: str | None = None

    @classmethod
    def example(cls) -> "PowerTransformerEquipment":
        return cls(
            **DistributionTransformerEquipment.example().model_dump(exclude_none=True),
            vector_group="Dyn1",
            cooling_class="ONAN",
            fluid_type="mineral_oil",
        )
