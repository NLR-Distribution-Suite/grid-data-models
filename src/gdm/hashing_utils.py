from copy import deepcopy
from typing import TYPE_CHECKING
from uuid import UUID

from infrasys import Component, SupplementalAttribute
from pydantic import BaseModel

if TYPE_CHECKING:
    from gdm.systems.distribution.distribution_system import DistributionSystem


def _remove_keys_from_dict(model_dict: dict, key_names: list[str] = ["name", "uuid"]) -> dict:
    """Method recursively removes keys from the model

    Args:
        model_dict (dict): model in dict representation
        key_names (list[str]): keys to remove from the model

    Returns:
        dict: reduced model dictionary
    """
    for key_name in key_names:
        if key_name in model_dict:
            model_dict.pop(key_name)
        for k, v in model_dict.items():
            if isinstance(v, dict):
                model_dict[k] = _remove_keys_from_dict(v)
            elif isinstance(v, list):
                values = []
                for value in v:
                    if isinstance(value, dict):
                        value = _remove_keys_from_dict(value)
                    values.append(value)
                    model_dict[k] = values
    return model_dict


def hash_model(model: Component, key_names: list[str] = ["name", "uuid"]) -> int:
    """Return hash of the passed model

    Args:
        model (Component): Instance of a derived infrasys Component model
        key_names (list[str], optional): List of keys to be removed from the model. Defaults to ["name", "uuid"].

    Returns:
        int: model hash
    """
    model_dict = (
        model.model_dump()
    )  # TODO: exclude={"name"} seems not to work  well with list of objects
    cleaned_model = _remove_keys_from_dict(model_dict, key_names)
    return hash(str(cleaned_model))


def _referenced_components(components: list[Component]) -> set[UUID]:
    stored = {component.uuid: component for component in components}

    def is_equipment(component: Component) -> bool:
        return any(
            cls.__module__.startswith("gdm.systems.distribution.equipment.")
            for cls in type(component).__mro__
        )

    retained = set()
    visited = set()
    pending = [component for component in components if not is_equipment(component)]
    while pending:
        value = pending.pop()
        if isinstance(value, Component):
            if value.uuid not in stored:
                raise ValueError(
                    f"Referenced component {value.label} is not stored in the system."
                )
            if stored[value.uuid] is not value:
                raise ValueError(f"Referenced component {value.label} is not the stored instance.")
            retained.add(value.uuid)
        if isinstance(value, BaseModel):
            if id(value) in visited:
                continue
            visited.add(id(value))
            pending.extend(getattr(value, field) for field in type(value).model_fields)
        elif isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            pending.extend(value)
    return retained


def remove_unreferenced_equipment(system: "DistributionSystem") -> "DistributionSystem":
    """Return an independent copy without equipment unused by non-equipment components.

    Equipment referenced through other equipment is retained. Supplemental attributes
    and time series belonging exclusively to removed equipment are omitted.
    """
    components = list(system.iter_all_components())
    retained = _referenced_components(components)
    kept_components = [component for component in components if component.uuid in retained]
    attributes = {
        attribute.uuid: attribute
        for component in kept_components
        for attribute in system.get_supplemental_attributes_with_component(component)
    }
    for attribute in system.get_supplemental_attributes(SupplementalAttribute):
        if not system.get_components_with_supplemental_attribute(attribute):
            raise ValueError(f"Cannot copy unattached supplemental attribute {attribute.label}.")
    copied_components, copied_attributes = deepcopy((kept_components, attributes))
    copies = {component.uuid: component for component in copied_components}

    result = type(system)(
        name=system.name,
        description=system.description,
        uuid=system.uuid,
        auto_add_composed_components=True,
    )
    if system.data_format_version is not None:
        result.data_format_version = system.data_format_version
    result.deserialize_system_attributes(deepcopy(system.serialize_system_attributes()))
    for component in copied_components:
        if not result.has_component(component):
            result.add_component(component)
    result.auto_add_composed_components = system.auto_add_composed_components
    result.rebuild_component_associations()

    for component in kept_components:
        for attribute in system.get_supplemental_attributes_with_component(component):
            result.add_supplemental_attribute(
                copies[component.uuid], copied_attributes[attribute.uuid]
            )

    owners = [(component, copies[component.uuid]) for component in kept_components]
    owners.extend((attribute, copied_attributes[uuid]) for uuid, attribute in attributes.items())
    for original, copy in owners:
        for metadata in system.time_series.metadata_store.list_metadata(original):
            data = system.time_series.storage.get_time_series(metadata)
            result.add_time_series(data, copy, **metadata.features)
    return result
