# OPC UA Client

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)

An OPC UA client with a CLI and an interactive TUI for browsing, connecting to, and collecting data from OPC UA servers.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/).

```bash
uv tool install opcua-client
```

Or run directly without installing:

```bash
uvx opcua-client --help
```

## CLI — `opcua-client`

```
opcua-client [--connection-profile NAME] [--mode prod|debug] <command> [options]
```

| Command | What it does |
|---|---|
| `browse` | Browse the OPC UA node tree of a server |
| `collect` | Subscribe to alarms/events and write them to a CSV file |
| `connect` | Smoke-test a connection (plain or secure) |
| `config` | Show or validate the resolved runtime configuration |
| `list-profiles` | List available connection profiles |

Connection profiles (YAML files) live in `./connections/` or `~/.config/opcua-client/connections/`.

**Examples**

```bash
# Browse a server
opcua-client browse --url opc.tcp://localhost:4840

# Collect alarms to a CSV
opcua-client collect --url opc.tcp://localhost:4840 --csv-file alarms.csv

# Test a secure connection
opcua-client connect --url opc.tcp://localhost:4840 \
  --security-policy Basic256Sha256 \
  --cert-file my-certs/client-cert.pem \
  --key-file my-certs/client-key.pem

# Use a saved profile
opcua-client --connection-profile myserver browse
```

## TUI — `opcua-tui`

An interactive terminal UI (htop-style) for live server exploration.

```bash
opcua-tui --url opc.tcp://localhost:4840
# or with a saved profile
opcua-tui --connection-profile myserver
```

Key bindings:

| Key | Action |
|---|---|
| `F1` | Help |
| `Tab` / `Shift-Tab` | Move between panels |
| `Enter` / `→` | Expand node / focus right |
| `←` | Collapse node / focus left |
| `r` | Reconnect |
| `q` / `F10` | Quit |
