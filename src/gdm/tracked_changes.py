from typing import Any, Annotated
from datetime import datetime

from gdm.distribution import DistributionSystem, CatalogSystem

from pydantic import Field
from rich.console import Console
from infrasys import Component
from infrasys.exceptions import ISNotStored
from rich.table import Table
from uuid import UUID


class PropertyEdit(Component):
    name: str
    value: Any
    component_uuid: UUID


class TrackedChange(Component):
    """
    This model represents tracked changes to the distribution system model. This is useful when there is a need
    a) to track system changes over time (e.g., a capacity expansion problem)
    b) to save multiple scenarios that apply to a given base model. (e.g., a Monte Carlo study)
    """

    name: Annotated[str, Field("", description="Internal name for the tracked change")]
    scenario_name: Annotated[
        str,
        Field(
            "",
            description="If these changes represent a scenario that needs to be tracked, provide a name, otherwise, use the default value",
        ),
    ]
    timestamp: Annotated[
        datetime | None,
        Field(
            None,
            description="If these changes are to be applied on specific timestamp, provide a timestamp, else leave it blank",
        ),
    ]
    additions: Annotated[
        list[UUID], Field([], description="List of additions to the base distribution system")
    ]
    edits: Annotated[
        list[PropertyEdit], Field([], description="List of edits for the base distribution system")
    ]
    deletions: Annotated[
        list[UUID], Field([], description="List of edits to the base distribution system")
    ]


def filter_tracked_changes_by_name_and_date(
    tracked_changes: list[TrackedChange],
    scenario_name: str | None = None,
    timestamp: datetime | None = None,
) -> list[TrackedChange]:
    """
    Filters a list of tracked changes based on scenario name and/or update date.

    This function allows filtering of tracked changes by either scenario name or update date.
    At least one of these parameters must be provided. If both are provided, the function
    returns changes that match the scenario name and have an update date less than or equal
    to the specified date.

    Parameters
    ----------
    tracked_changes : list[TrackedChange]
        A list of TrackedChange objects to be filtered.
    scenario_name : str, optional
        The name of the scenario to filter by. If None, filtering by scenario name is skipped.
    timestamp : datetime, optional
        The date to filter by. If None, filtering by date is skipped.

    Returns
    -------
    list[TrackedChange]
        A list of TrackedChange objects that match the specified filters.

    Raises
    ------
    ValueError
        If neither 'scenario_name' nor 'timestamp' is provided.
    AssertionError
        If filtering by timestamp and any TrackedChange object has a None timestamp.

    Examples
    --------
    >>> changes = filter_tracked_changes_by_name_and_date(tracked_changes, scenario_name="Scenario A")
    >>> changes = filter_tracked_changes_by_name_and_date(
    ...     tracked_changes, timestamp=datetime(2023, 1, 1)
    ... )
    >>> changes = filter_tracked_changes_by_name_and_date(
    ...     tracked_changes, "Scenario A", datetime(2023, 1, 1)
    ... )
    """

    if scenario_name is None and timestamp is None:
        raise ValueError(
            "At least one of 'scenario_name' or 'timestamp' must be provided for filtering."
        )

    if scenario_name:
        tracked_changes_filt = [
            change for change in tracked_changes if change.scenario_name == scenario_name
        ]
    else:
        tracked_changes_filt = tracked_changes

    if timestamp:
        assert (
            None not in [change.timestamp for change in tracked_changes_filt]
        ), "When filtering by timestamp, for all TrackedChange objects timestamp should be a valid date"
        tracked_changes_by_date = [
            change for change in tracked_changes_filt if change.timestamp <= timestamp
        ]
        return tracked_changes_by_date
    else:
        return tracked_changes_filt


def _update_temporal_table(
    updates: list,
    timestamp: datetime,
    change_type: str,
    component: Component,
    bus_names: str,
    scenario_name: str,
):
    """
    Updates a temporal table with change information.

    Appends a list of change details to the provided updates list. The details
    include the update date, type of change, component UUID, component label,
    component name, and bus names.

    Args:
        updates (list): The list to which the update details will be appended.
        timestamp (date): The date of the update.
        change_type (str): The type of change being recorded.
        component (Component): The component associated with the change.
        bus_names (str): The names of the buses affected by the change.
        scenario_name (str): The names of scenario_name.
    """
    updates.append(
        [
            str(timestamp),
            change_type,
            str(component.uuid),
            component.label.split(".")[0],
            component.name,
            bus_names,
            scenario_name,
        ]
    )


def _get_bus_names(component):
    if hasattr(component, "bus"):
        bus_names = component.bus.name
    elif hasattr(component, "buses"):
        bus_names = "\n".join([bus.name for bus in component.buses])
    else:
        bus_names = "None"
    return bus_names


def _rebind_composed_components(component: Component, system: DistributionSystem) -> None:
    for field_name in type(component).model_fields:
        value = getattr(component, field_name)
        if isinstance(value, Component):
            canonical = (
                system.get_component_by_uuid(value.uuid) if system.has_component(value) else value
            )
            if canonical is not value:
                setattr(component, field_name, canonical)
            else:
                _rebind_composed_components(value, system)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Component):
                    _rebind_composed_components(item, system)


def _remove_component_with_unique_cascade(
    system: DistributionSystem, component: Component
) -> None:
    child_uuids = list(
        dict.fromkeys(child.uuid for child in system.list_child_components(component))
    )
    system.remove_component(component, cascade_down=False)
    for child_uuid in child_uuids:
        try:
            child = system.get_component_by_uuid(child_uuid)
        except ISNotStored:
            continue
        if not system.list_parent_components(child):
            _remove_component_with_unique_cascade(system, child)


