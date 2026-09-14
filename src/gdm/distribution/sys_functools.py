from typing import Type, Callable
from functools import singledispatch

import pandas as pd

from infrasys.time_series_models import (
    SingleTimeSeriesMetadata,
    NonSequentialTimeSeries,
    TimeSeriesMetadata,
    SingleTimeSeries,
    TimeSeriesData,
)
from infrasys.normalization import NormalizationMax, NormalizationByValue
from infrasys.component import Component
from pint import Quantity
import numpy as np

from gdm.distribution.components.distribution_load import DistributionLoad
from gdm.distribution.components.distribution_solar import DistributionSolar
from gdm.distribution.components.distribution_battery import DistributionBattery
from gdm.distribution.enums import Phase
from gdm.distribution.distribution_system import DistributionSystem, UserAttributes
from gdm.exceptions import (
    InconsistentTimeSeriesAggregation,
    NoComponentsFoundError,
    NoTimeSeriesDataFound,
    TimeSeriesVariableDoesNotExist,
    UnsupportedVariableError,
    IncompatibleTimeSeries,
    GDMQuantityError,
    GDMQuantityUnitsError,
)
from gdm.quantities import ActivePower


def get_time_series_actual_data(
    ts_data: SingleTimeSeries | NonSequentialTimeSeries,
) -> Quantity:
    """Function to return denormalized load power, if normalized."""
    return _apply_normalization(ts_data.normalization, ts_data.data)


@singledispatch
def _apply_normalization(normalization, data):
    msg = f"Unspported type of normalization {type(normalization)=}"
    raise TypeError(msg)


@_apply_normalization.register
def _(normalization: None, data) -> Quantity:
    return data


@_apply_normalization.register(NormalizationMax)
def _(normalization, data) -> Quantity:
    return data * normalization.max_value


@_apply_normalization.register(NormalizationByValue)
def _(normalization, data) -> Quantity:
    return data * normalization.value


def _get_load_power(
    load: DistributionLoad, ts_data: TimeSeriesData, metadata: TimeSeriesMetadata
) -> Quantity:
    """Internal function to return load power."""

    if metadata.features is None:
        msg = f"The {metadata.name} data is not a GDM quantity: {metadata.get_time_series_data_type()}"
        raise GDMQuantityError(msg)

    user_attr = UserAttributes.model_validate(metadata.features)

    # the denormalized data here is the time series multiplier of the peak
    # use_actual identifies this as actual time series values rather than multiplier
    denormalized_data = get_time_series_actual_data(ts_data)
    if user_attr.use_actual:
        return denormalized_data

    if metadata.name in {"active_power", "reactive_power"}:
        return denormalized_data.magnitude.tolist() * sum(
            ph_load.real_power if metadata.name == "active_power" else ph_load.reactive_power
            for ph_load in load.equipment.phase_loads
        )
    else:
        msg = f"{metadata.name} is not supported for load power calculation."
        raise UnsupportedVariableError(msg)


def _get_solar_power(
    solar: DistributionSolar, ts_data: TimeSeriesData, metadata: TimeSeriesMetadata
) -> Quantity:
    """Internal function to return time series data in kw"""

    if metadata.features is None:
        msg = f"The {metadata.name} data is not a GDM quantity: {metadata.get_time_series_data_type()}"
        raise GDMQuantityError(msg)

    denormalized_data = get_time_series_actual_data(ts_data)

    user_attr = UserAttributes.model_validate(metadata.features)
    if user_attr.use_actual:
        if denormalized_data.units not in {"kilowatt", "watt"}:
            msg = f"Invalid unit for use_actual: {denormalized_data.units}"
            raise GDMQuantityUnitsError(msg)

        return denormalized_data

    if not isinstance(denormalized_data, Quantity):
        msg = f"Denormalized data is not a pint Quantity: {type(denormalized_data)}"
        raise GDMQuantityError(msg)

    dc_power = denormalized_data.to("kilowatt/m^2").magnitude.tolist() * solar.active_power.to(
        "kilowatts"
    )
    return ActivePower(
        np.clip(
            dc_power,
            a_min=ActivePower(0, dc_power.units),
            a_max=solar.equipment.rated_power.to("kilova"),
        ).magnitude,
        dc_power.units,
    )


