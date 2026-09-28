"""Auto-fixer for applying validation error fixes."""

import copy
from datetime import datetime
from typing import Any

from gdm.systems.distribution import DistributionSystem

from gdm.mcp.schemas import (
    ChangeLogEntry,
    FixResult,
    FixStrategy,
    FixSuggestion,
    ValidationIssue,
)
from gdm.mcp.validation.diagnostics import diagnose_system


def apply_fixes(
    system: DistributionSystem,
    suggestions: list[FixSuggestion],
    auto_approve: bool = False,
) -> tuple[DistributionSystem, FixResult]:
    """
    Apply fixes to a distribution system.

    Args:
        system: DistributionSystem to fix
        suggestions: List of FixSuggestion to apply
        auto_approve: If False, only apply high-confidence fixes

    Returns:
        Tuple of (fixed_system, FixResult)
    """
    # Create a deep copy to avoid modifying original
    try:
        fixed_system = system.deepcopy()
    except Exception as e:
        return system, FixResult(
            success=False,
            fixes_applied=0,
            fixes_failed=len(suggestions),
            error_message=f"Failed to create system copy: {str(e)}",
        )

    change_log: list[ChangeLogEntry] = []
    fixes_applied = 0
    fixes_failed = 0
    failed_issues: list[ValidationIssue] = []

    for suggestion in suggestions:
        # Skip low-confidence fixes unless auto_approve is True
        if not auto_approve and suggestion.confidence.value == "low":
            fixes_failed += 1
            failed_issues.append(suggestion.issue)
            continue

        try:
            # Get the component by UUID
            component = fixed_system.get_component_by_uuid(str(suggestion.issue.component_uuid))
            if component is None:
                fixes_failed += 1
                failed_issues.append(suggestion.issue)
                continue

            # Apply the fix based on strategy
            if suggestion.strategy == FixStrategy.ALIGN_PHASES:
                success = _apply_phase_fix(component, suggestion, change_log)
            elif suggestion.strategy == FixStrategy.RESIZE_MATRIX:
                success = _apply_matrix_fix(component, suggestion, change_log)
            elif suggestion.strategy == FixStrategy.ADJUST_ARRAY_LENGTH:
                success = _apply_array_fix(component, suggestion, change_log)
            else:
                success = False

            if success:
                fixes_applied += 1
            else:
                fixes_failed += 1
                failed_issues.append(suggestion.issue)

        except Exception:
            fixes_failed += 1
            failed_issues.append(suggestion.issue)

    # Re-validate the fixed system
    validation_report = diagnose_system(fixed_system)

    return fixed_system, FixResult(
        success=validation_report.is_valid,
        fixes_applied=fixes_applied,
        fixes_failed=fixes_failed,
        change_log=change_log,
        remaining_issues=validation_report.issues if not validation_report.is_valid else [],
    )


def _apply_phase_fix(
    component: Any, suggestion: FixSuggestion, change_log: list[ChangeLogEntry]
) -> bool:
    """Apply phase alignment fix."""
    try:
        field_path = suggestion.issue.field_path
        new_phases = suggestion.parameters.get("new_phases")
        old_phases = getattr(component, "phases", None)

        if new_phases is None or old_phases is None:
            return False

        # Update component phases
        setattr(component, "phases", new_phases)

        # Log the change
        change_log.append(
            ChangeLogEntry(
                component_uuid=suggestion.issue.component_uuid,
                component_type=suggestion.issue.component_type,
                component_name=suggestion.issue.component_name,
                field_path=field_path,
                old_value=old_phases,
                new_value=new_phases,
                fix_strategy=FixStrategy.ALIGN_PHASES,
                timestamp=datetime.now().isoformat(),
            )
        )

        # Also update equipment phase_loads if present
        if hasattr(component, "equipment") and component.equipment is not None:
            equipment = component.equipment
            if hasattr(equipment, "phase_loads") and equipment.phase_loads:
                old_phase_loads = equipment.phase_loads
                # Adjust phase_loads to match new phase count
                new_count = len(new_phases)
                if len(old_phase_loads) > new_count:
                    equipment.phase_loads = old_phase_loads[:new_count]
                elif len(old_phase_loads) < new_count:
                    # Pad with copies of the last element or default
                    while len(equipment.phase_loads) < new_count:
                        equipment.phase_loads.append(copy.deepcopy(old_phase_loads[-1]))

        return True
    except Exception:
        return False