def apply_updates_to_system(
    tracked_changes: list[TrackedChange],
    system: DistributionSystem,
    catalog: DistributionSystem,
    system_date: datetime | None = None,
):
    """
    Applies a series of tracked changes to a distribution system model.

    This function processes a list of `TrackedChange` objects and applies the specified
    additions, deletions, and edits to the given `system`. The changes are applied in
    chronological order based on the `timestamp` of each tracked change. If a `system_date`
    is provided, only changes with an `timestamp` less than or equal to this date are applied.

    Parameters
    ----------
    tracked_changes : list[TrackedChange]
        A list of `TrackedChange` objects containing the changes to be applied.
    system : DistributionSystem
        The distribution system to which the changes will be applied.
    catalog : DistributionSystem
        The catalog used to retrieve components by UUID for additions.
    system_date : datetime, optional
        The cutoff date for applying changes. Only changes with an `timestamp` less than
        or equal to this date will be applied. If None, all changes are applied.

    Returns
    -------
    DistributionSystem
        The updated distribution system with the applied changes.

    Raises
    ------
    ValueError
        If the scenario names are not consistent across all tracked changes.
    AttributeError
        If an edit specifies a property that does not exist on a component.

    Examples
    --------
    >>> updated_system = apply_updates_to_system(tracked_changes, system, catalog)
    >>> updated_system = apply_updates_to_system(
    ...     tracked_changes, system, catalog, datetime(2023, 1, 1)
    ... )
    """

    if None not in [change.timestamp for change in tracked_changes]:
        tracked_changes = sorted(tracked_changes, key=lambda x: x.timestamp, reverse=False)
    if system_date:
        tracked_changes = list(filter(lambda x: x.timestamp <= system_date, tracked_changes))

    unique_scenarios = {change.scenario_name for change in tracked_changes}
    if len(unique_scenarios) != 1:
        raise ValueError("Scenario name should be consistant across all tracked changes.")

    log = []
    system_copy = system.deepcopy()
    for change in tracked_changes:
        system_copy = _apply_tracked_changes(
            system=system_copy, tracked_change=change, catalog=catalog, log=log
        )

    # Log the system updates.
    _update_log(log)
    return system_copy


def _apply_tracked_changes(
    system: DistributionSystem,
    tracked_change: TrackedChange,
    catalog: DistributionSystem | CatalogSystem,
    log: list = [],
    show_table: bool = False,
):
    """
    Applies tracked changes to a distribution system model.

    This function processes additions, deletions, and edits specified in the
    `TrackedChange` object and applies them to the given `system`. It updates
    the system by adding new components, removing existing ones, and modifying
    attributes of components. The changes are logged in the `log` list, and an
    optional table display of the changes can be shown.

    Args:
        system (DistributionSystem): The distribution system to which changes are applied.
        tracked_change (TrackedChange): The object containing lists of additions, deletions, and edits.
        catalog (DistributionSystem | CatalogSystem): The catalog used to retrieve components by UUID.
        log (list, optional): A list to store logs of the changes applied. Defaults to an empty list.
        show_table (bool, optional): If True, displays a table of the changes applied. Defaults to False.

    Returns:
        DistributionSystem: The updated distribution system with the applied changes.

    Raises:
        AttributeError: If an edit specifies a property that does not exist on a component.
    """

    for model_uuid in tracked_change.additions:
        component = catalog.get_component_by_uuid(model_uuid)
        if not system.has_component(component):
            component = component.model_copy(deep=True)
            _rebind_composed_components(component, system)
            system.add_component(component)
            bus_names = _get_bus_names(component)
            _update_temporal_table(
                log,
                tracked_change.timestamp,
                "Addition",
                component,
                bus_names,
                tracked_change.scenario_name,
            )

    # Process deletions: Remove components from the system.
    for model_uuid in tracked_change.deletions:
        component = system.get_component_by_uuid(model_uuid)
        if system.has_component(component):
            _remove_component_with_unique_cascade(system, component)
            bus_names = _get_bus_names(component)
            _update_temporal_table(
                log,
                tracked_change.timestamp,
                "Deletion",
                component,
                bus_names,
                tracked_change.scenario_name,
            )

    # Process edits: Update component attributes.
    for edit_model in tracked_change.edits:
        component = system.get_component_by_uuid(edit_model.component_uuid)
        if not hasattr(component, edit_model.name):
            raise AttributeError(
                f"{component.label} does not have a property called {edit_model.name}"
            )
        setattr(component, edit_model.name, edit_model.value)
        component = system.get_component_by_uuid(edit_model.component_uuid)
        bus_names = _get_bus_names(component)

        _update_temporal_table(
            log,
            tracked_change.timestamp,
            "Edit",
            component,
            bus_names,
            tracked_change.scenario_name,
        )

    if show_table:
        _update_log(log)
    return system


def _update_log(update_log: list[str]):
    """
    Displays a table of updates applied to the system from a given scenario.

    Args:
        scenario_name (str): The name of the scenario from which updates are applied.
        update_log (list[str]): A list of update entries, where each entry is a list
            containing details such as timestamp, operation, UUID, component type,
            component name, and connected bus.

    Returns:
        None
    """

    table = Table(title="Updates applied to the system")
    table.add_column("Timestamp", justify="right", style="cyan", no_wrap=True)
    table.add_column("Operation", style="magenta")
    table.add_column("UUID", justify="right", style="bright_magenta")
    table.add_column("Component Type", justify="right", style="cyan")
    table.add_column("Component Name", justify="right", style="green")
    table.add_column("Connected bus", justify="right", style="bright_red")
    table.add_column("Scenario", justify="right", style="turquoise2")
    for log in update_log:
        table.add_row(*log)

    console = Console()
    console.print(table)
    return