def _get_load_power_per_phase(
    load: DistributionLoad, ts_data: TimeSeriesData, metadata: TimeSeriesMetadata
) -> list[tuple[Phase, Quantity]]:
    """Internal function to return per-phase load power as a list of (phase, power) tuples."""
    if metadata.features is None:
        msg = f"The {metadata.name} data is not a GDM quantity: {metadata.get_time_series_data_type()}"
        raise GDMQuantityError(msg)

    user_attr = UserAttributes.model_validate(metadata.features)
    denormalized_data = get_time_series_actual_data(ts_data)

    if user_attr.use_actual:
        n_phases = len(load.phases)
        return [(phase, denormalized_data / n_phases) for phase in load.phases]

    if metadata.name in {"active_power", "reactive_power"}:
        return [
            (
                phase,
                denormalized_data.magnitude.tolist()
                * (
                    ph_load.real_power
                    if metadata.name == "active_power"
                    else ph_load.reactive_power
                ),
            )
            for phase, ph_load in zip(load.phases, load.equipment.phase_loads)
        ]
    else:
        msg = f"{metadata.name} is not supported for load power calculation."
        raise UnsupportedVariableError(msg)


def _get_solar_power_per_phase(
    solar: DistributionSolar, ts_data: TimeSeriesData, metadata: TimeSeriesMetadata
) -> list[tuple[Phase, Quantity]]:
    """Internal function to return per-phase solar power as a list of (phase, power) tuples.

    Solar has no per-phase power model, so total power is split equally across phases.
    """
    total_power = _get_solar_power(solar, ts_data, metadata)
    n_phases = len(solar.phases)
    return [(phase, total_power / n_phases) for phase in solar.phases]


def _check_for_time_series_metadata_consistency(ts_metadata: list[TimeSeriesMetadata]):
    # Extract unique properties from ts_data

    user_attrs = [UserAttributes.model_validate(metadata.features) for metadata in ts_metadata]
    unique_props = {
        "profile_type": {user_attr.profile_type for user_attr in user_attrs},
    }
    # Validate uniformity across properties
    if any(len(prop) != 1 for prop in unique_props.values()):
        inconsistent_props = {k: v for k, v in unique_props.items() if len(v) > 1}
        msg = f"Inconsistent time series data: {inconsistent_props}"
        raise InconsistentTimeSeriesAggregation(msg)


@singledispatch
def _check_for_time_series_consistency(times_series_sample, ts_list):
    msg = f"Incompatible time series model: {type(times_series_sample)}"
    raise IncompatibleTimeSeries(msg)


@_check_for_time_series_consistency.register(SingleTimeSeries)
def _(times_series_sample, ts_list) -> None:
    # Extract unique properties from SingleTimeSeries list
    unique_props = {
        "length": {data.length for data in ts_list},
        "resolution": {data.resolution for data in ts_list},
        "start_time": {data.initial_timestamp for data in ts_list},
        "variable": {data.name for data in ts_list},
        "data_type": {type(data.data) for data in ts_list},
    }
    # Validate uniformity across properties
    if any(len(prop) != 1 for prop in unique_props.values()):
        inconsistent_props = {k: v for k, v in unique_props.items() if len(v) > 1}
        msg = (
            f"Inconsistent time series data: {inconsistent_props} for {type(times_series_sample)}"
        )
        raise InconsistentTimeSeriesAggregation(msg)
    return None


@_check_for_time_series_consistency.register(NonSequentialTimeSeries)
def _(times_series_sample, ts_list) -> None:
    # Extract unique properties from SingleTimeSeries list
    unique_props = {
        "length": {data.length for data in ts_list},
        "variable": {data.name for data in ts_list},
        "data_type": {type(data.data) for data in ts_list},
        "timestamps_type": {type(data.timestamps) for data in ts_list},
    }

    # Validate uniformity across properties
    if any(len(prop) != 1 for prop in unique_props.values()):
        inconsistent_props = {k: v for k, v in unique_props.items() if len(v) > 1}
        msg = (
            f"Inconsistent time series data: {inconsistent_props} for {type(times_series_sample)}"
        )
        raise InconsistentTimeSeriesAggregation(msg)
    return None


