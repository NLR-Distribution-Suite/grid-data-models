"""Shared helpers for distribution system reduction."""

import uuid
from typing import Callable, Type

from infrasys import Component
from infrasys.time_series_models import NonSequentialTimeSeries, SingleTimeSeries, TimeSeriesData
import networkx as nx

from gdm.systems.distribution.components.base.distribution_component_base import (
    _in_service_components,
)
from gdm.systems.distribution.components.distribution_battery import DistributionBattery
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.components.distribution_generator import DistributionGenerator
from gdm.systems.distribution.components.distribution_load import DistributionLoad
from gdm.systems.distribution.components.distribution_solar import DistributionSolar
from gdm.systems.distribution.distribution_system import DistributionSystem, UserAttributes
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.sys_functools import (
    _check_for_time_series_consistency,
    get_aggregated_battery_time_series,
    get_aggregated_load_time_series,
    get_aggregated_solar_time_series,
)


def _time_series_aggregators() -> dict[Type[Component], Callable]:
    return {
        DistributionLoad: get_aggregated_load_time_series,
        DistributionSolar: get_aggregated_solar_time_series,
        DistributionBattery: get_aggregated_battery_time_series,
    }


def _aggregation_metadata(system, component, time_series_type):
    result = {}
    for metadata in system.list_time_series_metadata(component, time_series_type=time_series_type):
        features = {key: value for key, value in metadata.features.items() if key != "use_actual"}
        key = (metadata.name, repr(sorted(features.items())))
        if key in result:
            raise ValueError(f"Ambiguous time series for {component.name}: {metadata.name}.")
        result[key] = metadata
    return result


def _get_aggregated_bus_component(
    subtree_system: DistributionSystem,
    bus: DistributionBus,
    model_type: DistributionLoad | DistributionSolar,
    split_phase_mapping: dict[str, set[Phase]],
    model_components: list[DistributionLoad | DistributionSolar] | None = None,
) -> DistributionLoad | DistributionSolar:
    if model_components is None:
        model_components = subtree_system.get_components(model_type)
    return model_type.aggregate(
        instances=list(model_components),
        bus=bus,
        name=str(uuid.uuid4()),
        split_phase_mapping=split_phase_mapping,
    )


def _validate_aggregation_time_series(
    system: DistributionSystem,
    model_type: type[Component],
    components: list[Component],
    time_series_type: Type[TimeSeriesData],
) -> None:
    metadata_keys = [
        set(_aggregation_metadata(system, component, time_series_type)) for component in components
    ]
    if any(keys != metadata_keys[0] for keys in metadata_keys[1:]):
        raise ValueError(f"Cannot aggregate mismatched {model_type.__name__} time series.")
    if metadata_keys[0] and model_type not in (DistributionLoad, DistributionSolar):
        raise ValueError(f"Time-series aggregation is unsupported for {model_type.__name__}.")


def _add_aggregated_time_series(
    source_system: DistributionSystem,
    reduced_system: DistributionSystem,
    model_type: type[Component],
    group: list[Component],
    aggregate: Component,
    time_series_type: Type[TimeSeriesData],
    ts_agg_func_mapper: dict[Type[Component], Callable],
    strict_time_series: bool = False,
) -> None:
    metadata_by_component = (
        [_aggregation_metadata(source_system, component, time_series_type) for component in group]
        if strict_time_series
        else None
    )
    metadata_list = (
        metadata_by_component[0].items()
        if metadata_by_component is not None
        else (
            (None, metadata)
            for metadata in source_system.list_time_series_metadata(
                group[0], time_series_type=time_series_type
            )
        )
    )
    for key, metadata in metadata_list:
        if metadata_by_component is None:
            ts_aggregate = ts_agg_func_mapper[model_type](
                source_system, group, metadata.name, time_series_type, **metadata.features
            )
        else:
            parts = [
                ts_agg_func_mapper[model_type](
                    source_system,
                    [component],
                    metadata.name,
                    time_series_type,
                    **component_metadata[key].features,
                )
                for component, component_metadata in zip(group, metadata_by_component)
            ]
            _check_for_time_series_consistency(parts[0], parts)
            if isinstance(parts[0], NonSequentialTimeSeries) and any(
                list(part.timestamps) != list(parts[0].timestamps) for part in parts[1:]
            ):
                raise ValueError("Cannot aggregate time series with different timestamps.")
            ts_aggregate = parts[0].model_copy(update={"data": sum(part.data for part in parts)})
        user_attr = UserAttributes.model_validate(metadata.features)
        user_attr.use_actual = True
        reduced_system.add_time_series(
            ts_aggregate,
            aggregate,
            **user_attr.model_dump(),
            **{k: v for k, v in metadata.features.items() if k not in user_attr.model_dump()},
        )


