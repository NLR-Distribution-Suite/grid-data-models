"""Diagnostic tools for identifying validation errors in distribution systems."""

import contextlib
import traceback
from typing import Any
from uuid import UUID

from gdm.systems.distribution import DistributionSystem
from pydantic import ValidationError as PydanticValidationError

from gdm.mcp.schemas import (
    ErrorType,
    ValidationIssue,
    ValidationReport,
)


def _collect_check_issues(
    raw_issues: list[dict],
    component_uuid: UUID,
    component_type: str,
    component_name: str,
    error_type: ErrorType,
) -> list[ValidationIssue]:
    """Convert raw check results into ValidationIssue objects."""
    return [
        ValidationIssue(
            component_uuid=component_uuid,
            component_type=component_type,
            component_name=component_name,
            field_path=issue["field"],
            error_type=error_type,
            message=issue["message"],
            current_value=issue.get("current"),
            expected_value=issue.get("expected"),
        )
        for issue in raw_issues
    ]


def _diagnose_component(
    component: Any,
    component_uuid: UUID,
    component_type: str,
    component_name: str,
) -> list[ValidationIssue]:
    """Run all checks on a single component and return issues."""
    issues: list[ValidationIssue] = []

    checks = [
        (_check_phase_consistency, ErrorType.PHASE_MISMATCH),
        (_check_matrix_dimensions, ErrorType.MATRIX_DIMENSION),
        (_check_array_lengths, ErrorType.ARRAY_LENGTH),
    ]

    for check_fn, error_type in checks:
        raw = check_fn(component)
        if raw:
            issues.extend(
                _collect_check_issues(
                    raw, component_uuid, component_type, component_name, error_type
                )
            )

    return issues


def diagnose_system(system: DistributionSystem) -> ValidationReport:
    """
    Diagnose a distribution system for validation errors.

    Args:
        system: DistributionSystem to diagnose

    Returns:
        ValidationReport with all identified issues
    """
    issues: list[ValidationIssue] = []
    total_components = 0
    valid_components = 0

    for component in system.iter_all_components():
        total_components += 1
        component_uuid = (
            component.uuid if isinstance(component.uuid, UUID) else UUID(component.uuid)
        )
        component_type = component.__class__.__name__
        component_name = component.name

        try:
            comp_issues = _diagnose_component(
                component, component_uuid, component_type, component_name
            )
            if comp_issues:
                issues.extend(comp_issues)
            else:
                valid_components += 1

        except PydanticValidationError as e:
            for error in e.errors():
                issues.append(
                    ValidationIssue(
                        component_uuid=component_uuid,
                        component_type=component_type,
                        component_name=component_name,
                        field_path=".".join(str(loc) for loc in error["loc"]),
                        error_type=ErrorType.PYDANTIC_VALIDATION,
                        message=error["msg"],
                        current_value=error.get("input"),
                    )
                )
        except Exception as e:
            issues.append(
                ValidationIssue(
                    component_uuid=component_uuid,
                    component_type=component_type,
                    component_name=component_name,
                    field_path="unknown",
                    error_type=ErrorType.OTHER,
                    message=f"Unexpected error: {str(e)}\n{traceback.format_exc()}",
                )
            )

    return ValidationReport(
        system_name=system.name,
        total_components=total_components,
        valid_components=valid_components,
        invalid_components=total_components - valid_components,
        issues=issues,
    )


def _check_bus_phase_consistency(component_phases, bus, field_prefix: str) -> list[dict]:
    """Check if component phases are a subset of a single bus's phases."""
    if not hasattr(bus, "phases") or bus.phases is None:
        return []
    if not set(component_phases).issubset(set(bus.phases)):
        return [
            {
                "field": f"{field_prefix}phases",
                "message": f"Component phases {component_phases} not subset of bus phases {bus.phases}",
                "current": component_phases,
                "expected": bus.phases,
            }
        ]
    return []


