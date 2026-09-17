from datetime import datetime
from uuid import UUID
import pytest

from gdm.distribution.components import DistributionLoad, DistributionSolar
from gdm.quantities import ReactivePower, Voltage
from gdm.distribution import DistributionSystem
from gdm.distribution.equipment import (
    PhaseCapacitorEquipment,
    LoadEquipment,
)
from gdm.tracked_changes import (
    filter_tracked_changes_by_name_and_date,
    apply_updates_to_system,
    TrackedChange,
    PropertyEdit,
)


def build_tracked_changes(
    system: DistributionSystem,
) -> tuple[list[TrackedChange], UUID, UUID, UUID]:
    capacitor = next(system.get_components(PhaseCapacitorEquipment))

    load1, load2 = list(system.get_components(DistributionLoad))[:2]
    update_scenario = [
        TrackedChange(
            scenario_name="scenario_1",
            timestamp="2022-01-01 00:00:00",
            edits=[
                PropertyEdit(
                    component_uuid=capacitor.uuid,
                    name="rated_reactive_power",
                    value=ReactivePower(200, "kvar"),
                )
            ],
        ),
        TrackedChange(
            scenario_name="scenario_1",
            timestamp="2023-01-01 00:00:00",
            additions=["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
        ),
        TrackedChange(
            scenario_name="scenario_1",
            timestamp="2024-01-01 00:00:00",
            deletions=[load1.uuid],
        ),
        TrackedChange(
            scenario_name="scenario_2",
            timestamp="2025-01-01 00:00:00",
            deletions=[load2.uuid],
        ),
    ]
    return update_scenario, capacitor.uuid, load1.uuid, load2.uuid


def test_tracked_changes_by_date(distribution_system_with_single_time_series):
    system: DistributionSystem = distribution_system_with_single_time_series

    tracked_changes, cap_uuid, load_1_uuid, load_2_uuid = build_tracked_changes(system)

    catalog = DistributionSystem(auto_add_composed_components=True)
    load_equipment = LoadEquipment.example().model_copy(
        update={
            "uuid": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "name": "added_phase_load_model",
        }
    )
    catalog.add_component(load_equipment)
    system_date = datetime.strptime("2024-1-1", r"%Y-%m-%d")
    apply_updates_to_system(
        tracked_changes=tracked_changes, system=system, catalog=catalog, system_date=system_date
    )


def test_scenario_update(distribution_system_with_single_time_series):
    system: DistributionSystem = distribution_system_with_single_time_series
    tracked_changes, cap_uuid, _, _ = build_tracked_changes(system)
    catalog = DistributionSystem(auto_add_composed_components=True)
    load_equipment = LoadEquipment.example().model_copy(
        update={
            "uuid": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "name": "added_phase_load_model",
        }
    )
    catalog.add_component(load_equipment)
    with pytest.raises(ValueError):
        apply_updates_to_system(tracked_changes=tracked_changes, system=system, catalog=catalog)


def test_scenario_update_filter_by_scenario_name(distribution_system_with_single_time_series):
    system: DistributionSystem = distribution_system_with_single_time_series
    tracked_changes, cap_uuid, _, _ = build_tracked_changes(system)
    tracked_changes = filter_tracked_changes_by_name_and_date(
        tracked_changes, scenario_name="scenario_1"
    )
    catalog = DistributionSystem(auto_add_composed_components=True)
    load_equipment = LoadEquipment.example().model_copy(
        update={
            "uuid": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "name": "added_phase_load_model",
        }
    )
    catalog.add_component(load_equipment)
    updated_system = apply_updates_to_system(
        tracked_changes=tracked_changes, system=system, catalog=catalog
    )
    capacitor_new = updated_system.get_component_by_uuid(cap_uuid)

    assert capacitor_new.rated_reactive_power.to("kilovar").magnitude == 200.0


def test_scenario_update_filter_by_scenario_name_and_date(
    distribution_system_with_single_time_series,
):
    system: DistributionSystem = distribution_system_with_single_time_series
    tracked_changes, cap_uuid, _, _ = build_tracked_changes(system)
    tracked_changes = filter_tracked_changes_by_name_and_date(
        tracked_changes,
        scenario_name="scenario_1",
        timestamp=datetime.strptime("2022-1-1", "%Y-%m-%d"),
    )
    catalog = DistributionSystem(auto_add_composed_components=True)
    load_equipment = LoadEquipment.example().model_copy(
        update={
            "uuid": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "name": "added_phase_load_model",
        }
    )
    catalog.add_component(load_equipment)
    updated_system = apply_updates_to_system(
        tracked_changes=tracked_changes, system=system, catalog=catalog
    )
    capacitor = updated_system.get_component_by_uuid(cap_uuid)
    assert capacitor.rated_reactive_power.to("kilovar").magnitude == 200.0


def test_scenario_update_deletion_cascades_without_duplicate_child_failure():
    system = DistributionSystem(auto_add_composed_components=True)
    load = DistributionLoad.example()
    system.add_component(load)
    catalog = DistributionSystem(auto_add_composed_components=True)

    updated_system = apply_updates_to_system(
        [TrackedChange(scenario_name="scenario_1", deletions=[load.uuid])],
        system,
        catalog,
    )

    assert not updated_system.has_component(load)


def test_scenario_update_addition_rebinds_nested_component_to_system_instance():
    system = DistributionSystem(auto_add_composed_components=True)
    load = DistributionLoad.example()
    system.add_component(load)
    bus = load.bus

    catalog = DistributionSystem(auto_add_composed_components=True)
    solar = DistributionSolar.example()
    solar.bus = bus.model_copy(deep=True)
    catalog.add_component(solar)

    updated_system = apply_updates_to_system(
        [
            TrackedChange(
                scenario_name="scenario_1",
                additions=[solar.uuid],
                edits=[
                    PropertyEdit(
                        component_uuid=bus.uuid,
                        name="rated_voltage",
                        value=Voltage(999, "volt"),
                    )
                ],
            )
        ],
        system,
        catalog,
    )

    canonical_bus = updated_system.get_component_by_uuid(bus.uuid)
    new_solar = updated_system.get_component_by_uuid(solar.uuid)
    assert new_solar.bus is canonical_bus
    assert new_solar.bus.rated_voltage == Voltage(999, "volt")