def _aggregate_subtree_components(
    subtree_system: DistributionSystem,
    dist_system: DistributionSystem,
    reduced_system: DistributionSystem,
    model_types: list[Type[Component]],
    source_bus_names: list[str],
    aggregated_component_uuids: set[uuid.UUID],
    target_bus: DistributionBus,
    split_phase_mapping: dict[str, set[Phase]],
    agg_time_series: bool,
    time_series_type: Type[TimeSeriesData],
    ts_agg_func_mapper: dict[Type[Component], Callable],
    strict_time_series: bool = False,
    asset_mapping: list[tuple[str, str, str]] | None = None,
) -> None:
    for model_type in model_types:
        model_components = [
            component
            for component in subtree_system.get_components(model_type)
            if component.uuid not in aggregated_component_uuids
            and getattr(component, "bus", None).name in source_bus_names
        ]
        aggregated_component_uuids.update(component.uuid for component in model_components)
        model_components = _in_service_components(model_components, require_nonempty=False)
        if not model_components:
            continue
        if model_type is DistributionGenerator:
            if agg_time_series and any(
                dist_system.has_time_series(component, time_series_type=time_series_type)
                for component in model_components
            ):
                raise ValueError(
                    "Time-series aggregation is unsupported for DistributionGenerator."
                )
            generator_components = [
                component
                for component in model_components
                if isinstance(component, DistributionGenerator)
            ]
            groups = DistributionGenerator._group_for_aggregation(
                generator_components, split_phase_mapping
            )
        else:
            groups = [model_components]
        for group in groups:
            if agg_time_series and strict_time_series:
                _validate_aggregation_time_series(dist_system, model_type, group, time_series_type)
            agg_component = _get_aggregated_bus_component(
                subtree_system,
                target_bus,
                model_type=model_type,
                split_phase_mapping=split_phase_mapping,
                model_components=group,
            )
            reduced_system.add_component(agg_component)
            if asset_mapping is not None:
                asset_mapping.extend(
                    (model_type.__name__, component.name, agg_component.name)
                    for component in group
                )
            if not agg_time_series:
                continue
            _add_aggregated_time_series(
                dist_system,
                reduced_system,
                model_type,
                group,
                agg_component,
                time_series_type,
                ts_agg_func_mapper,
                strict_time_series,
            )


def _reduce_system(
    dist_system: DistributionSystem,
    bus_subset: list[DistributionBus],
    name: str,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    allow_cycles: bool = False,
    directed_graph: nx.DiGraph | None = None,
    strict_time_series: bool = False,
    asset_mapping: list[tuple[str, str, str]] | None = None,
) -> DistributionSystem:
    if agg_timeseries is not None:
        agg_time_series = agg_timeseries

    closed_graph = _closed_edge_graph(dist_system)
    if not allow_cycles and nx.cycle_basis(nx.Graph(closed_graph)):
        raise ValueError("The system contains closed loops; run reduce_to_radial_network first.")

    original_tree = (
        directed_graph if directed_graph is not None else dist_system.get_directed_graph()
    )
    reduced_system = dist_system.get_subsystem(
        bus_subset,
        name,
        keep_time_series=agg_time_series,
        time_series_type=time_series_type,
        directed_graph=original_tree,
    )

    split_phase_mapping = dist_system.get_split_phase_mapping(directed_graph=original_tree)
    reduced_network_tree = original_tree.subgraph(bus_subset)
    retained_bus_names = set(bus_subset)
    aggregated_bus_names: set[str] = set()
    aggregated_component_uuids: set[uuid.UUID] = set()
    for node in reduced_network_tree.nodes():
        if reduced_network_tree.out_degree(node) < original_tree.out_degree(node):
            sucessors_diff = set(original_tree.successors(node)) - set(
                reduced_network_tree.successors(node)
            )
            successors_descendants = [
                snode
                for successor in sucessors_diff
                for snode in nx.descendants(original_tree, successor)
            ] + list(sucessors_diff)
            successors_descendants = list(
                set(successors_descendants) - retained_bus_names - aggregated_bus_names
            )
            aggregated_bus_names.update(successors_descendants)
            if not successors_descendants:
                continue
            subtree = original_tree.subgraph(successors_descendants)
            subtree_system = dist_system.get_subsystem(
                list(subtree.nodes),
                "",
                directed_graph=original_tree,
            )
            model_types = subtree_system.get_model_types_with_field_type(DistributionBus)
            _aggregate_subtree_components(
                subtree_system,
                dist_system,
                reduced_system,
                model_types,
                successors_descendants,
                aggregated_component_uuids,
                reduced_system.get_component(DistributionBus, node),
                split_phase_mapping,
                agg_time_series,
                time_series_type,
                _time_series_aggregators(),
                strict_time_series,
                asset_mapping,
            )

    return reduced_system


def _closed_edge_graph(system: DistributionSystem) -> nx.MultiGraph:
    """Build an undirected graph containing only electrically closed edges.

    Mirrors the edge filtering performed by ``get_directed_graph``: open switch
    edges (any phase open) are excluded, while all other branches and
    transformers count as closed.
    """
    graph = system.get_undirected_graph()
    closed_graph = nx.MultiGraph()
    for node in graph.nodes():
        closed_graph.add_node(node)
    for u, v, key, data in graph.edges(data=True, keys=True):
        if data.get("is_closed"):
            closed_graph.add_edge(u, v, key=key, **data)
    return closed_graph
