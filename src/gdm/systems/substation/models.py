"""Shared references, ratings, documents, and lifecycle records."""

from datetime import datetime
from typing import Annotated

from pydantic import Field
from infrasys import Component

from gdm.systems.substation.enums import AssetRole, DocumentType, LifecycleStatus


Identifier = Annotated[str, Field(min_length=1)]


class ExternalIdentifier(Component):
    """Identifier assigned by another utility or engineering system."""

    source_system: Identifier
    value: Identifier
    role: str = "external_id"

    @classmethod
    def example(cls) -> "ExternalIdentifier":
        return cls(name="asset-id", source_system="utility_eam", value="SUB-001")


class AssetReference(Component):
    """Stable reference to an asset owned by another model or system."""

    asset_id: Identifier
    role: AssetRole = AssetRole.PRIMARY_EQUIPMENT
    source_system: str | None = None
    display_name: str | None = None

    @classmethod
    def example(cls) -> "AssetReference":
        return cls(name="transformer-ref", asset_id="asset-transformer-001")


class ModelReference(Component):
    """Reference to a distribution, plant, or analysis model boundary."""

    model_id: Identifier
    model_type: Identifier
    revision: str | None = None
    relationship: str = "references"

    @classmethod
    def example(cls) -> "ModelReference":
        return cls(
            name="distribution-model-ref", model_id="dist-model-001", model_type="distribution"
        )


class StandardProfile(Component):
    """A project or utility applicability profile for a standard or rule."""

    standard: Identifier
    edition: str
    authority: str | None = None
    jurisdiction: str = "US"
    applicability: str | None = None
    source_url: str | None = None

    @classmethod
    def example(cls) -> "StandardProfile":
        return cls(
            name="der-profile",
            standard="IEEE 1547",
            edition="2018",
            authority="utility_interconnection",
        )


class DocumentReference(Component):
    """Metadata for an external engineering or compliance artifact."""

    document_type: DocumentType
    uri: str
    revision: str | None = None
    sha256: str | None = None
    approved: bool = False
    effective_from: datetime | None = None
    supersedes_document_id: str | None = None

    @classmethod
    def example(cls) -> "DocumentReference":
        return cls(
            name="station-scd",
            document_type=DocumentType.SCL,
            uri="urn:example:substation:001:scd",
            revision="A",
        )


class Rating(Component):
    """A rating with its operating condition and provenance."""

    rating_type: Identifier
    value: float = Field(..., ge=0)
    unit: Identifier
    duration_seconds: float | None = Field(None, gt=0)
    condition: str | None = None
    standard_profile_id: str | None = None
    study_id: str | None = None

    @classmethod
    def example(cls) -> "Rating":
        return cls(
            name="normal-current", rating_type="continuous_current", value=600, unit="ampere"
        )


class LifecycleRecord(Component):
    """Lifecycle status and validity interval for a station object."""

    status: LifecycleStatus
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_document_id: str | None = None
    notes: str | None = None

    @classmethod
    def example(cls) -> "LifecycleRecord":
        return cls(name="commissioned", status=LifecycleStatus.COMMISSIONED)


class StateObservation(Component):
    """Observed or scenario state, separate from engineering configuration."""

    observed_at: datetime
    state: str
    source: str
    quality: str | None = None
    scenario: str | None = None

    @classmethod
    def example(cls) -> "StateObservation":
        return cls(
            name="breaker-state",
            observed_at=datetime(2025, 1, 1),
            state="closed",
            source="scada",
        )


class ConfigurationBaseline(Component):
    """Approved engineering or operational model baseline."""

    baseline_type: Identifier
    revision: Identifier
    status: str = "draft"
    parent_baseline_id: str | None = None
    standard_profile_ids: list[str] = Field(default_factory=list)
    document_reference_ids: list[str] = Field(default_factory=list)
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    @classmethod
    def example(cls) -> "ConfigurationBaseline":
        return cls(
            name="as-commissioned-baseline",
            baseline_type="station_engineering",
            revision="A",
            status="approved",
        )