def _check_buses_phase_consistency(component_phases, buses) -> list[dict]:
    """Check phase consistency against a list of buses."""
    issues = []
    for i, bus in enumerate(buses):
        if hasattr(bus, "phases") and bus.phases is not None:
            if not set(component_phases).issubset(set(bus.phases)):
                issues.append(
                    {
                        "field": f"buses[{i}].phases",
                        "message": f"Component phases {component_phases} not compatible with bus[{i}] phases {bus.phases}",
                        "current": component_phases,
                        "expected": bus.phases,
                    }
                )
    return issues


def _check_equipment_phase_loads(component_phases, equipment) -> list[dict]:
    """Check equipment phase_loads length matches component phases."""
    if not hasattr(equipment, "phase_loads") or not equipment.phase_loads:
        return []
    if len(component_phases) != len(equipment.phase_loads):
        return [
            {
                "field": "equipment.phase_loads",
                "message": f"Number of phases {len(component_phases)} doesn't match phase_loads count {len(equipment.phase_loads)}",
                "current": len(equipment.phase_loads),
                "expected": len(component_phases),
            }
        ]
    return []


def _check_phase_consistency(component: Any) -> list[dict]:
    """Check for phase consistency issues in a component."""
    if not hasattr(component, "phases"):
        return []

    component_phases = getattr(component, "phases", None)
    if component_phases is None:
        return []

    issues = []

    if hasattr(component, "bus") and component.bus is not None:
        issues.extend(_check_bus_phase_consistency(component_phases, component.bus, ""))

    if hasattr(component, "buses") and component.buses:
        issues.extend(_check_buses_phase_consistency(component_phases, component.buses))

    if hasattr(component, "equipment") and component.equipment is not None:
        issues.extend(_check_equipment_phase_loads(component_phases, component.equipment))

    return issues


def _check_matrix_dimensions(component: Any) -> list[dict]:
    """Check for matrix dimension issues in component equipment."""
    issues = []

    if not hasattr(component, "equipment") or component.equipment is None:
        return issues

    equipment = component.equipment
    if not hasattr(component, "phases") or component.phases is None:
        return issues

    expected_size = len(component.phases)

    # Check impedance matrices
    matrix_attrs = [
        "r_matrix",
        "x_matrix",
        "c_matrix",
        "impedance_matrix",
        "admittance_matrix",
    ]

    for attr in matrix_attrs:
        if hasattr(equipment, attr):
            matrix = getattr(equipment, attr)
            if matrix is not None:
                with contextlib.suppress(Exception):
                    # Check if it's a list of lists (matrix)
                    if isinstance(matrix, list) and len(matrix) > 0:
                        if isinstance(matrix[0], list):
                            rows = len(matrix)
                            cols = len(matrix[0]) if matrix else 0
                            if rows != expected_size or cols != expected_size:
                                issues.append(
                                    {
                                        "field": f"equipment.{attr}",
                                        "message": f"Matrix dimensions ({rows}x{cols}) don't match phase count ({expected_size}x{expected_size})",
                                        "current": f"{rows}x{cols}",
                                        "expected": f"{expected_size}x{expected_size}",
                                    }
                                )

    return issues


def _check_array_lengths(component: Any) -> list[dict]:
    """Check for array length consistency issues."""
    issues = []

    if not hasattr(component, "phases") or component.phases is None:
        return issues

    expected_length = len(component.phases)

    # Check for per-phase attributes that should match phase count
    per_phase_attrs = ["is_closed", "winding_phases"]

    for attr in per_phase_attrs:
        if hasattr(component, attr):
            value = getattr(component, attr)
            if value is not None and isinstance(value, list):
                if len(value) != expected_length:
                    issues.append(
                        {
                            "field": attr,
                            "message": f"Array length {len(value)} doesn't match phase count {expected_length}",
                            "current": len(value),
                            "expected": expected_length,
                        }
                    )

    return issues