def _apply_matrix_fix(
    component: Any, suggestion: FixSuggestion, change_log: list[ChangeLogEntry]
) -> bool:
    """Apply matrix dimension fix."""
    try:
        field_path = suggestion.issue.field_path
        expected_dim_str = suggestion.parameters.get("expected_dimensions", "")

        # Parse expected dimensions
        if "x" in str(expected_dim_str):
            expected_size = int(str(expected_dim_str).split("x")[0])
        else:
            return False

        # Navigate to the matrix field
        parts = field_path.split(".")
        obj = component
        for part in parts[:-1]:
            obj = getattr(obj, part)

        matrix_attr = parts[-1]
        matrix = getattr(obj, matrix_attr)

        if matrix is None or not isinstance(matrix, list):
            return False

        old_matrix = copy.deepcopy(matrix)

        # Resize matrix
        new_matrix = _resize_matrix(matrix, expected_size)
        setattr(obj, matrix_attr, new_matrix)

        # Log the change
        change_log.append(
            ChangeLogEntry(
                component_uuid=suggestion.issue.component_uuid,
                component_type=suggestion.issue.component_type,
                component_name=suggestion.issue.component_name,
                field_path=field_path,
                old_value=f"{len(old_matrix)}x{len(old_matrix[0]) if old_matrix else 0}",
                new_value=f"{expected_size}x{expected_size}",
                fix_strategy=FixStrategy.RESIZE_MATRIX,
                timestamp=datetime.now().isoformat(),
            )
        )

        return True
    except Exception:
        return False


def _apply_array_fix(
    component: Any, suggestion: FixSuggestion, change_log: list[ChangeLogEntry]
) -> bool:
    """Apply array length fix."""
    try:
        field_path = suggestion.issue.field_path
        expected_length = suggestion.parameters.get("expected_length")

        if expected_length is None:
            return False

        # Get the array
        if "." in field_path:
            parts = field_path.split(".")
            obj = component
            for part in parts[:-1]:
                obj = getattr(obj, part)
            array_attr = parts[-1]
        else:
            obj = component
            array_attr = field_path

        array = getattr(obj, array_attr)
        if not isinstance(array, list):
            return False

        old_length = len(array)

        # Resize array
        if old_length > expected_length:
            # Truncate
            new_array = array[:expected_length]
        else:
            # Pad with default values
            new_array = array.copy()
            default_value = array[-1] if array else False  # Use last element or False
            while len(new_array) < expected_length:
                new_array.append(copy.deepcopy(default_value))

        setattr(obj, array_attr, new_array)

        # Log the change
        change_log.append(
            ChangeLogEntry(
                component_uuid=suggestion.issue.component_uuid,
                component_type=suggestion.issue.component_type,
                component_name=suggestion.issue.component_name,
                field_path=field_path,
                old_value=old_length,
                new_value=expected_length,
                fix_strategy=FixStrategy.ADJUST_ARRAY_LENGTH,
                timestamp=datetime.now().isoformat(),
            )
        )

        return True
    except Exception:
        return False


def _resize_matrix(matrix: list[list], target_size: int) -> list[list]:
    """Resize a matrix to target dimensions."""
    current_rows = len(matrix)
    current_cols = len(matrix[0]) if matrix else 0

    # Create new matrix with target dimensions
    new_matrix = []

    for i in range(target_size):
        row = []
        for j in range(target_size):
            if i < current_rows and j < current_cols:
                # Copy existing value
                row.append(matrix[i][j])
            else:
                # Pad with zero (or identity for diagonal)
                row.append(1.0 if i == j else 0.0)
        new_matrix.append(row)

    return new_matrix
