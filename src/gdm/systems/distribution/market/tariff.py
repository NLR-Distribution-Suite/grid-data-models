from datetime import time

from pydantic import Field, model_validator
from typing import List, Optional
from infrasys import Component

from gdm.systems.distribution.enums import (
    AncillaryServiceType,
    WholesaleMarketType,
    BillingDemandBasis,
    CapacityMarketType,
    PricingNodeType,
    TOUPeriodType,
    CustomerClass,
    Month,
)


class TOURatePeriod(Component):
    name: str = ""
    start_time: time = Field(..., description="Start time of the rate period")
    end_time: time = Field(..., description="End time of the rate period")
    rate: float = Field(..., gt=0, description="Rate for the period in $/kWh")
    period_type: TOUPeriodType = Field(
        ..., description="Type of the TOU period (peak, off-peak, mid-peak)"
    )

    @model_validator(mode="after")
    def check_time_order(self) -> "TOURatePeriod":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

    @classmethod
    def example(cls) -> "TOURatePeriod":
        return TOURatePeriod(
            start_time=time(14, 0), end_time=time(20, 0), rate=0.25, period_type=TOUPeriodType.PEAK
        )


class DemandCharge(Component):
    name: str = ""
    months: List[Month] = Field(
        ..., min_length=1, description="Months for which this demand charge applies"
    )
    rate: float = Field(..., gt=0, description="Rate for demand charge in $/kW")
    billing_demand_basis: BillingDemandBasis = Field(
        ..., description="Basis for billing demand calculation"
    )
    time_applicability: Optional[List[TOURatePeriod]] = Field(
        ..., description="Time periods when the demand charge applies"
    )

    @model_validator(mode="after")
    def check_no_duplicate_months(self) -> "DemandCharge":
        if len(self.months) != len(set(self.months)):
            raise ValueError("Duplicate months are not allowed within a single DemandCharge")
        return self

    @classmethod
    def example(cls) -> "DemandCharge":
        return DemandCharge(
            months=[Month.JUNE, Month.JULY, Month.AUGUST],
            rate=12.50,
            billing_demand_basis=BillingDemandBasis.PEAK_15MIN,
            time_applicability=[TOURatePeriod.example()],
        )


class SeasonalTOURates(Component):
    name: str = ""
    months: List[Month] = Field(
        ..., min_length=1, description="Months for which these TOU rates apply"
    )
    tou_periods: List[TOURatePeriod] = Field(
        ..., description="List of TOU periods for the specified months"
    )

    @model_validator(mode="after")
    def check_no_duplicate_months(self) -> "SeasonalTOURates":
        if len(self.months) != len(set(self.months)):
            raise ValueError("Duplicate months are not allowed within a single SeasonalTOURates")
        return self

    @classmethod
    def example(cls) -> "SeasonalTOURates":
        return SeasonalTOURates(
            months=[Month.JUNE, Month.JULY, Month.AUGUST],
            tou_periods=[
                TOURatePeriod.example(),
                TOURatePeriod(
                    start_time=time(20, 0),
                    end_time=time(23, 59),
                    rate=0.15,
                    period_type=TOUPeriodType.OFF_PEAK,
                ),
            ],
        )


class TieredRate(Component):
    name: str = ""
    upper_limit_kwh: float = Field(..., gt=0, description="Upper limit of the tier in kWh")
    rate: float = Field(..., gt=0, description="Rate for the tier in $/kWh")

    @classmethod
    def example(cls) -> "TieredRate":
        return TieredRate(upper_limit_kwh=500, rate=0.12)


class FixedCharge(Component):
    name: str = ""
    amount: float = Field(..., ge=0, description="Amount of the fixed charge in $/month")
    description: Optional[str] = Field(None, description="Description of the fixed charge")

    @classmethod
    def example(cls) -> "FixedCharge":
        return FixedCharge(amount=15.00, description="Monthly fixed customer charge")


class DistributionTariff(Component):
    name: str = Field(..., description="Name of the tariff")
    utility: str = Field(..., description="Name of the utility company")
    customer_class: CustomerClass = Field(..., description="Customer class for the tariff")
    fixed_charge: Optional[FixedCharge] = Field(None, description="Fixed charge for the tariff")
    seasonal_tou: List[SeasonalTOURates] = Field(
        ..., description="Seasonal TOU rates for the tariff"
    )
    demand_charges: Optional[List[DemandCharge]] = Field(
        None, description="List of demand charges for the tariff"
    )
    tiered_energy_charges: Optional[List[TieredRate]] = Field(
        None, description="List of tiered energy charges for the tariff"
    )

    @model_validator(mode="after")
    def check_no_overlapping_months(self) -> "DistributionTariff":
        all_months = [m for entry in self.seasonal_tou for m in entry.months]
        if len(all_months) != len(set(all_months)):
            raise ValueError("A month must not appear in more than one SeasonalTOURates entry")
        return self

    @classmethod
    def example(cls) -> "DistributionTariff":
        return DistributionTariff(
            name="Residential Summer Tariff",
            utility="Example Utility",
            customer_class=CustomerClass.RESIDENTIAL,
            fixed_charge=FixedCharge.example(),
            seasonal_tou=[
                SeasonalTOURates.example(),
                SeasonalTOURates(
                    months=[Month.DECEMBER, Month.JANUARY, Month.FEBRUARY],
                    tou_periods=[
                        TOURatePeriod.example(),
                        TOURatePeriod(
                            start_time=time(0, 0),
                            end_time=time(6, 0),
                            rate=0.10,
                            period_type=TOUPeriodType.OFF_PEAK,
                        ),
                    ],
                ),
            ],
            demand_charges=[DemandCharge.example()],
            tiered_energy_charges=[TieredRate.example()],
        )


