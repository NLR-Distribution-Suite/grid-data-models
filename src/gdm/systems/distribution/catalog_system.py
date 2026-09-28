import importlib.metadata

from infrasys import System


class CatalogSystem(System):
    """Class interface for catalog system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_format_version = importlib.metadata.version("grid-data-models")
