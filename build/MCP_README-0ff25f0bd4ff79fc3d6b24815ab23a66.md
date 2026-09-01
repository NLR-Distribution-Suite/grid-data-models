# Grid Data Models MCP Server

MCP (Model Context Protocol) server integration for [grid-data-models](https://github.com/NLR-Distribution-Suite/grid-data-models).

## Overview

This package provides an MCP server that exposes grid-data-models functionality as tools for AI agents and assistants. It enables validation error fixing, system merging/disaggregation, inspection, and utility operations on distribution power system models. The server also provides documentation search and API reference capabilities to help answer questions about the grid-data-models library itself.

## Features

- **Validation Tools**: Diagnose validation errors, suggest fixes, and apply automatic corrections
- **System Operations**: Merge multiple distribution systems, split systems by substation or feeder
- **Inspection Tools**: Query components, analyze topology, get system summaries, find orphaned components, explore relationships
- **Utility Tools**: Export subsystems, manage time series
- **Documentation/Knowledge**: Search GDM docs, get API references, view code examples

## Installation

```bash
pip install grid-data-models
```

For development:
```bash
git clone https://github.com/NLR-Distribution-Suite/grid-data-models.git
cd grid-data-models
pip install -e ".[dev]"
```

## Quick Start

### Using with VS Code GitHub Copilot Agent Mode

GitHub Copilot in VS Code supports MCP servers through Agent Mode. Follow these steps to set up the server:

#### 1. Install the package

```bash
pip install grid-data-models
```

Verify the server command is available:

```bash
which gdm-mcp-server
```

> **Note:** If you're using conda or a virtual environment, note the full path to the executable (e.g., `/opt/homebrew/Caskroom/miniconda/base/envs/gdm/bin/gdm-mcp-server`). VS Code may not activate your environment, so using the full path is recommended.

#### 2. Create the MCP configuration file

Create a `.vscode/mcp.json` file in your workspace root:

```json
{
  "servers": {
    "gridDataModels": {
      "type": "stdio",
      "command": "gdm-mcp-server",
      "env": {
        "GDM_REPO_PATH": "/path/to/grid-data-models"
      }
    }
  }
}
```

> **Tip:** If VS Code can't find the command, replace `"gdm-mcp-server"` with the full path to the executable.

Set `GDM_REPO_PATH` to the local clone of the [grid-data-models](https://github.com/NLR-Distribution-Suite/grid-data-models) repository (used for documentation search).

#### 3. Start the server

- Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`)
- Run **MCP: List Servers**
- Select `gridDataModels` and click **Start**
- Check the **Output** panel (dropdown: `MCP: gridDataModels`) for any errors

Alternatively, you should see **Start** code lenses directly in the `mcp.json` file.

#### 4. Use tools in Copilot Chat

1. Open Copilot Chat (`Cmd+Shift+I` / `Ctrl+Shift+I`)
2. Switch to **Agent** mode using the dropdown at the top of the chat panel
3. Click the **Tools** icon (wrench) in the chat input area to verify the server's 22 tools are listed and enabled
4. Ask questions naturally — the agent automatically selects the right tools:
   - *"Get a summary of the system in /path/to/model.json"*
   - *"Diagnose validation errors in system.json and suggest fixes"*
   - *"What fields does DistributionBus have?"*
   - *"Show me code examples for working with time series"*
5. To reference a specific tool, type `#` followed by the tool name (e.g., `#get_system_summary`)

See [VSCODE_SETUP.md](VSCODE_SETUP.md) for more detailed examples.

### Using with Claude Desktop

MCP servers are also supported in Claude Desktop. Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "gdm": {
      "command": "gdm-mcp-server",
      "args": []
    }
  }
}
```

Restart Claude Desktop and the assistant will have access to all 22 GDM tools.

### Starting the MCP Server Standalone

Run the server directly:

```bash
gdm-mcp-server
```

Or with custom host/port:

```bash
gdm-mcp-server --host localhost --port 8000
```

### Using with Other MCP Clients

Any MCP-compatible client can connect to the server. The server exposes 22 tools for working with distribution power system models.

## Runtime Tool Toggle

The server supports runtime enable/disable for non-control tool calls. This is useful when you want a UI switch (or policy gate) without restarting the server.

- `set_tool_calls_enabled` toggles non-control tools on/off.
- `get_tool_calls_enabled` returns current toggle state.
- Control tools remain callable even when all other tools are disabled.

Example payloads:

```json
{"enabled": false}
```

```json
{"enabled": true}
```

You can also set the startup default from CLI:

```bash
gdm-mcp-server --tool-calls-disabled
```

```bash
gdm-mcp-server --tool-calls-enabled
```

## model_ref Interoperability

Path-based tools now support either legacy `system_path` or a `model_ref`
object, enabling compatibility with persisted model registries.

### model_ref shape

```json
{
  "model_id": "abc123def456",
  "version": 2
}
```

Direct path-carrying references are also valid:

```json
{
  "stored_path": "/abs/path/to/system.json"
}
```

### Resolution behavior

Resolution order:

1. `stored_path`
2. `path`
3. `source_path`
4. Registry lookup by `model_id` / `version`

Registry lookup uses:

- `model_ref.registry_db` if provided
- otherwise environment variable `DIST_STACK_MODEL_REGISTRY_DB`

### Backward compatibility

Existing clients using `system_path` continue to work unchanged.

### Example payloads

Legacy:

```json
{
  "system_path": "/abs/path/to/system.json"
}
```

Registry-backed:

```json
{
  "model_ref": {
    "model_id": "abc123def456",
    "version": 2
  }
}
```

## Available Tools

### Validation (3 tools)
- `diagnose_system` — Identify validation errors in a distribution system
- `suggest_fixes` — Get fix suggestions for validation errors
- `apply_fixes` — Automatically apply fixes to resolve validation errors

### System Operations (3 tools)
- `merge_systems` — Merge multiple distribution systems into one
- `split_by_substation` — Disaggregate system into subsystems by substation
- `split_by_feeder` — Disaggregate system into subsystems by feeder

### Inspection (7 tools)
- `get_system_summary` — Get component counts and overview
- `query_components` — Filter and query components by type, substation, feeder, phases, etc.
- `analyze_topology` — Analyze network topology and connectivity
- `get_component_details` — Get detailed information about a component
- `validate_connectivity` — Check if all components are reachable from source
- `find_orphaned_components` — Find components without substation/feeder assignment
- `get_component_relationships` — Get parent/child relationships for a component

### Utilities (2 tools)
- `export_subsystem_by_buses` — Extract subsystem by bus list
- `get_time_series_summary` — Get overview of time series data

### Documentation / Knowledge (5 tools)
- `search_gdm_documentation` — Search grid-data-models documentation for relevant content
- `get_api_reference` — Get API reference for a specific component class
- `get_code_examples` — Get code examples for specific topics
- `list_available_components` — List all available distribution component types
- `get_component_fields` — Get detailed field information for a component type

### Server Control (2 tools)
- `set_tool_calls_enabled` — Enable or disable non-control tool calls at runtime
- `get_tool_calls_enabled` — Get current tool-call enablement state

## Example Usage

### Validating and Fixing a System

```python
# Through MCP client (e.g., Claude or Copilot)
"Diagnose the system in model.json and apply automatic fixes"
```

### Merging Systems

```python
# Through MCP client
"Merge system1.json and system2.json into combined_system.json"
```

### Splitting by Feeder

```python
# Through MCP client
"Split the system in large_model.json into separate systems for each feeder"
```

### Getting Documentation and API Information

```python
# Through MCP client
"How do I create a DistributionBus?"
"Show me code examples for working with time series"
"What fields does DistributionLoad have?"
```

## Compatibility

- **Python**: >=3.11
- **grid-data-models**: >=0.1.0
- **MCP Protocol**: >=1.0.0

## Development

Run tests:
```bash
pytest tests/
```

Run linting:
```bash
ruff check src/
```

## License

BSD 3-Clause License. See [LICENSE.txt](../../LICENSE.txt) for details.

## Contributing

Contributions welcome! Please open an issue or pull request on GitHub.

## Support

For issues and questions:
- GitHub Issues: https://github.com/NLR-Distribution-Suite/grid-data-models/issues
- Documentation: https://github.com/NLR-Distribution-Suite/grid-data-models

## Citation

If you use this software in your research, please cite:

```bibtex
@software{grid_data_models_mcp,
  title = {Grid Data Models MCP Server},
  author = {Latif, Aadil and Duwadi, Kapil},
  year = {2026},
  organization = {National Renewable Energy Laboratory}
}
```
