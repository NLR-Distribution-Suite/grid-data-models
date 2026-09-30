

[![Upload to PyPi](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/publish_to_pypi.yml/badge.svg)](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/publish_to_pypi.yml) •  [![Pytest](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/pull_request_tests.yml/badge.svg)](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/pull_request_tests.yml) •  [![deploy-book](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/deploy.yml) • ![PyPI - Downloads](https://img.shields.io/pypi/dm/grid-data-models) •  [![codecov](https://codecov.io/github/NLR-Distribution-Suite/grid-data-models/branch/main/graph/badge.svg?token=K0X11EXOX8)](https://codecov.io/github/NLR-Distribution-Suite/grid-data-models) •  [![CodeFactor](https://www.codefactor.io/repository/github/nlr-distribution-suite/grid-data-models/badge)](https://www.codefactor.io/repository/github/nlr-distribution-suite/grid-data-models) • ![MCP Server](https://img.shields.io/badge/MCP_Server-enabled-brightgreen) • ![MCP Tools](https://img.shields.io/badge/MCP_Tools-20-blue) • [![GitHub issues](https://img.shields.io/github/issues/NLR-Distribution-Suite/grid-data-models)](https://github.com/NLR-Distribution-Suite/grid-data-models/issues) • [![License](https://img.shields.io/github/license/NLR-Distribution-Suite/grid-data-models)](https://github.com/NLR-Distribution-Suite/grid-data-models/blob/main/LICENSE.txt) •  [![PyPI Downloads](https://static.pepy.tech/personalized-badge/grid-data-models?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/grid-data-models) • [![Generate LinkedIn Post Draft](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/linkedin_draft.yml/badge.svg)](https://github.com/NLR-Distribution-Suite/grid-data-models/actions/workflows/linkedin_draft.yml)

# Grid Data Models (GDM)

GDM is a python package containing data models for power system assets and datasets. This package is actively being developed at [National Renewable Energy Laboratory (NREL)](https://www.nrel.gov/).

## Installation

You can install the latest version of `grid-data-models` from PyPi.

```bash
pip install grid-data-models
```

## Why Grid Data Models?

In an effort to reduce code duplication and provide client packages a standard interface to interact with power system data, a group of research engineers at NREL is working on developing standard data models. Features:

- **Built-in validation layer:** Use of [pydantic](https://docs.pydantic.dev/latest/) allows us to validate model fields.
- **Time series data management:** GDM uses [infrasys](https://github.nrel.gov/CADET/infrastructure_systems) package which enables [efficient time series data management](https://nrel.github.io/infrasys/explanation/time_series.html) by sharing arrays across components and offloading system memory. For example, we can attach time series power consumption data to a load profile.
- **Built-in unit conversion:** GDM leverages [pint](https://pint.readthedocs.io/en/stable/) for unit conversion for power system quantities. For example, power, voltage, time, etc.
- **JSON serialization/deserialization:** GDM uses [infrasys](https://github.com/NatLabRockies/infrasys) to serialize and deserialize distribution system components to/from JSON.
- **Track System Changes:** Supports tracking changes within a distribution model (both temporal and scenario-based static updates), enabling powerful scenario management capabilities.
- **Graph-Based Analysis:** Exposes a connectivity graph using NetworkX, allowing advanced graph-based algorithms and visualizations.
- **Interoperability:** Easily integrates with existing tools.
- **Model reduction:** Built-in support for multiple model reduction algorithms.

## How to get started?

To get started, you can clone and pip install this library from [here](https://nrel-distribution-suites.github.io/grid-data-models/).

## Model Context Protocol (MCP) Integration

GDM includes an MCP server that enables AI assistants to interact with power system models through natural language. The MCP integration provides:

- **System inspection and analysis** - Query components, analyze topology, validate connectivity
- **Validation and diagnostics** - Diagnose errors, suggest fixes, and automatically apply corrections
- **System operations** - Merge, split, and extract subsystems
- **Documentation and API access** - Search documentation and get component API references

To install with MCP support:

```bash
pip install -e ".[mcp]"
```

To run the MCP server:

```bash
gdm-mcp-server
```

For more details, see the [MCP documentation](docs/mcp/).


## Contributors

- **Aadil Latif**
- **Daniel Thom**
- **Jeremy Keen**
- **Kapil Duwadi**
- **Tarek Elgindy**
- **Pedro Andres Sanchez Perez**
