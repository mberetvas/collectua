# OPC UA Client

[![Build Status](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/workflows/CI/badge.svg)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions)
[![Coverage](https://img.shields.io/codecov/c/github/{{GITHUB_ORG}}/{{GITHUB_REPO}})](https://codecov.io/gh/{{GITHUB_ORG}}/{{GITHUB_REPO}})
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/opcua-client)](https://pypi.org/project/opcua-client/)

**A high-performance, feature-rich OPC UA client for browsing, connecting to, and collecting data from OPC UA servers with both CLI and interactive TUI modes.**

## Project Status

### Current Release: v0.1.0 (March 2026)

**Status:** Early Stage / Alpha

This project is in active development. The core functionality is stable and ready for testing, but breaking changes may occur before v1.0.0.

### Roadmap

- ✅ **v0.1.0** - Initial release
  - CLI interface with four core commands
  - Basic OPC UA server connectivity and browsing
  - Alarm/event collection and CSV export
  - Interactive Textual-based TUI for live monitoring and node inspection
  - Production and debug runtime modes
  
- 🔄 **v0.2.0** (Planned)
  - Enhanced data visualization
  - Batch operations and scripting support
  - Configuration file support (YAML/TOML)

- 📋 **v0.3.0** (Planned)
  - Advanced filtering and query capabilities
  - Historical data export
  - Performance profiling tools
  - Cloud integration (HTTP/REST gateway)

- 🎯 **v1.0.0** (Target)
  - Stable API and CLI interface
  - Comprehensive test coverage (>80%)
  - Complete documentation with examples
  - Docker support

## Prerequisites

### System Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| **Operating System** | Linux, macOS 12+, Windows 10/11 | All modern OSes supported |
| **Python** | 3.12 or later | 3.12.x recommended for optimal performance |
| **Memory** | 512 MB minimum | 2 GB recommended for large OPC UA server trees |
| **Disk Space** | 100 MB | For installation and debug logs |

### Required Dependencies

- **asyncua** (≥1.1.8) – OPC UA protocol implementation
- **textual** (≥0.87.1) – TUI framework for interactive mode

### Optional Dependencies

- **OPC UA Server** – Your own instance or test server (for testing connectivity)
- **SSL/TLS Certificates** – For secure connections

### Package Managers

- **UV** (≥0.9.4) – Recommended for dependency management and execution
  - Install: https://docs.astral.sh/uv/getting-started/
- **pip/pip3** – Standard Python package manager (v21.0+ recommended)
- **venv** – Python built-in virtual environment tool

### Development Tools (Optional)

- **Git** (≥2.30) – for cloning and version control
- **pytest** (≥7.0) – for running the test suite
- **ruff** (≥0.1.0) – for code linting and formatting

## Installation

### Quick Install (Linux/macOS)

Using UV (recommended):

```bash
uv pip install opcua-client
```

Or via pip:

```bash
pip install opcua-client
```

### Installation from Source (All Platforms)

#### Linux/macOS

```bash
# Clone the repository
git clone https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}.git
cd opcua-client

# Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies using UV (recommended)
uv sync

# Or install with pip
pip install -e .
```

#### Windows (PowerShell)

```powershell
# Clone the repository
git clone https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}.git
cd opcua-client

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies using UV (recommended)
uv sync

# Or install with pip
pip install -e .
```

#### Windows (Command Prompt)

```cmd
REM Clone the repository
git clone https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}.git
cd opcua-client

REM Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

REM Install dependencies using UV (recommended)
uv sync

REM Or install with pip
pip install -e .
```

### Verify Installation

```bash
# Check CLI installation
opcua-client --version
opcua-client --help

# Check TUI installation
opcua-tui --help
```

## Quickstart

### ⚠️ Important: OPC UA URL is Required

All commands require an explicit `--url` argument pointing to your OPC UA server. There are no hardcoded defaults for security and correctness reasons.

```bash
# Format: opc.tcp://hostname:port
export OPC_URL="opc.tcp://your-server.example.com:4840"
```

### Basic Connection Test

Test connectivity to an OPC UA server:

```bash
# Using UV (recommended)
uv run opcua-client connect --url opc.tcp://localhost:4840

# Or using installed package
opcua-client connect --url opc.tcp://localhost:4840
```

### Browse OPC UA Node Tree

```bash
# Browse server nodes starting from root
opcua-client browse \
  --url opc.tcp://localhost:4840 \
  --max-depth 3

# With authentication
opcua-client browse \
  --url opc.tcp://localhost:4840 \
  --username admin \
  --password secret123 \
  --max-depth 4
```

### Collect Alarms to CSV

```bash
# Subscribe to alarms and export to CSV
opcua-client collect \
  --url opc.tcp://localhost:4840 \
  --csv-file alarms.csv
```

### Interactive TUI Mode

```bash
# Launch interactive terminal UI for real-time monitoring
opcua-tui --url opc.tcp://localhost:4840
```

## TUI Overview

The project ships with `opcua-tui`, a full-screen terminal dashboard built with Textual for live monitoring of an OPC UA server.

### What the TUI shows

- **Connection status bar** with endpoint, security mode, reconnect state, and uptime
- **Lazy-loaded node tree** for browsing `Objects` without dumping the whole address space at once
- **Node details panel** showing node metadata and live values for variable nodes
- **Live alarms table** with severity-based highlighting
- **Embedded log stream** for connection, subscription, and runtime diagnostics
- **Runtime config panel** with sensitive values such as passwords masked

### Start the TUI

The TUI **requires** a `--url` argument. Attempting to launch without it will display an error:

```bash
# ERROR: Missing required --url argument
opcua-tui
# Error: the following arguments are required: --url

# CORRECT: Always provide the OPC UA server URL
opcua-tui --url opc.tcp://localhost:4840
```

**Examples:**

```bash
# Basic launch
opcua-tui --url opc.tcp://localhost:4840

# Debug mode with verbose logging
opcua-tui --mode debug --log-level DEBUG --url opc.tcp://localhost:4840

# Filter browsing to specific namespace indexes
opcua-tui --url opc.tcp://localhost:4840 --target-namespace 3 4 --max-depth 4

# Connect with username/password auth
opcua-tui --url opc.tcp://localhost:4840 --username myuser --password mypass

# Connect with certificate-based security
opcua-tui \
  --url opc.tcp://localhost:4840 \
  --auth-policy Basic256Sha256 \
  --security-mode SignAndEncrypt \
  --cert-file my-certs/opcua_certs/own/certs/MyOPCUAClient.der \
  --key-file my-certs/opcua_certs/own/private/MyOPCUAClient_key.pem
```

### TUI keyboard shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Focus the next panel |
| `↑` / `↓` | Move to previous or next sibling node in the tree |
| `→` | Expand the current node or move into its first child |
| `←` | Collapse the current node or move to its parent |
| `F6` | Toggle between **Live Alarms** and **Node Info** |
| `Shift+F6` | Jump directly to **Live Alarms** |
| `F5` | Reconnect to the OPC UA server |
| `F9` | Show or hide the runtime config panel |
| `F1` | Open the in-app help screen |
| `F10` / `q` | Quit the TUI |

### TUI notes

- The dashboard is **read-only**; it does not write values back to the server.
- Alarm events are still appended to `alarms.csv` while the TUI is running.
- Variable values are read on selection, so the node details panel updates as you move through the tree.
- When browsing large servers, the tree expands lazily to keep the interface responsive.

## Configuration

### Command-Line Arguments

All commands, including the TUI, require the `--url` argument:

| Argument | CLI | TUI | Required | Description |
|----------|-----|-----|----------|-------------|
| `--url` | ✅ | ✅ | **YES** | OPC UA endpoint URL (e.g., `opc.tcp://server:4840`) |
| `--timeout` | ✅ | ✅ | No | Socket timeout in seconds (default: 30) |
| `--username` | ✅ | ✅ | No | Username for user/password authentication |
| `--password` | ✅ | ✅ | No | Password for user/password authentication |
| `--auth-policy` | ✅ | ✅ | No | Security policy: `None`, `Basic128Rsa15`, `Basic256`, `Basic256Sha256` (default: `None`) |
| `--security-mode` | ✅ | ✅ | No | Security mode: `None_`, `Sign`, `SignAndEncrypt` (default: `None_`) |
| `--cert-file` | ✅ | ✅ | No | Path to client certificate for secure connections |
| `--key-file` | ✅ | ✅ | No | Path to client private key for secure connections |
| `--max-depth` | ✅ | ✅ | No | Maximum depth for node tree browsing (default: 3) |
| `--target-namespace` | ✅ | ✅ | No | Namespace index filter for browsing (space-separated) |
| `--csv-file` | ✅ (collect) | ✅ | No | Output CSV file path for alarm collection (default: `alarms.csv`) |
| `--mode` | ✅ | ✅ | No | Runtime mode: `prod`, `debug` (default: `prod`) |
| `--log-level` | ✅ | ✅ | No | Console logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |

### Creating Shell Aliases (Optional)

For convenience, create aliases to avoid typing the URL repeatedly:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias opcua-prod='opcua-client --url opc.tcp://prod-server.internal:4840'
alias opcua-dev='opcua-client --url opc.tcp://dev-server.internal:4840'
alias opcua-tui-prod='opcua-tui --url opc.tcp://prod-server.internal:4840'

# Now use:
opcua-prod connect
opcua-dev browse --max-depth 2
opcua-tui-prod  # Opens TUI connected to prod server
```

### Example .env File

Create a `.env` file in your project root:

```bash
# .env
OPCUA_CLIENT_LOG_LEVEL=INFO
OPCUA_CLIENT_MODE=production
OPCUA_SERVER_URL=opc.tcp://my-server.example.com:4840
OPCUA_USERNAME=serviceaccount
OPCUA_CONNECTION_TIMEOUT=30
OPCUA_OUTPUT_FORMAT=csv
```

Load environment variables:

```bash
# On Linux/macOS
export $(cat .env | xargs)

# On Windows PowerShell
Get-Content .env | ForEach-Object {
  $key, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($key, $value)
}
```

### Configuration File (Planned)

Future versions will support YAML/TOML configuration files. Placeholder path:

```bash
~/.config/opcua-client/config.yaml
```

## CLI Reference

### Commands Overview

#### `opcua-client browse`

Browse the OPC UA node tree from a server.

```bash
opcua-client browse [OPTIONS]

Options:
  --server-url TEXT              OPC UA server URL [default: opc.tcp://localhost:4840]
  --depth INTEGER                Browsing depth [default: 2]
  --username TEXT                Username for authentication
  --password TEXT                Password for authentication
  --protocol [SECURE_CERTIFICATE|SECURE_USERNAME|INSECURE]
                                 Security protocol [default: INSECURE]
  --output-file TEXT            Save output to file (JSON format)
  --verbose                     Enable verbose output
  --help                        Show this help message
```

#### `opcua-client collect`

Subscribe to alarms/events and export to CSV.

```bash
opcua-client collect [OPTIONS]

Options:
  --server-url TEXT              OPC UA server URL [default: opc.tcp://localhost:4840]
  --output-file TEXT            CSV file path [required]
  --interval-ms INTEGER         Collection interval in ms [default: 5000]
  --timeout-sec INTEGER         Timeout in seconds [default: 300]
  --username TEXT               Username for authentication
  --password TEXT               Password for authentication
  --protocol [SECURE_CERTIFICATE|SECURE_USERNAME|INSECURE]
                                Security protocol [default: INSECURE]
  --help                        Show this help message
```

#### `opcua-client connect`

Test connectivity to an OPC UA server.

```bash
opcua-client connect [OPTIONS]

Options:
  --server-url TEXT              OPC UA server URL [default: opc.tcp://localhost:4840]
  --username TEXT               Username for authentication
  --password TEXT               Password for authentication
  --protocol [SECURE_CERTIFICATE|SECURE_USERNAME|INSECURE]
                                Security protocol [default: INSECURE]
  --timeout-sec INTEGER         Connection timeout in seconds [default: 10]
  --verbose                     Enable verbose output
  --help                        Show this help message
```

#### `opcua-client config`

Display or validate runtime configuration.

```bash
opcua-client config [OPTIONS]

Options:
  --validate                    Validate current configuration
  --show-env                    Show environment variables
  --help                        Show this help message
```

For the latest command details:

```bash
opcua-client --help
opcua-client <command> --help
opcua-tui --help
```

### `opcua-tui`

Launch the interactive terminal dashboard.

```bash
opcua-tui [OPTIONS]

Options:
  --mode [prod|debug]                          Runtime mode [default: prod]
  --log-level [DEBUG|INFO|WARNING|ERROR]      Console logging level [default: INFO]
  --debug-log-dir TEXT                        Directory for debug log files [default: logs/debug]
  --url TEXT                                  OPC UA endpoint URL
                                               [default: opc.tcp://10.205.139.4:4840]
  --timeout FLOAT                             Socket timeout in seconds [default: 30.0]
  --session-timeout INTEGER                   Session timeout in milliseconds [default: 60000]
  --request-timeout INTEGER                   Request timeout in milliseconds [default: 20000]
  --username TEXT                             Username for user/password auth
  --password TEXT                             Password for user/password auth
  --auth-policy [None|Basic128Rsa15|Basic256|Basic256Sha256]
                                               Security policy [default: None]
  --security-mode [None_|Sign|SignAndEncrypt] Security mode [default: None_]
  --cert-file TEXT                            Client certificate path
  --key-file TEXT                             Client private key path
  --max-depth INTEGER                         Browse depth [default: 3]
  --target-namespace INTEGER [INTEGER ...]    Optional namespace filter
  --csv-file TEXT                             Alarm/event CSV output path [default: alarms.csv]
  --publish-interval-ms INTEGER               Subscription publish interval [default: 500]
  --reconnect-delay-sec INTEGER               Reconnect delay in seconds [default: 5]
  --help                                      Show this help message
```

## Testing

### Run All Tests

Using UV:

```bash
uv run pytest tests/
```

Or with pip environment:

```bash
pytest tests/
```

### Run Specific Test Suite

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires OPC UA server)
pytest tests/integration/

# Only browse command tests
pytest tests/ -k browse

# Verbose output with output capture disabled
pytest tests/ -vv -s
```

### Test With Coverage Report

```bash
# Generate coverage report
pytest tests/ --cov=opcua_client --cov-report=html

# View coverage report
open htmlcov/index.html          # macOS
xdg-open htmlcov/index.html      # Linux
start htmlcov\index.html         # Windows
```

### Example Test Output

```
tests/test_cli.py::test_connect_success PASSED                    [ 20%]
tests/test_cli.py::test_browse_with_depth PASSED                  [ 40%]
tests/test_collector.py::test_alarm_collection PASSED             [ 60%]
tests/test_config.py::test_config_validation PASSED               [ 80%]
tests/integration/test_server_connection.py::test_live_server SKIPPED [ 100%]

========================== 4 passed, 1 skipped in 2.34s ==========================
```

## CI/CD

### Build Status

[![Build Status](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/workflows/CI/badge.svg)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions)
[![Python Tests](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/workflows/tests.yml/badge.svg)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions/workflows/tests.yml)
[![Code Quality](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/workflows/lint.yml/badge.svg)](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/actions/workflows/lint.yml)

### GitHub Actions Workflow

Below is a sample CI/CD workflow (`.github/workflows/ci.yml`):

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ ubuntu-latest, macos-latest, windows-latest ]
        python-version: [ '3.12', '3.13' ]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install UV
      run: |
        pip install uv

    - name: Sync dependencies
      run: |
        uv sync

    - name: Lint with ruff
      run: |
        uv run ruff check .

    - name: Run tests
      run: |
        uv run pytest tests/ -v --cov=opcua_client

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

### Local CI Simulation

Run locally before pushing:

```bash
# Run all checks (lint + tests)
uv run ruff check .
uv run pytest tests/ --cov=opcua_client

# Format code
uv run ruff format .
```

## Contributing

We welcome contributions from the community! This project follows a collaborative development model.

### Contribution Workflow

1. **Fork the repository**
   - Click "Fork" on GitHub to create your personal copy

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/{{GITHUB_REPO}}.git
   cd opcua-client
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or for bug fixes:
   git checkout -b fix/your-bug-fix
   ```

4. **Make your changes**
   - Follow the code conventions in [CONTRIBUTING.md](./CONTRIBUTING.md)
   - Ensure your code matches the project style (see Code Style below)
   - Write or update tests for new functionality

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```
   - Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

6. **Test locally**
   ```bash
   uv sync
   uv run pytest tests/
   uv run ruff check .
   ```

7. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Open a Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your branch and provide a clear description
   - Reference any related issues: `Closes #123`

9. **Respond to review comments**
   - Make requested changes to your branch
   - Push updates (no need to create new PR)
   - CI/CD checks must pass before merge

### Code Style

This project enforces code quality through automated tools:

- **Formatting:** `ruff format` (automatic)
- **Linting:** `ruff check` (must pass before merge)
- **Type hints:** Required on all functions (Python 3.12+ style)
- **Docstrings:** Google-style format for all public functions

Before submitting, run:

```bash
uv run ruff format .          # Auto-format code
uv run ruff check .            # Check for linting issues
```

### Testing Requirements

All contributions must include tests:

- **Unit tests:** For isolated functions and classes
- **Integration tests:** For multi-component workflows
- **Minimum coverage:** New code should maintain >80% coverage

```bash
# Run tests with coverage
uv run pytest tests/ --cov=opcua_client --cov-report=term-missing
```

### Documentation Updates

- Update [CHANGELOG.md](./CHANGELOG.md) with your changes
- Update [README.md](./README.md) if you modify user-facing features
- Add docstrings to all new public functions
- See [copilot-instructions.md](./copilot-instructions.md) for documentation standards

### Guidelines

- Read [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) – we're committed to a welcoming community
- See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed contribution guidelines
- Start small with bug fixes or documentation improvements
- Discuss major features in an issue before starting work

## License

This project is licensed under the **{{LICENSE_NAME}}** License – see the [LICENSE](./LICENSE) file for details.

**In short:** [Brief summary of license permissions and restrictions. Example: "You are free to use, modify, and distribute this software in personal and commercial projects."]

## Support & Contact

### Getting Help

- **Documentation:** See [docs/](./docs/) directory for detailed guides
- **API Reference:** Run `opcua-client --help` or `opcua-tui --help`
- **Issue Tracker:** [GitHub Issues](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/issues)
- **Discussions:** [GitHub Discussions](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/discussions) for questions

### Reporting Bugs

Please report bugs on [GitHub Issues](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/issues) with:

- OPC UA Client version: `opcua-client --version`
- Python version: `python --version`
- Operating System and version
- Steps to reproduce
- Actual vs. expected behavior
- Relevant logs or error messages

### Feature Requests

Submit feature requests as [GitHub Issues](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/issues) with the `enhancement` label.

### Contact

- **Maintainers:** [{{MAINTAINER_EMAIL}}](mailto:{{MAINTAINER_EMAIL}})
- **Repository:** [github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}})
- **Issues & Questions:** [GitHub Issues](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/issues)

### Community

- Join the community discussions
- Share your use cases and projects
- Help answer questions from other users

---

## Additional Resources

- [OPC UA Specification](https://opcfoundation.org/developer-tools/specifications-unified-architecture/)
- [asyncua Documentation](https://asyncua.readthedocs.io/)
- [Textual Documentation](https://textual.textualize.io/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**Made with ❤️ by the OPC UA Client community**
