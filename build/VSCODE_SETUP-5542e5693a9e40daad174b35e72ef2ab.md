# Using Grid Data Models MCP Server with VS Code

This guide explains how to use the Grid Data Models MCP server with GitHub Copilot Agent Mode in VS Code.

## Prerequisites

1. **VS Code**: Latest version with GitHub Copilot extension
2. **GitHub Copilot**: Active subscription with Agent Mode support
3. **Package Installed**: `grid-data-models` must be installed (the MCP server is included)

## Setup

### 1. Install the Package

```bash
pip install grid-data-models
```

Or for development from source:

```bash
git clone https://github.com/NLR-Distribution-Suite/grid-data-models.git
cd grid-data-models
pip install -e ".[dev]"
```

### 2. Verify Installation

```bash
which gdm-mcp-server
gdm-mcp-server --help
```

> **Note:** If you're using conda or a virtual environment, note the full path (e.g., `/opt/homebrew/Caskroom/miniconda/base/envs/gdm/bin/gdm-mcp-server`). VS Code may not activate your environment, so using the full path is recommended.

### 3. Configure VS Code

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

Set `GDM_REPO_PATH` to the local clone of the grid-data-models repository (used for documentation search).

### 4. Start the Server

- Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`)
- Run **MCP: List Servers**
- Select `gridDataModels` and click **Start**
- Check the **Output** panel (dropdown: `MCP: gridDataModels`) for any errors

Alternatively, you should see **Start** code lenses directly in the `mcp.json` file.

### 5. Verify MCP Server Integration

After starting:
1. Open Copilot Chat (`Cmd+Shift+I` / `Ctrl+Shift+I`)
2. Switch to **Agent** mode using the dropdown at the top of the chat panel
3. Click the **Tools** icon (wrench) in the chat input area
4. Verify the server's 20 tools are listed and enabled

## Usage

Once configured, Copilot Agent Mode automatically selects the appropriate GDM tools based on your prompts. You can also reference a specific tool by typing `#` followed by the tool name (e.g., `#get_system_summary`).

### Example Prompts

**Validation & Diagnostics:**
```
Diagnose the system in model.json for validation errors

Suggest fixes for the validation errors in my system

Apply automatic fixes to resolve validation issues
```

**System Operations:**
```
Merge system1.json and system2.json into combined.json

Split the system in large_model.json by substation

Split the system by feeders
```

**Inspection & Analysis:**
```
Give me a summary of the components in system.json

Query all transformers in the SUBSTATION_1 substation

Analyze the topology and check for connectivity issues

Find orphaned components in my system
```

**Documentation & Learning:**
```
Search the documentation for time series examples

Show me the API reference for DistributionBus

What fields are required for DistributionLoad?

Give me code examples for creating a transformer
```

## Available Tools

The MCP server exposes 20 tools:

### Validation (3 tools)
- `diagnose_system` — Identify validation errors
- `suggest_fixes` — Get fix suggestions
- `apply_fixes` — Auto-apply fixes

### Operations (3 tools)
- `merge_systems` — Merge multiple systems
- `split_by_substation` — Split by substation
- `split_by_feeder` — Split by feeder

### Inspection (7 tools)
- `get_system_summary` — Component counts and overview
- `query_components` — Filter and query components
- `analyze_topology` — Network topology analysis
- `get_component_details` — Detailed component info
- `validate_connectivity` — Check reachability
- `find_orphaned_components` — Find unassigned components
- `get_component_relationships` — Parent/child relationships

### Utilities (2 tools)
- `export_subsystem_by_buses` — Extract subsystem
- `get_time_series_summary` — Time series overview

### Documentation (5 tools)
- `search_gdm_documentation` — Search docs
- `get_api_reference` — API reference
- `get_code_examples` — Usage examples
- `list_available_components` — List components
- `get_component_fields` — Field information

## Troubleshooting

### Server Not Connecting

1. Check the command exists:
   ```bash
   which gdm-mcp-server
   ```

2. Test the server manually:
   ```bash
   gdm-mcp-server
   ```

3. Check VS Code output panel:
   - Open Command Palette (`Cmd+Shift+P`)
   - Select **View: Toggle Output**
   - Choose **MCP: gridDataModels** from dropdown

### Server Crashes

Check logs in VS Code:
1. Open Command Palette
2. **Developer: Show Logs**
3. Look for MCP-related errors

### Tools Not Available

1. Verify package is installed:
   ```bash
   python -c "from gdm.mcp import __version__; print(__version__)"
   ```

2. Reinstall if needed:
   ```bash
   pip install --force-reinstall -e ".[dev]"
   ```

### Documentation Search Returns No Results

Set the correct repository path in your `.vscode/mcp.json`:

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

Or set the environment variable directly:
```bash
export GDM_REPO_PATH="/path/to/grid-data-models"
```

## Tips

1. **Use Agent Mode**: Switch to Agent mode in the Copilot Chat dropdown to enable tool usage
2. **Reference Tools**: Type `#tool_name` to explicitly invoke a specific tool
3. **Be Specific**: Include file paths and specific component names in your prompts
4. **Iterative Workflow**: Break complex tasks into multiple prompts
5. **Reference Files**: Use file paths relative to workspace root

## Examples

### Complete Workflow

```
User: I have a system file at tests/data/system.json.
      Can you diagnose it for validation errors?

Copilot: [Uses diagnose_system tool]
         Found 5 validation errors:
         1. Bus 'bus_1' missing voltage
         2. Transformer 'xfmr_1' has invalid winding configuration
         ...

User: Can you suggest fixes for these errors?

Copilot: [Uses suggest_fixes tool]
         Suggestions for fixing validation errors:
         1. Bus 'bus_1': Set voltage to 12.47 kV (common distribution voltage)
         ...

User: Apply the high-confidence fixes automatically

Copilot: [Uses apply_fixes tool]
         Applied 3 fixes successfully. 2 low-confidence fixes skipped.
```

## Configuration Options

### Environment Variables

Set in `.vscode/mcp.json` under `env`:

- `GDM_REPO_PATH`: Path to grid-data-models repository (for documentation search)

### Debug Logging

Pass `--log-level debug` for verbose logging:

```json
{
  "servers": {
    "gridDataModels": {
      "type": "stdio",
      "command": "gdm-mcp-server",
      "args": ["--log-level", "DEBUG"],
      "env": {
        "GDM_REPO_PATH": "/path/to/grid-data-models"
      }
    }
  }
}
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/NLR-Distribution-Suite/grid-data-models/issues
- Documentation: https://github.com/NLR-Distribution-Suite/grid-data-models

## Notes

- MCP server support via GitHub Copilot Agent Mode
- Requires GitHub Copilot subscription
- Server runs locally and processes files on your machine
- No data is sent to external servers except standard Copilot API calls
