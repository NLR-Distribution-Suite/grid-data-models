"""Station power-transformer equipment definitions."""

import re

from pydantic import model_validator

from gdm.systems.distribution.equipment.distribution_transformer_equipment import (
    DistributionTransformerEquipment,
)
from gdm.systems.distribution.enums import ConnectionType

_VECTOR_GROUP_TOKEN = re.compile(r"([YyDdZz])([Nn]?)(\d{0,2})")
_CONNECTION_SYMBOLS = {
    ConnectionType.STAR: "Y",
    ConnectionType.OPEN_STAR: "Y",
    ConnectionType.DELTA: "D",
    ConnectionType.OPEN_DELTA: "D",
    ConnectionType.ZIG_ZAG: "Z",
}


class PowerTransformerEquipment(DistributionTransformerEquipment):
    """Reusable electrical and nameplate data for a station transformer."""

    vector_group: str | None = None
    cooling_class: str | None = None
    fluid_type: str | None = None

    @model_validator(mode="after")
    def validate_vector_group_connections(self) -> "PowerTransformerEquipment":
        """Check that vector-group winding symbols match winding connection types."""
        if self.vector_group is None:
            return self

        tokens = []
        position = 0
        while position < len(self.vector_group):
            match = _VECTOR_GROUP_TOKEN.match(self.vector_group, position)
            if match is None:
                raise ValueError(f"Invalid transformer vector group {self.vector_group!r}.")
            tokens.append(match)
            position = match.end()

        if (
            len(tokens) < 2
            or tokens[0].group(3)
            or any(not token.group(3) for token in tokens[1:])
        ):
            raise ValueError(
                "Vector group must specify a connection for each winding and a clock "
                "number for each secondary winding."
            )
        if len(tokens) != len(self.windings):
            raise ValueError(
                f"Vector group {self.vector_group!r} specifies {len(tokens)} windings, "
                f"but the equipment defines {len(self.windings)} windings."
            )

        for index, (token, winding) in enumerate(zip(tokens, self.windings, strict=True), 1):
            expected_symbol = _CONNECTION_SYMBOLS[winding.connection_type]
            if token.group(1).upper() != expected_symbol:
                raise ValueError(
                    f"Vector group {self.vector_group!r} specifies winding {index} as "
                    f"{token.group(1)!r}, but its connection type is "
                    f"{winding.connection_type.value!r}."
                )
        return self

    @classmethod
    def example(cls) -> "PowerTransformerEquipment":
        equipment = DistributionTransformerEquipment.example()
        windings = [
            equipment.windings[0].model_copy(update={"connection_type": ConnectionType.DELTA}),
            *equipment.windings[1:],
        ]
        return cls(
            **equipment.model_dump(exclude_none=True, exclude={"windings"}),
            windings=windings,
            vector_group="Dyn1",
            cooling_class="ONAN",
            fluid_type="mineral_oil",
        )
