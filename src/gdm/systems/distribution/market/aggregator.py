"""Data models for resource aggregation in wholesale and demand response markets."""

from typing import Annotated, Optional

from pydantic import Field, model_validator
from infrasys import Component

from gdm.systems.distribution.components.distribution_battery import DistributionBattery
from gdm.systems.distribution.components.distribution_solar import DistributionSolar
from gdm.systems.distribution.components.distribution_load import DistributionLoad
from gdm.systems.distribution.enums import (
    AggregatorType,
    AncillaryServiceType,
    DemandResponseType,
)
from gdm.systems.distribution.market.tariff import DistributionTariff, WholesaleMarketTariff
from gdm.quantities import ActivePower


class AggregatedDER(Component):
    """A DER resource committed to an aggregation portfolio."""

    name: str = ""
    resource: Annotated[
        DistributionBattery | DistributionSolar,
        Field(..., description="The DER component being aggregated."),
    ]
    committed_capacity: Annotated[
        ActivePower,
        Field(
            ...,
            description="Active power capacity committed to the aggregation in kW.",
            ge=0,
        ),
    ]

    @classmethod
    def example(cls) -> "AggregatedDER":
        return AggregatedDER(
            resource=DistributionBattery.example(),
            committed_capacity=ActivePower(50, "kilowatt"),
        )


class AggregatedLoad(Component):
    """A load resource committed to demand response aggregation."""

    name: str = ""
    resource: Annotated[
        DistributionLoad,
        Field(..., description="The load component being aggregated."),
    ]
    curtailable_capacity: Annotated[
        ActivePower,
        Field(
            ...,
            description="Active power capacity available for curtailment in kW.",
            ge=0,
        ),
    ]
    response_type: Annotated[
        DemandResponseType,
        Field(..., description="Type of demand response program."),
    ]

    @classmethod
    def example(cls) -> "AggregatedLoad":
        return AggregatedLoad(
            resource=DistributionLoad.example(),
            curtailable_capacity=ActivePower(25, "kilowatt"),
            response_type=DemandResponseType.ECONOMIC,
        )


class DERAggregator(Component):
    """Aggregates distributed energy resources for wholesale market participation."""

    name: str = Field(..., description="Name of the DER aggregator")
    aggregator_type: AggregatorType = Field(
        default=AggregatorType.DER,
        description="Type of aggregator.",
    )
    resources: Annotated[
        list[AggregatedDER],
        Field(..., min_length=1, description="DER resources in the aggregation portfolio."),
    ]
    offered_services: Annotated[
        list[AncillaryServiceType],
        Field(
            default_factory=list,
            description="Ancillary services the aggregator can provide.",
        ),
    ]
    min_dispatch: Annotated[
        ActivePower,
        Field(
            ...,
            description="Minimum dispatchable capacity in kW.",
            ge=0,
        ),
    ]
    max_dispatch: Annotated[
        ActivePower,
        Field(
            ...,
            description="Maximum dispatchable capacity in kW.",
            ge=0,
        ),
    ]
    wholesale_tariff: Annotated[
        Optional[WholesaleMarketTariff],
        Field(None, description="Wholesale market tariff under which the aggregator settles."),
    ]

    @model_validator(mode="after")
    def validate_dispatch_limits(self) -> "DERAggregator":
        if self.max_dispatch < self.min_dispatch:
            raise ValueError("max_dispatch must be >= min_dispatch")
        return self

    @classmethod
    def example(cls) -> "DERAggregator":
        return DERAggregator(
            name="DER Portfolio Alpha",
            resources=[AggregatedDER.example()],
            offered_services=[
                AncillaryServiceType.REGULATION_UP,
                AncillaryServiceType.SPINNING_RESERVE,
            ],
            min_dispatch=ActivePower(10, "kilowatt"),
            max_dispatch=ActivePower(100, "kilowatt"),
        )


class LoadAggregator(Component):
    """Aggregates controllable loads for demand response programs."""

    name: str = Field(..., description="Name of the load aggregator")
    aggregator_type: AggregatorType = Field(
        default=AggregatorType.LOAD,
        description="Type of aggregator.",
    )
    resources: Annotated[
        list[AggregatedLoad],
        Field(..., min_length=1, description="Load resources in the aggregation portfolio."),
    ]
    total_curtailable_capacity: Annotated[
        ActivePower,
        Field(
            ...,
            description="Total curtailable capacity across all loads in kW.",
            ge=0,
        ),
    ]
    notification_lead_time_minutes: Annotated[
        int,
        Field(
            ...,
            description="Minimum advance notice required before curtailment in minutes.",
            ge=0,
        ),
    ]
    max_curtailment_duration_hours: Annotated[
        float,
        Field(
            ...,
            description="Maximum duration of a single curtailment event in hours.",
            gt=0,
        ),
    ]
    retail_tariff: Annotated[
        Optional[DistributionTariff],
        Field(None, description="Retail distribution tariff defining avoided cost for DR."),
    ]

    @classmethod
    def example(cls) -> "LoadAggregator":
        return LoadAggregator(
            name="DR Program Beta",
            resources=[AggregatedLoad.example()],
            total_curtailable_capacity=ActivePower(500, "kilowatt"),
            notification_lead_time_minutes=30,
            max_curtailment_duration_hours=4.0,
        )


class Aggregator(Component):
    """General-purpose aggregator that can bundle both DERs and loads."""

    name: str = Field(..., description="Name of the aggregator")
    aggregator_type: AggregatorType = Field(
        default=AggregatorType.GENERIC,
        description="Type of aggregator.",
    )
    der_resources: Annotated[
        Optional[list[AggregatedDER]],
        Field(None, description="DER resources in the portfolio."),
    ]
    load_resources: Annotated[
        Optional[list[AggregatedLoad]],
        Field(None, description="Load resources in the portfolio."),
    ]
    offered_services: Annotated[
        list[AncillaryServiceType],
        Field(
            default_factory=list,
            description="Ancillary services the aggregator can provide.",
        ),
    ]
    min_dispatch: Annotated[
        ActivePower,
        Field(
            ...,
            description="Minimum dispatchable capacity in kW.",
            ge=0,
        ),
    ]
    max_dispatch: Annotated[
        ActivePower,
        Field(
            ...,
            description="Maximum dispatchable capacity in kW.",
            ge=0,
        ),
    ]
    wholesale_tariff: Annotated[
        Optional[WholesaleMarketTariff],
        Field(None, description="Wholesale market tariff under which DER resources settle."),
    ]
    retail_tariff: Annotated[
        Optional[DistributionTariff],
        Field(None, description="Retail distribution tariff defining avoided cost for DR."),
    ]

    @model_validator(mode="after")
    def validate_has_resources(self) -> "Aggregator":
        if not self.der_resources and not self.load_resources:
            raise ValueError("Aggregator must have at least one DER or load resource")
        return self

    @model_validator(mode="after")
    def validate_dispatch_limits(self) -> "Aggregator":
        if self.max_dispatch < self.min_dispatch:
            raise ValueError("max_dispatch must be >= min_dispatch")
        return self

    @classmethod
    def example(cls) -> "Aggregator":
        return Aggregator(
            name="Mixed Portfolio Gamma",
            der_resources=[AggregatedDER.example()],
            load_resources=[AggregatedLoad.example()],
            offered_services=[
                AncillaryServiceType.REGULATION_UP,
                AncillaryServiceType.FREQUENCY_RESPONSE,
            ],
            min_dispatch=ActivePower(10, "kilowatt"),
            max_dispatch=ActivePower(200, "kilowatt"),
        )
