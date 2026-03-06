# OPC UA Client CLI

A command-line client for OPC UA operations with built-in logging and runtime mode management.

## Installation

### Using UV (Recommended)

```bash
uv sync
```

Then run commands using:

```bash
uv run opcua-client --help
uv run opcua-client config
uv run opcua-tui --help
```

### Using pip

```bash
pip install -e .
```

Then run commands directly:

```bash
opcua-client --help
opcua-client config
opcua-tui --help
```

## TUI Dashboard (htop/btop-inspired)

This project also provides a full-screen terminal dashboard:

- command: `opcua-tui`
- style: multi-panel, keyboard-driven interface inspired by htop/btop
- panels: connection status, node tree, live alarms table, runtime config, and logs

### TUI Usage

```bash
# With uv
uv run opcua-tui --url opc.tcp://localhost:4840

# With pip-installed script
opcua-tui --url opc.tcp://localhost:4840
```

### TUI Keybindings

- `Tab`: focus next panel
- `F1`: help overlay
- `F5`: reconnect
- `F9`: toggle config panel
- `F10` or `q`: quit

## Usage

The CLI can run in two modes: **production** (default) and **debug**.

### Running with UV

All command examples below use `uv run`. If you installed with pip, omit `uv run`:

```bash
# With uv:
uv run opcua-client browse --url opc.tcp://example.com:4840

# With pip (direct command):
opcua-client browse --url opc.tcp://example.com:4840
```

### Production Mode (Default)

Production mode is the default runtime mode. Console output is concise at INFO level, with errors and warnings prominently displayed:

```bash
# Default: production mode, INFO level
opcua-client browse --url opc.tcp://example.com:4840

# Explicitly specify production mode
opcua-client --mode prod collect --csv-file output.csv

# Override console log level in prod mode (e.g., to see DEBUG details)
opcua-client --log-level DEBUG connect --url opc.tcp://example.com:4840
```

### Debug Mode

Debug mode is designed for troubleshooting and development:
- Console output remains concise (INFO level by default)
- A separate **per-run debug log file** is created automatically
- Debug log files capture all DEBUG-level messages and stack traces
- Files are stored in `logs/debug/` (configurable)
- Each run generates a unique filename: `debug-YYYYMMDD-HHMMSS-pidNNNN.log`

```bash
# Enable debug mode (creates a new debug log file for this run)
opcua-client --mode debug collect --csv-file output.csv

# Debug mode with custom log directory
opcua-client --mode debug --debug-log-dir /var/log/opcua-client browse --url opc.tcp://example.com:4840

# Override console level in debug mode
opcua-client --mode debug --log-level DEBUG connect --url opc.tcp://example.com:4840
```

#### Debug Log Files

When running in debug mode, the CLI will print the path to the debug log file:

```
[cli] Debug log: logs/debug/debug-20260306-143022-pid12345.log
```

Debug log files contain detailed diagnostic information and are useful for:
- Investigating connection failures
- Understanding authentication issues
- Tracking down performance problems
- Reviewing full request/response traces

### Available Commands

- **browse**: Browse the OPC UA node tree
- **collect**: Subscribe to alarms/events and write to CSV
- **connect**: Test connectivity (smoke test)
- **config**: Show or validate the runtime configuration

### Logging Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `prod` | Runtime mode: `prod` or `debug` |
| `--log-level` | `INFO` | Console log level (overrides mode defaults) |
| `--debug-log-dir` | `logs/debug` | Directory for debug log files (debug mode only) |

### Examples

#### Browse OPC UA tree in production
```bash
opcua-client browse --url opc.tcp://localhost:4840 --max-depth 5
```

#### Collect alarms with debug logging
```bash
opcua-client --mode debug collect \
  --url opc.tcp://localhost:4840 \
  --csv-file /tmp/alarms.csv \
  --publish-interval-ms 500
```

#### Test connection with verbose console output
```bash
opcua-client --log-level DEBUG connect \
  --url opc.tcp://localhost:4840 \
  --username myuser \
  --password mypass
```

#### Show and validate configuration
```bash
opcua-client config --url opc.tcp://localhost:4840 --action show
opcua-client config --action validate
```

## Configuration

All CLI options can be specified as command-line arguments. See help for details:

```bash
opcua-client --help
opcua-client browse --help
opcua-client collect --help
opcua-client connect --help
opcua-client config --help
```

## Debug Workflow

When investigating an issue:

1. **First run**: Use production mode initially to see concise output
   ```bash
   opcua-client --log-level WARNING collect --csv-file output.csv
   ```

2. **If issue occurs**: Re-run in debug mode to capture full diagnostic info
   ```bash
   opcua-client --mode debug collect --csv-file output.csv
   ```

3. **Review debug log**: Examine the generated log file for detailed traces and errors
   ```bash
   cat logs/debug/debug-20260306-143022-pid12345.log
   ```

4. **Clean up logs** (optional): Debug log files accumulate over time—remove old ones as needed
   ```bash
   find logs/debug -mtime +7 -delete  # remove logs older than 7 days
   ```
