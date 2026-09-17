from pathlib import Path


from pydantic import ValidationError
from gdm.distribution import DistributionSystem
from gdm.distribution.upgrade_handler.upgrade_handler import UpgradeHandler, UpgradeSchema
from gdm.distribution.upgrade_handler.from__2_3_2__to__2_3_3 import from__2_3_2__to__2_3_3

import pytest

base_path = Path(__file__).parent
model_path = base_path / "dataset" / "p5r" / "p5r.json"


def test_version_bump():
    upgrade_handler = UpgradeHandler()
    DistributionSystem.from_json(filename=model_path, upgrade_handler=upgrade_handler.upgrade)


def test_unique_from_version():
    with pytest.raises(ValidationError):
        UpgradeHandler(
            upgrade_schemas=[
                UpgradeSchema(
                    method=lambda x: x,
                    from_version="1.0.0",
                    to_version="2.0.0",
                ),
                UpgradeSchema(
                    method=lambda x: x,
                    from_version="1.0.0",
                    to_version="2.0.0",
                ),
            ]
        )


def test_unique_to_version():
    with pytest.raises(ValidationError):
        UpgradeHandler(
            upgrade_schemas=[
                UpgradeSchema(
                    method=lambda x: x,
                    from_version="1.0.0",
                    to_version="2.0.0",
                ),
                UpgradeSchema(
                    method=lambda x: x,
                    from_version="1.1.0",
                    to_version="2.0.0",
                ),
            ]
        )


def test_version_chain():
    upgrade_handler = UpgradeHandler(
        upgrade_schemas=[
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.0.0",
                to_version="1.1.0",
            ),
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.2.0",
                to_version="2.0.0",
            ),
        ]
    )
    with pytest.raises(ValueError):
        upgrade_handler.upgrade({}, "1.0.0", "2.0.0")


def test_version_chain_start():
    upgrade_handler = UpgradeHandler(
        upgrade_schemas=[
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.0.0",
                to_version="1.1.0",
            ),
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.1.0",
                to_version="2.0.0",
            ),
        ]
    )
    with pytest.raises(ValueError):
        upgrade_handler.upgrade({}, "0.1.0", "2.0.0")


def test_version_chain_end():
    upgrade_handler = UpgradeHandler(
        upgrade_schemas=[
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.0.0",
                to_version="1.1.0",
            ),
            UpgradeSchema(
                method=lambda x: x,
                from_version="1.1.0",
                to_version="2.0.0",
            ),
        ]
    )
    with pytest.raises(ValueError):
        upgrade_handler.upgrade({}, "1.0.0", "3.0.0")


def test_version_chain_valid():
    upgrade_handler = UpgradeHandler(
        upgrade_schemas=[
            UpgradeSchema(
                method=lambda x, y, z: x,
                from_version="1.0.0",
                to_version="1.1.0",
            ),
            UpgradeSchema(
                method=lambda x, y, z: x,
                from_version="1.1.0",
                to_version="2.0.0",
            ),
            UpgradeSchema(
                method=lambda x, y, z: x,
                from_version="2.0.0",
                to_version="3.0.0",
            ),
        ]
    )
    upgrade_handler.upgrade({}, "1.0.0", "3.0.0")


def _make_component(component_type, module, fields):
    """Helper to build a serialized component dict with __metadata__."""
    return {
        **fields,
        "__metadata__": {
            "fields": {
                "module": module,
                "type": component_type,
                "serialized_type": "base",
            }
        },
    }


def _sample_tou_period():
    """Return a minimal serialized TOURatePeriod component."""
    return _make_component(
        "TOURatePeriod",
        "gdm.distribution.market.tariff",
        {
            "name": "",
            "start_time": "14:00:00",
            "end_time": "20:00:00",
            "rate": 0.25,
            "period_type": "peak",
        },
    )


def _make_tariff_data(seasonal_tou_entries, demand_charges=None, fixed_charge=None):
    """Build a minimal data dict containing a DistributionTariff with nested components."""
    tariff = _make_component(
        "DistributionTariff",
        "gdm.distribution.market.tariff",
        {
            "name": "test_tariff",
            "utility": "TestCo",
            "customer_class": "residential",
            "fixed_charge": fixed_charge,
            "seasonal_tou": seasonal_tou_entries,
            "demand_charges": demand_charges,
        },
    )
    return {
        "data_format_version": "2.3.2",
        "components": [tariff],
    }


def test_migrate_seasonal_tou_season_to_months():
    """season (single Season enum) is renamed to months (List[Month])."""
    seasonal_entry = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"season": "summer", "tou_periods": [_sample_tou_period()]},
    )
    data = _make_tariff_data([seasonal_entry])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    migrated = result["components"][0]["seasonal_tou"][0]
    assert "season" not in migrated
    assert migrated["months"] == ["june", "july", "august"]


