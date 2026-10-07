"""Generate standalone HTML schematics for the documentation gallery."""

from pathlib import Path

from gdm.systems.substation import (
    SubstationLayout,
    build_layout_example,
    build_reference_design,
)


def main() -> None:
    output_path = Path("docs/_build/html/reference_designs")
    output_path.mkdir(parents=True, exist_ok=True)

    for layout in SubstationLayout:
        build_layout_example(layout).plot_schematic(export_path=output_path, show=False)

    build_reference_design("detailed_distribution").plot_schematic(
        export_path=output_path,
        show=False,
    )


if __name__ == "__main__":
    main()