def get_aggregated_solar_time_series(
    sys: DistributionSystem,
    solars: list[DistributionSolar],
    var_name: str,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
) -> TimeSeriesData:
    """Method to return aggregated solar time series data.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of the DistributionSystem
    solars: list[DistributionSolar]
        List of solar for aggregating time series data.
    var_name: str
        Variable name for which to combine time series data.
    time_series_type: Type[TimeSeriesData]
        Type of time series data. Defaults to: SingleTimeSeries

    Returns
    -------
    TimeSeriesData
    """
    if time_series_type.__name__ not in {"SingleTimeSeries", "NonSequentialTimeSeries"}:
        msg = f"Incompatible time series data: {time_series_type.__name__}"
        raise IncompatibleTimeSeries(msg)

    if var_name not in ["irradiance"]:
        msg = f"{var_name=} is not supported for solar time series aggregation."
        raise UnsupportedVariableError(msg)

    ts_components: list[TimeSeriesData] = [
        sys.get_time_series(solar, var_name, time_series_type=time_series_type) for solar in solars
    ]
    times_series_sample = ts_components[0]
    _check_for_time_series_consistency(times_series_sample, ts_components)

    ts_metadata: list[TimeSeriesMetadata] = [
        sys.list_time_series_metadata(solar, var_name, time_series_type=time_series_type)[0]
        for solar in solars
    ]
    _check_for_time_series_metadata_consistency(ts_metadata)
    ts_solar_data = [
        _get_solar_power(solar, ts_data, metadata)
        for solar, ts_data, metadata in zip(solars, ts_components, ts_metadata)
    ]
    if isinstance(times_series_sample, SingleTimeSeries):
        return SingleTimeSeries(
            data=sum(ts_solar_data),
            name=var_name,
            normalization=None,
            initial_timestamp=times_series_sample.initial_timestamp,
            resolution=times_series_sample.resolution,
        )
    else:
        return NonSequentialTimeSeries(
            data=sum(ts_solar_data),
            timestamps=times_series_sample.timestamps,
            name=var_name,
            normalization=None,
        )


def get_aggregated_battery_time_series(
    sys: DistributionSystem, batteries: list[DistributionBattery], var_name: str
) -> SingleTimeSeries:
    """Method to return combined battery time series data.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of the DistributionSystem
    batteries: list[DistributionBattery]
        List of battery for aggregating time series data.
    var_name: str
        Variable name used for time series aggregation.

    Returns
    -------
    SingleTimeSeries
    """
    ts_components: list[SingleTimeSeries] = [
        sys.get_time_series(battery, var_name) for battery in batteries
    ]
    _check_for_time_series_consistency(ts_components)
    ts_metadata: list[SingleTimeSeriesMetadata] = [
        sys.list_time_series_metadata(battery, var_name)[0] for battery in batteries
    ]
    _check_for_time_series_metadata_consistency(ts_metadata)
    ts_battery_data = [
        _get_load_power(battery, ts_data, metadata)
        for battery, ts_data, metadata in zip(batteries, ts_components, ts_metadata)
    ]
    return SingleTimeSeries(
        data=sum(ts_battery_data),
        name=var_name,
        normalization=None,
        initial_timestamp=ts_components[0].initial_timestamp,
        resolution=ts_components[0].resolution,
    )


