from datetime import datetime, timedelta
from uuid import uuid4

from infrasys import GeographicInfo, NonSequentialTimeSeries, SingleTimeSeries

from gdm.hashing_utils import remove_unreferenced_equipment
from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components import DistributionLoad, DistributionSolar
from gdm.systems.distribution.equipment import InverterEquipment, LoadEquipment, PhaseLoadEquipment
from gdm.systems.distribution.model_reduction import reduce_to_primary_system


def test_remove_unreferenced_equipment_preserves_shared_nested_models_and_metadata(tmp_path):
    system = DistributionSystem(name="test", auto_add_composed_components=True)
    load = DistributionLoad.example()
    second_load = load.model_copy(update={"uuid": uuid4(), "name": "second"})
    system.add_components(load, second_load)
    shared_phase = load.equipment.phase_loads[0]
    unused_phase = PhaseLoadEquipment.example().model_copy(update={"uuid": uuid4()})
    unused = LoadEquipment.example().model_copy(
        update={
            "uuid": uuid4(),
            "name": load.equipment.name,
            "phase_loads": [shared_phase, unused_phase],
        }
    )
    system.add_component(unused)
    info = GeographicInfo.example()
    unused_info = GeographicInfo.example()
    system.add_supplemental_attribute(load, info)
    system.add_supplemental_attribute(second_load, info)
    system.add_supplemental_attribute(unused, unused_info)
    series = SingleTimeSeries.from_array(
        [1.0, 2.0],
        name="power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    irregular = NonSequentialTimeSeries.from_array(
        [3.0, 4.0], name="other", timestamps=[datetime(2020, 1, 1), datetime(2020, 1, 3)]
    )
    system.add_time_series(series, load, second_load, scenario="base")
    system.add_time_series(irregular, info, scenario="attribute")
    system.add_time_series(series, unused, scenario="unused")

    cleaned = remove_unreferenced_equipment(system)

    assert system.has_component(unused)
    assert not cleaned.has_component(unused)
    assert not cleaned.has_component(unused_phase)
    assert cleaned.has_component(shared_phase)
    cleaned_load = cleaned.get_component_by_uuid(load.uuid)
    cleaned_second = cleaned.get_component_by_uuid(second_load.uuid)
    assert cleaned_load is not load
    assert cleaned_load.equipment is cleaned_second.equipment
    assert cleaned_load.equipment is not load.equipment
    assert cleaned.name == system.name
    assert cleaned.uuid == system.uuid
    assert cleaned.get_time_series(cleaned_load, "power", scenario="base").data.tolist() == [1, 2]
    assert cleaned.get_time_series(cleaned_second, "power", scenario="base").data.tolist() == [
        1,
        2,
    ]
    copied_info = cleaned.get_supplemental_attributes_with_component(cleaned_load)[0]
    assert copied_info is not info
    assert not cleaned.has_supplemental_attribute(unused_info)
    assert cleaned.get_supplemental_attributes_with_component(cleaned_second) == [copied_info]
    assert cleaned.get_time_series(
        copied_info, "other", time_series_type=NonSequentialTimeSeries, scenario="attribute"
    ).data.tolist() == [3, 4]
    assert len(cleaned.list_parent_components(cleaned_load.equipment)) == 2

    path = tmp_path / "cleaned.json"
    cleaned.to_json(path)
    restored = DistributionSystem.from_json(path)
    assert not restored.has_component(unused)
    assert restored.has_component(shared_phase)


def test_remove_unreferenced_equipment_uses_current_references():
    system = DistributionSystem(auto_add_composed_components=True)
    load = DistributionLoad.example()
    system.add_component(load)
    old_equipment = load.equipment
    new_equipment = LoadEquipment.example().model_copy(update={"uuid": uuid4()})
    system.add_component(new_equipment)
    load.equipment = new_equipment

    cleaned = remove_unreferenced_equipment(system)

    assert not cleaned.has_component(old_equipment)
    assert cleaned.has_component(new_equipment)
    assert cleaned.get_component_by_uuid(load.uuid).equipment.uuid == new_equipment.uuid


def test_remove_unreferenced_equipment_preserves_solar_inverter():
    system = DistributionSystem(auto_add_composed_components=True)
    solar = DistributionSolar.example()
    system.add_component(solar)
    unused_inverter = InverterEquipment.example().model_copy(update={"uuid": uuid4()})
    system.add_component(unused_inverter)

    cleaned = remove_unreferenced_equipment(system)

    assert cleaned.has_component(solar.inverter)
    assert not cleaned.has_component(unused_inverter)


def test_remove_unreferenced_equipment_after_primary_reduction(simple_distribution_system):
    reduced = reduce_to_primary_system(simple_distribution_system, name="reduced")
    unused = LoadEquipment.example()
    reduced.add_component(unused)

    cleaned = remove_unreferenced_equipment(reduced)

    assert reduced.has_component(unused)
    assert not cleaned.has_component(unused)
    assert {load.uuid for load in reduced.get_components(DistributionLoad)} == {
        load.uuid for load in cleaned.get_components(DistributionLoad)
    }
