"""Documentation search and retrieval for grid-data-models."""

import contextlib
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import inspect

from gdm.systems.distribution.components import (
    DistributionBus,
    DistributionSubstation,
    DistributionFeeder,
    DistributionLoad,
    DistributionTransformer,
    DistributionCapacitor,
    DistributionSolar,
    DistributionBattery,
    DistributionRegulator,
    DistributionVoltageSource,
    MatrixImpedanceBranch,
    MatrixImpedanceSwitch,
    MatrixImpedanceFuse,
    MatrixImpedanceRecloser,
)

from ..schemas import (
    DocumentationSearchResult,
    APIReferenceResult,
    CodeExample,
    ComponentInfoBasic,
)


# Map of component names to classes
COMPONENT_MAP = {
    "DistributionBus": DistributionBus,
    "MatrixImpedanceBranch": MatrixImpedanceBranch,
    "DistributionLoad": DistributionLoad,
    "DistributionTransformer": DistributionTransformer,
    "DistributionCapacitor": DistributionCapacitor,
    "DistributionSolar": DistributionSolar,
    "DistributionBattery": DistributionBattery,
    "DistributionSubstation": DistributionSubstation,
    "DistributionFeeder": DistributionFeeder,
    "MatrixImpedanceSwitch": MatrixImpedanceSwitch,
    "MatrixImpedanceFuse": MatrixImpedanceFuse,
    "MatrixImpedanceRecloser": MatrixImpedanceRecloser,
    "DistributionRegulator": DistributionRegulator,
    "DistributionVoltageSource": DistributionVoltageSource,
}


def find_gdm_repo() -> Optional[Path]:
    """Find the grid-data-models repository."""
    # Common locations to check
    possible_paths = [
        Path.cwd().parent / "grid-data-models",  # Sibling directory
        Path.cwd() / ".." / "grid-data-models",  # Relative sibling
        Path(__file__).resolve().parents[4],  # This checkout's repository root
        Path.home() / "Documents" / "GitHub" / "grid-data-models",
        Path.home() / "Documents" / "grid-data-models",
        Path.home() / "grid-data-models",
    ]

    # Also check GDM_REPO_PATH environment variable
    env_path = os.getenv("GDM_REPO_PATH")
    if env_path:
        possible_paths.insert(0, Path(env_path))

    for path in possible_paths:
        resolved_path = path.resolve()
        if resolved_path.exists() and (resolved_path / "docs").exists():
            return resolved_path

    return None


def _search_md_files(docs_dir: Path, gdm_repo: Path, query_lower: str) -> list:
    """Search markdown files for query matches."""
    results = []
    for file_path in docs_dir.rglob("*.md"):
        with contextlib.suppress(Exception):
            content = file_path.read_text(encoding="utf-8")
            title = file_path.stem.replace("_", " ").title()
            content_lower = content.lower()

            matches = content_lower.count(query_lower)
            title_matches = title.lower().count(query_lower)
            score = matches + (title_matches * 5)

            if score > 0:
                snippet = _extract_snippet(content, content_lower, query_lower)
                results.append(
                    DocumentationSearchResult(
                        title=title,
                        file_path=str(file_path.relative_to(gdm_repo)),
                        content=snippet,
                        relevance_score=float(score),
                    )
                )
    return results


def _search_notebooks(docs_dir: Path, gdm_repo: Path, query_lower: str) -> list:
    """Search notebook files for query matches."""
    import json

    results = []
    for file_path in docs_dir.rglob("*.ipynb"):
        with contextlib.suppress(Exception):
            notebook = json.loads(file_path.read_text(encoding="utf-8"))
            text_content = []
            for cell in notebook.get("cells", []):
                if cell.get("cell_type") in ["markdown", "code"]:
                    source = cell.get("source", [])
                    text_content.append("".join(source) if isinstance(source, list) else source)

            content = "\n".join(text_content)
            content_lower = content.lower()
            matches = content_lower.count(query_lower)

            if matches > 0:
                title = file_path.stem.replace("_", " ").title()
                snippet = _extract_snippet(content, content_lower, query_lower)
                results.append(
                    DocumentationSearchResult(
                        title=f"{title} (Notebook)",
                        file_path=str(file_path.relative_to(gdm_repo)),
                        content=snippet,
                        relevance_score=float(matches),
                    )
                )
    return results


def _extract_snippet(content: str, content_lower: str, query_lower: str) -> str:
    """Extract a relevant text snippet around the first match of query."""
    match_pos = content_lower.find(query_lower)
    if match_pos >= 0:
        start = max(0, match_pos - 150)
        end = min(len(content), match_pos + 300)
        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
    else:
        snippet = content[:300] + "..."
    return snippet


def search_documentation(query: str, max_results: int = 5) -> List[DocumentationSearchResult]:
    """
    Search grid-data-models documentation for relevant content.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of documentation search results
    """
    gdm_repo = find_gdm_repo()
    if not gdm_repo:
        return [
            DocumentationSearchResult(
                title="Repository Not Found",
                file_path="",
                content="Could not locate grid-data-models repository",
                relevance_score=0.0,
            )
        ]

    docs_dir = gdm_repo / "docs"
    query_lower = query.lower()

    results = _search_md_files(docs_dir, gdm_repo, query_lower)
    results.extend(_search_notebooks(docs_dir, gdm_repo, query_lower))

    # Sort by relevance and limit results
    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return results[:max_results]