def get_aggregated_load_time_series(
    sys: DistributionSystem,
    loads: list[DistributionLoad],
    var_name: str,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    **features,
) -> TimeSeriesData:
    """Method to return aggregated load time series data.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of the DistributionSystem
    loads: list[DistributionLoad]
        List of loads for aggregating time series data.
    var_name: str
        Variable name used for time series aggregation.
    time_series_type: Type[TimeSeriesData]
        Type of time series data. Defaults to: SingleTimeSeries

    Returns
    -------
    TimeSeriesData
    """
    if time_series_type.__name__ not in {"SingleTimeSeries", "NonSequentialTimeSeries"}:
        msg = f"Incompatible time series data: {time_series_type.__name__}"
        raise IncompatibleTimeSeries(msg)

    ts_components: list[TimeSeriesData] = [
        sys.get_time_series(load, var_name, time_series_type=time_series_type, **features)
        for load in loads
    ]

    times_series_sample = ts_components[0]

    _check_for_time_series_consistency(times_series_sample, ts_components)
    ts_metadata: list[TimeSeriesMetadata] = [
        sys.list_time_series_metadata(load, var_name, time_series_type=time_series_type)[0]
        for load in loads
    ]
    _check_for_time_series_metadata_consistency(ts_metadata)
    ts_load_data = [
        _get_load_power(load, ts_data, metadata)
        for load, ts_data, metadata in zip(loads, ts_components, ts_metadata)
    ]
    if isinstance(times_series_sample, SingleTimeSeries):
        return SingleTimeSeries(
            data=sum(ts_load_data),
            name=var_name,
            normalization=None,
            initial_timestamp=times_series_sample.initial_timestamp,
            resolution=times_series_sample.resolution,
        )
    else:
        return NonSequentialTimeSeries(
            data=sum(ts_load_data),
            timestamps=times_series_sample.timestamps,
            name=var_name,
            normalization=None,
        )


def _get_timestamps(ts_data: TimeSeriesData) -> pd.DatetimeIndex:
    """Extract timestamps from SingleTimeSeries or NonSequentialTimeSeries."""
    if isinstance(ts_data, SingleTimeSeries):
        return pd.date_range(
            start=ts_data.initial_timestamp,
            periods=ts_data.length,
            freq=ts_data.resolution,
        )
    return pd.DatetimeIndex(ts_data.timestamps)


def _convert_power_value(power_data, var: str, unit_conversion: dict[str, str]):
    """Apply unit conversion to power data. Returns (value, units) tuple."""
    if var in unit_conversion:
        if not isinstance(power_data, Quantity):
            msg = f"Unit conversion specified for {var}, but power data is not a pint Quantity."
            raise GDMQuantityError(msg)
        return power_data.to(unit_conversion[var]).magnitude, unit_conversion[var]
    return power_data, power_data.units


def _extract_features_cols(metadata: TimeSeriesMetadata) -> dict:
    """Extract scalar feature values from metadata, excluding use_actual.

    Returns scalars (one value per feature). Final DataFrame assembly expands
    each scalar to a column via ``np.repeat`` using each slice's row count.
    """
    return {k: v for k, v in (metadata.features or {}).items() if k != "use_actual"}


