from enum import Enum
from pathlib import Path
import shutil
from typing import Annotated

import typer

from gdm.systems.distribution.model_reduction.reducer import reduce_to_three_phase_system
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.exceptions import FolderAlreadyExistsError


class ReducerType(str, Enum):
    three_phase = "three_phase"


def reduce(
    gdm_file: Annotated[str, typer.Option("-g", "--gdm-file", help="GDM system JSON file path.")],
    target_file: Annotated[
        str, typer.Option("-t", "--target-file", help="Target GDM system JSON file path.")
    ],
    force: Annotated[
        bool,
        typer.Option(
            "-f", "--force", help="Force delete the target GDM system file if already exists."
        ),
    ] = False,
    reducer: Annotated[
        ReducerType, typer.Option("-r", "--reducer", help="Reducer type to apply.")
    ] = ReducerType.three_phase,
    time_series: Annotated[
        bool,
        typer.Option(
            "-ts", "--time-series", help="Include time series data in the reduced system."
        ),
    ] = False,
):
    """Reduce a GDM distribution system."""
    target_path = Path(target_file)
    if force and target_path.exists():
        shutil.rmtree(target_path.parent / f"{target_path.stem}_time_series")
        target_path.unlink()

    if not force and target_path.exists():
        raise FolderAlreadyExistsError(
            f"{target_path} already exists. Consider deleting it first."
        )
    sys = DistributionSystem.from_json(gdm_file)
    reducer_func = {"three_phase": reduce_to_three_phase_system}
    new_sys_name = sys.name + "_reduced" if sys.name else None
    new_sys = reducer_func[reducer.value](sys, new_sys_name, time_series)
    new_sys.to_json(target_path)
    typer.echo(str(target_path))