def get_api_reference(component_name: str) -> APIReferenceResult:
    """
    Get API reference for a specific component or class.

    Args:
        component_name: Name of the component class (e.g., "DistributionBus")

    Returns:
        API reference information
    """
    if component_name not in COMPONENT_MAP:
        return APIReferenceResult(
            component_name=component_name,
            description=f"Component '{component_name}' not found",
            fields=[],
            methods=[],
            examples=[],
        )

    component_class = COMPONENT_MAP[component_name]

    # Get docstring
    description = inspect.getdoc(component_class) or "No description available"

    # Get fields from model
    fields = []
    if hasattr(component_class, "model_fields"):
        for field_name, field_info in component_class.model_fields.items():
            field_type = str(field_info.annotation) if hasattr(field_info, "annotation") else "Any"
            field_desc = field_info.description if hasattr(field_info, "description") else ""
            is_required = field_info.is_required() if hasattr(field_info, "is_required") else True

            fields.append(
                {
                    "name": field_name,
                    "type": field_type,
                    "description": field_desc or "",
                    "required": is_required,
                }
            )

    # Get methods
    methods = []
    for name, method in inspect.getmembers(component_class, predicate=inspect.isfunction):
        if not name.startswith("_"):
            method_doc = inspect.getdoc(method) or "No description"
            sig = str(inspect.signature(method))
            methods.append({"name": name, "signature": f"{name}{sig}", "description": method_doc})

    # Get examples from documentation
    examples = []
    gdm_repo = find_gdm_repo()
    if gdm_repo:
        # Look for component-specific documentation
        component_file = component_name.lower().replace("distribution", "distribution_")
        docs_dir = gdm_repo / "docs" / "api" / "components"
        if (docs_dir / f"{component_file}.md").exists():
            examples.append(f"See: docs/api/components/{component_file}.md")

    return APIReferenceResult(
        component_name=component_name,
        description=description,
        fields=fields,
        methods=methods,
        examples=examples,
    )


def get_code_examples(topic: str) -> List[CodeExample]:
    """
    Get code examples for a specific topic.

    Args:
        topic: Topic to search for (e.g., "creating a bus", "time series")

    Returns:
        List of code examples
    """
    gdm_repo = find_gdm_repo()
    if not gdm_repo:
        return []

    examples = []
    docs_dir = gdm_repo / "docs"

    # Search notebooks for code examples
    for notebook_path in docs_dir.rglob("*.ipynb"):
        with contextlib.suppress(Exception):
            import json

            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

            for idx, cell in enumerate(notebook.get("cells", [])):
                if cell.get("cell_type") == "code":
                    source = cell.get("source", [])
                    if isinstance(source, list):
                        code = "".join(source)
                    else:
                        code = source

                    # Check if code is relevant to topic
                    if topic.lower() in code.lower():
                        # Get preceding markdown cell for context
                        description = ""
                        if idx > 0 and notebook["cells"][idx - 1].get("cell_type") == "markdown":
                            desc_source = notebook["cells"][idx - 1].get("source", [])
                            if isinstance(desc_source, list):
                                description = "".join(desc_source)
                            else:
                                description = desc_source

                        examples.append(
                            CodeExample(
                                title=notebook_path.stem.replace("_", " ").title(),
                                code=code,
                                description=description or f"Example from {notebook_path.name}",
                                file_path=str(notebook_path.relative_to(gdm_repo)),
                            )
                        )

    return examples[:10]  # Limit to 10 examples


def list_available_components() -> List[ComponentInfoBasic]:
    """
    List all available distribution components.

    Returns:
        List of component information
    """
    components = []

    for name, cls in COMPONENT_MAP.items():
        doc = inspect.getdoc(cls) or f"{name} component"
        # Get first line of docstring as summary
        summary = doc.split("\n")[0] if doc else f"{name} component"

        components.append(
            ComponentInfoBasic(name=name, description=summary, category="Distribution Component")
        )

    return components


def get_component_fields(component_name: str) -> Dict[str, Any]:
    """
    Get detailed field information for a component.

    Args:
        component_name: Name of the component class

    Returns:
        Dictionary of field information
    """
    if component_name not in COMPONENT_MAP:
        return {"error": f"Component '{component_name}' not found"}

    component_class = COMPONENT_MAP[component_name]
    fields = {}

    if hasattr(component_class, "model_fields"):
        for field_name, field_info in component_class.model_fields.items():
            fields[field_name] = {
                "type": str(field_info.annotation) if hasattr(field_info, "annotation") else "Any",
                "required": field_info.is_required()
                if hasattr(field_info, "is_required")
                else True,
                "description": field_info.description
                if hasattr(field_info, "description")
                else "",
                "default": str(field_info.default)
                if hasattr(field_info, "default") and field_info.default is not None
                else None,
            }

    return fields