class LMPRate(Component):
    """Locational Marginal Price (LMP) broken into its standard components."""

    name: str = ""
    energy_rate: float = Field(..., description="Energy component of LMP in $/MWh")
    congestion_rate: float = Field(0.0, description="Congestion component of LMP in $/MWh")
    loss_rate: float = Field(0.0, description="Marginal loss component of LMP in $/MWh")

    @property
    def total_lmp(self) -> float:
        """Total LMP is the sum of energy, congestion, and loss components."""
        return self.energy_rate + self.congestion_rate + self.loss_rate

    @classmethod
    def example(cls) -> "LMPRate":
        return LMPRate(
            energy_rate=35.50,
            congestion_rate=5.25,
            loss_rate=1.10,
        )


class PricingNode(Component):
    """Represents a pricing node (PNode) in the wholesale market."""

    name: str = Field(..., description="Name or identifier of the pricing node")
    node_type: PricingNodeType = Field(..., description="Type of pricing node")
    zone: Optional[str] = Field(None, description="Load zone the node belongs to")

    @classmethod
    def example(cls) -> "PricingNode":
        return PricingNode(
            name="NODE_12345",
            node_type=PricingNodeType.LOAD_ZONE,
            zone="ZONE_A",
        )


class AncillaryServiceRate(Component):
    """Rate for a specific ancillary service product."""

    name: str = ""
    service_type: AncillaryServiceType = Field(..., description="Type of ancillary service")
    rate: float = Field(..., ge=0, description="Rate for the service in $/MW")
    market_type: WholesaleMarketType = Field(
        ..., description="Market in which the service is procured"
    )

    @classmethod
    def example(cls) -> "AncillaryServiceRate":
        return AncillaryServiceRate(
            service_type=AncillaryServiceType.REGULATION_UP,
            rate=12.00,
            market_type=WholesaleMarketType.DAY_AHEAD,
        )


class CapacityPayment(Component):
    """Capacity market payment structure."""

    name: str = ""
    capacity_market_type: CapacityMarketType = Field(
        ..., description="Type of capacity market product"
    )
    rate: float = Field(..., ge=0, description="Capacity payment rate in $/MW-day")
    commitment_months: List[Month] = Field(
        ..., min_length=1, description="Months covered by the capacity commitment"
    )

    @model_validator(mode="after")
    def check_no_duplicate_months(self) -> "CapacityPayment":
        if len(self.commitment_months) != len(set(self.commitment_months)):
            raise ValueError("Duplicate months are not allowed within a single CapacityPayment")
        return self

    @classmethod
    def example(cls) -> "CapacityPayment":
        return CapacityPayment(
            capacity_market_type=CapacityMarketType.FORWARD_CAPACITY,
            rate=150.00,
            commitment_months=[Month.JUNE, Month.JULY, Month.AUGUST],
        )


class TransmissionServiceCharge(Component):
    """Charge for transmission network service."""

    name: str = ""
    rate: float = Field(..., ge=0, description="Transmission service rate in $/MW")
    description: Optional[str] = Field(
        None, description="Description of the transmission service charge"
    )

    @classmethod
    def example(cls) -> "TransmissionServiceCharge":
        return TransmissionServiceCharge(
            rate=8.75,
            description="Network integration transmission service",
        )


class WholesaleMarketTariff(Component):
    """Wholesale electricity market tariff combining LMP, ancillary services,
    capacity, and transmission charges."""

    name: str = Field(..., description="Name of the wholesale tariff")
    market_operator: str = Field(
        ..., description="Name of the ISO/RTO operating the market (e.g., PJM, CAISO, ERCOT)"
    )
    market_type: WholesaleMarketType = Field(..., description="Day-ahead or real-time market")
    pricing_node: PricingNode = Field(..., description="Pricing node where the tariff applies")
    lmp_rate: LMPRate = Field(..., description="Locational marginal price components")
    ancillary_service_rates: Optional[List[AncillaryServiceRate]] = Field(
        None, description="Ancillary service rates"
    )
    capacity_payments: Optional[List[CapacityPayment]] = Field(
        None, description="Capacity market payments"
    )
    transmission_charges: Optional[List[TransmissionServiceCharge]] = Field(
        None, description="Transmission service charges"
    )

    @model_validator(mode="after")
    def check_no_duplicate_ancillary_services(self) -> "WholesaleMarketTariff":
        if self.ancillary_service_rates:
            service_keys = [(r.service_type, r.market_type) for r in self.ancillary_service_rates]
            if len(service_keys) != len(set(service_keys)):
                raise ValueError(
                    "Duplicate ancillary service type and market type "
                    "combinations are not allowed"
                )
        return self

    @classmethod
    def example(cls) -> "WholesaleMarketTariff":
        return WholesaleMarketTariff(
            name="PJM Day-Ahead LMP Tariff",
            market_operator="PJM",
            market_type=WholesaleMarketType.DAY_AHEAD,
            pricing_node=PricingNode.example(),
            lmp_rate=LMPRate.example(),
            ancillary_service_rates=[
                AncillaryServiceRate.example(),
                AncillaryServiceRate(
                    service_type=AncillaryServiceType.SPINNING_RESERVE,
                    rate=6.50,
                    market_type=WholesaleMarketType.DAY_AHEAD,
                ),
            ],
            capacity_payments=[CapacityPayment.example()],
            transmission_charges=[TransmissionServiceCharge.example()],
        )
