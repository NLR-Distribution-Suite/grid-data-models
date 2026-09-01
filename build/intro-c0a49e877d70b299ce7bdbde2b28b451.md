# Intro to Grid-Data-Models
GDM is a Python package containing data models for distribution system assets and datasets. This package is actively being developed at [National Renewable Energy Laboratory (NREL)](https://www.nrel.gov/).

## Why Grid Data Models?

To reduce code duplication and provide client packages with a standard interface to interact with power system data, a group of research engineers at NREL is developing standard data models. Features include:

- **Built-in Validation Layer:** The use of [pydantic](https://docs.pydantic.dev/latest/) allows for the validation of model fields.
- **Time Series Data Management:** GDM uses the [infrasys](https://github.com/NREL/infrasys) package, enabling [efficient time series data management](https://natlabrockies.github.io/infrasys/explanation/time_series.html) by sharing arrays across components and offloading system memory. For example, time series power consumption data can be attached to a load profile.
- **Built-in Unit Conversion:** GDM leverages [pint](https://pint.readthedocs.io/en/stable/) for unit conversion of power system quantities, such as power, voltage, and time.
- **JSON Serialization/Deserialization:** GDM uses [infrasys](https://github.com/NREL/infrasys) to serialize and deserialize distribution system components to/from JSON.
- **Track System Changes:** Supports tracking changes within a distribution model (both temporal and scenario-based static updates), enabling powerful scenario management capabilities.
- **Graph-Based Analysis:** Exposes a connectivity graph using NetworkX, allowing advanced graph-based algorithms and visualizations.
- **Model Reduction:** Built-in support for multiple model reduction algorithms.
- **Interoperability:** Easily integrates with existing tools.

## The GDM Ecosystem

- **Grid-Data-Models:** Foundational models for distribution system analysis.
- **Shift:** Builds synthetic distribution models in GDM format.
- **DiTto:** Model conversion framework, refactored with GDM models now representing DiTto core.
- **ERAD:** Resilience analysis of distribution systems, taking in hazard models and GDM models as input.
- **Cadet-OPT / Cadet-MDAO:** Distribution system optimization frameworks.
- **GridAI:** Builds training datasets for PyTorch for generative AI applications from GDM base models.
- **GridDB:** Distribution asset cost database, currently being built, will map to GDM equipment models.
- **DistLLM:** LLM interface for the entire distribution suite ecosystem.

<!-- ## Table of Content

```{tableofcontents}
``` -->
## License

BSD 3-Clause License

Copyright (c) 2024, Alliance for Sustainable Energy, LLC
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.