def test_migrate_seasonal_tou_all_seasons():
    """Verify all three season values are mapped correctly."""
    entries = [
        _make_component(
            "SeasonalTOURates",
            "gdm.distribution.market.tariff",
            {"season": season, "tou_periods": [_sample_tou_period()]},
        )
        for season in ("summer", "winter", "shoulder")
    ]
    data = _make_tariff_data(entries)
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    months_lists = [e["months"] for e in result["components"][0]["seasonal_tou"]]
    assert months_lists[0] == ["june", "july", "august"]
    assert months_lists[1] == ["december", "january", "february"]
    assert months_lists[2] == ["march", "april", "may", "september", "october", "november"]


def test_migrate_seasonal_tou_already_has_months():
    """If months already exists, it should not be modified."""
    seasonal_entry = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"months": ["june", "july"], "tou_periods": [_sample_tou_period()]},
    )
    data = _make_tariff_data([seasonal_entry])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    migrated = result["components"][0]["seasonal_tou"][0]
    assert migrated["months"] == ["june", "july"]


def test_migrate_demand_charge_adds_months():
    """DemandCharge without months gets all 12 months added."""
    demand = _make_component(
        "DemandCharge",
        "gdm.distribution.market.tariff",
        {
            "rate": 10.0,
            "billing_demand_basis": "peak_15min",
            "time_applicability": [_sample_tou_period()],
        },
    )
    seasonal = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"months": ["june"], "tou_periods": [_sample_tou_period()]},
    )
    data = _make_tariff_data([seasonal], demand_charges=[demand])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    migrated = result["components"][0]["demand_charges"][0]
    assert len(migrated["months"]) == 12
    assert migrated["months"][0] == "january"
    assert migrated["months"][-1] == "december"


def test_migrate_demand_charge_already_has_months():
    """DemandCharge with existing months should not be modified."""
    demand = _make_component(
        "DemandCharge",
        "gdm.distribution.market.tariff",
        {
            "months": ["june", "july", "august"],
            "rate": 10.0,
            "billing_demand_basis": "peak_15min",
            "time_applicability": [_sample_tou_period()],
        },
    )
    seasonal = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"months": ["january"], "tou_periods": [_sample_tou_period()]},
    )
    data = _make_tariff_data([seasonal], demand_charges=[demand])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    migrated = result["components"][0]["demand_charges"][0]
    assert migrated["months"] == ["june", "july", "august"]


def test_migrate_version_updated():
    """data_format_version should be updated to 2.3.3."""
    seasonal = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"months": ["june"], "tou_periods": [_sample_tou_period()]},
    )
    data = _make_tariff_data([seasonal])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")
    assert result["data_format_version"] == "2.3.3"


def test_migrate_component_count_preserved():
    """Component count must be the same before and after migration."""
    seasonal = _make_component(
        "SeasonalTOURates",
        "gdm.distribution.market.tariff",
        {"season": "winter", "tou_periods": [_sample_tou_period()]},
    )
    demand = _make_component(
        "DemandCharge",
        "gdm.distribution.market.tariff",
        {
            "rate": 5.0,
            "billing_demand_basis": "peak_hour",
            "time_applicability": [_sample_tou_period()],
        },
    )
    data = _make_tariff_data([seasonal], demand_charges=[demand])
    original_count = len(data["components"])
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")
    assert len(result["components"]) == original_count


def test_migrate_with_empty_list_fields():
    """Components with empty list fields must not break metadata migration."""
    bus = _make_component(
        "DistributionBus",
        "gdm.distribution.components.distribution_bus",
        {
            "name": "bus1",
            "voltage_type": "line-to-ground",
            "phases": ["A", "B", "C"],
            "voltagelimits": [],
        },
    )
    data = {"data_format_version": "2.3.2", "components": [bus]}
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    assert result["components"][0]["voltagelimits"] == []
    assert result["components"][0]["__metadata__"]["type"] == "DistributionBus"


def test_migrate_flat_metadata_with_empty_list_fields():
    """Flat (already migrated) metadata with empty list fields passes through unchanged."""
    bus = {
        "name": "bus1",
        "voltage_type": "line-to-ground",
        "phases": ["A", "B", "C"],
        "voltagelimits": [],
        "__metadata__": {
            "module": "gdm.distribution.components.distribution_bus",
            "type": "DistributionBus",
            "serialized_type": "base",
        },
    }
    data = {"data_format_version": "2.3.2", "components": [bus]}
    result = from__2_3_2__to__2_3_3(data, "2.3.2", "2.3.3")

    assert result["components"][0]["voltagelimits"] == []
    assert result["data_format_version"] == "2.3.3"