def _assemble_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Assemble a DataFrame from a list of row dicts produced by _build_power_row_df.

    Concatenates ndarray columns (value, timestamp) and repeats scalar columns
    (name, component_uuid, units, phase, features) to match lengths.
    """
    if not rows:
        return pd.DataFrame()

    lengths = np.fromiter((r["__length__"] for r in rows), dtype=np.int64, count=len(rows))
    ndarray_keys = {"value", "timestamp"}
    scalar_keys = [k for k in rows[0].keys() if k not in ndarray_keys and k != "__length__"]

    merged: dict = {}
    for k in ndarray_keys:
        merged[k] = np.concatenate([r[k] for r in rows])
    for k in scalar_keys:
        merged[k] = np.repeat(np.array([r[k] for r in rows], dtype=object), lengths)

    # Preserve original column order: timestamp, name, component_uuid, [phase], value, units, *features
    column_order = ["timestamp", "name", "component_uuid"]
    if "phase" in merged:
        column_order.append("phase")
    column_order += ["value", "units"]
    column_order += [k for k in scalar_keys if k not in column_order]
    return pd.DataFrame({k: merged[k] for k in column_order})


def _build_power_row_df(
    timestamps,
    var: str,
    component_uuid,
    length: int,
    power_data,
    unit_conversion: dict[str, str],
    features_cols: dict,
    phase: Phase | None = None,
) -> dict:
    """Build a column dict for one (component, variable, [phase]) time series slice.

    Stores ndarrays for the long columns (``value``, ``timestamp``) and *scalars*
    for everything else along with a ``__length__`` marker. The merge step uses
    ``np.concatenate`` for the ndarray columns and ``np.repeat`` for the scalar
    columns — so the final ``pd.DataFrame`` just wraps ready-made arrays.
    """
    value, units = _convert_power_value(power_data, var, unit_conversion)
    value_arr = np.asarray(value.magnitude if isinstance(value, Quantity) else value)
    timestamp_arr = timestamps.values
    row: dict = {
        "__length__": length,
        "timestamp": timestamp_arr,
        "name": var,
        "component_uuid": component_uuid,
    }
    if phase is not None:
        row["phase"] = phase
    row["value"] = value_arr
    row["units"] = units
    row.update(features_cols)
    return row


def _collect_component_rows(
    sys: DistributionSystem,
    component: Component,
    var_of_interest: set[str],
    power_function: Callable,
    unit_conversion: dict[str, str],
    time_series_type: Type[TimeSeriesData],
    aggregate_phases: bool,
    per_phase_function: Callable | None,
    include_features: bool,
) -> list[dict]:
    """Collect row dicts for a single component across all variables of interest."""
    ts_metadata = sys.list_time_series_metadata(component, time_series_type=time_series_type)

    if not ts_metadata:
        msg = f"No time series data found for {component=}."
        raise NoTimeSeriesDataFound(msg)

    avail_vars = {md.name for md in ts_metadata}

    if not var_of_interest.issubset(avail_vars):
        msg = f"{avail_vars=}. Only {var_of_interest=} is supported for dataframe computation."
        raise TimeSeriesVariableDoesNotExist(msg)

    rows = []
    for metadata in ts_metadata:
        if metadata.name not in var_of_interest:
            continue

        features = metadata.features or {}
        ts_data = sys.get_time_series(
            owner=component, name=metadata.name, time_series_type=time_series_type, **features
        )
        timestamps = _get_timestamps(ts_data)
        features_cols = _extract_features_cols(metadata) if include_features else {}

        if not aggregate_phases:
            for phase, power_data in per_phase_function(component, ts_data, metadata):
                rows.append(
                    _build_power_row_df(
                        timestamps,
                        metadata.name,
                        component.uuid,
                        ts_data.length,
                        power_data,
                        unit_conversion,
                        features_cols,
                        phase=phase,
                    )
                )
        else:
            power_data = power_function(component, ts_data, metadata)
            rows.append(
                _build_power_row_df(
                    timestamps,
                    metadata.name,
                    component.uuid,
                    ts_data.length,
                    power_data,
                    unit_conversion,
                    features_cols,
                )
            )
    return rows


def _get_combined_time_series_df(
    sys: DistributionSystem,
    component_type: type,
    var_of_interest: set[str],
    power_function: Callable,
    unit_conversion: dict[str, str],
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    aggregate_phases: bool = True,
    per_phase_function: Callable | None = None,
    include_features: bool = False,
) -> pd.DataFrame:
    """
    Generalized function for returning combined time series dataframe for given component type.

    Works with both SingleTimeSeries and NonSequentialTimeSeries.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of DistributionSystem.
    component_type: type
        The type of components to retrieve (e.g., DistributionLoad, DistributionSolar).
    var_of_interest: set[str]
        Set of variable names of interest.
    power_function: callable
        Function to compute power data for the component.
    unit_conversion: dict[str, str]
        Optional dictionary to perform unit conversion on data in pint quantities.
    time_series_type: Type[TimeSeriesData]
        Type of time series data. Defaults to: SingleTimeSeries
    aggregate_phases: bool
        If True (default), phases are summed and no ``phase`` column is added.
        If False, one row per phase is emitted and a ``phase`` column is added.
        Requires ``per_phase_function`` when False.
    per_phase_function: Callable | None
        Function with the same signature as ``power_function`` that returns
        ``list[tuple[Phase, Quantity]]``. Required when ``aggregate_phases=False``.
    include_features: bool
        If True, columns for each entry in ``metadata.features`` (excluding
        ``use_actual``) are added to the output DataFrame. Defaults to False.

    Returns
    -------
    pd.DataFrame

    Raises
    ------
    NoComponentsFoundError
        If no components of the specified type are found.
    NoTimeSeriesDataFound
        If no time series data is found for a component.
    TimeSeriesVariableDoesNotExist
        If specified variables do not exist for the given component.
    """
    components: list[Component] = list(sys.get_components(component_type))
    if not components:
        raise NoComponentsFoundError(
            f"No components of type {component_type.__name__} found in {sys.name}"
        )

    if not aggregate_phases and per_phase_function is None:
        msg = "per_phase_function is required when aggregate_phases is False."
        raise ValueError(msg)

    rows = []
    for component in components:
        rows.extend(
            _collect_component_rows(
                sys=sys,
                component=component,
                var_of_interest=var_of_interest,
                power_function=power_function,
                unit_conversion=unit_conversion,
                time_series_type=time_series_type,
                aggregate_phases=aggregate_phases,
                per_phase_function=per_phase_function,
                include_features=include_features,
            )
        )
    return _assemble_dataframe(rows)


def get_combined_load_time_series_df(
    sys: DistributionSystem,
    unit_conversion: dict[str, str],
    var_of_interest: set[str] = {"active_power", "reactive_power"},
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    aggregate_phases: bool = True,
    include_features: bool = False,
) -> pd.DataFrame:
    """
    Function for returning combined time series dataframe for load components.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of DistributionSystem.
    unit_conversion: dict[str, str]
        Optional dictionary to perform unit conversion on data in pint quantities.
    var_of_interest: set[str]
        Set of variable names of interest. Defaults to: {"active_power", "reactive_power"}
    time_series_type: Type[TimeSeriesData]
        Type of time series data. Defaults to: SingleTimeSeries
    aggregate_phases: bool
        If True (default), phase powers are summed into a single row per timestamp.
        If False, one row per phase is emitted with a ``phase`` column.
    include_features: bool
        If True, columns for each entry in ``metadata.features`` (excluding
        ``use_actual``) are added to the output DataFrame. Defaults to False.

    Returns
    -------
    pd.DataFrame
    """
    if time_series_type.__name__ not in {"SingleTimeSeries", "NonSequentialTimeSeries"}:
        msg = f"get_combined_load_time_series_df not implemented for {time_series_type.__name__}"
        raise IncompatibleTimeSeries(msg)
    return _get_combined_time_series_df(
        sys=sys,
        component_type=DistributionLoad,
        var_of_interest=var_of_interest,
        power_function=_get_load_power,
        unit_conversion=unit_conversion,
        time_series_type=time_series_type,
        aggregate_phases=aggregate_phases,
        per_phase_function=_get_load_power_per_phase,
        include_features=include_features,
    )


def get_combined_solar_time_series_df(
    sys: DistributionSystem,
    unit_conversion: dict[str, str],
    var_of_interest: set[str] = {"irradiance"},
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    aggregate_phases: bool = True,
    include_features: bool = False,
) -> pd.DataFrame:
    """
    Function for returning combined time series dataframe for solar components.

    Parameters
    ----------
    sys: DistributionSystem
        Instance of DistributionSystem.
    unit_conversion: dict[str, str]
        Optional dictionary to perform unit conversion on data in pint quantities.
    var_of_interest: set[str]
        Set of variable names of interest. Defaults to: {"irradiance"}
    time_series_type: Type[TimeSeriesData]
        Type of time series data. Defaults to: SingleTimeSeries
    aggregate_phases: bool
        If True (default), the total solar power is returned as a single row per timestamp.
        If False, one row per phase is emitted with a ``phase`` column; total power is
        split equally across phases since no per-phase solar model exists.
    include_features: bool
        If True, columns for each entry in ``metadata.features`` (excluding
        ``use_actual``) are added to the output DataFrame. Defaults to False.

    Returns
    -------
    pd.DataFrame
    """
    if time_series_type.__name__ not in {"SingleTimeSeries", "NonSequentialTimeSeries"}:
        msg = f"get_combined_solar_time_series_df not implemented for {time_series_type.__name__}"
        raise IncompatibleTimeSeries(msg)
    solar_df = _get_combined_time_series_df(
        sys=sys,
        component_type=DistributionSolar,
        var_of_interest=var_of_interest,
        power_function=_get_solar_power,
        unit_conversion=unit_conversion,
        time_series_type=time_series_type,
        aggregate_phases=aggregate_phases,
        per_phase_function=_get_solar_power_per_phase,
        include_features=include_features,
    )
    return solar_df.replace("irradiance", "active_power")
