# Technology Stack

**Analysis Date:** 2026-03-18

## Languages

**Primary:**
- Python 3.12+ - CLI, TUI, backend services, core business logic

**Secondary:**
- YAML - Connection profiles and configuration files
- CSV - Data export format for alarm/event logs

## Runtime

**Environment:**
- Python 3.12+ (specified in `pyproject.toml`)
- Unix/Linux/Windows compatible

**Package Manager:**
- UV (Python package manager and build backend)
  - Build backend: `uv_build>=0.9.4,<0.10.0`
  - Lockfile: `uv.lock` (present)
  - All dependency management via `pyproject.toml`

## Frameworks

**Core:**
- `asyncua>=1.1.8` - OPC UA client library, async protocol implementation, node browsing
- `textual>=0.87.1` - Terminal UI framework for TUI dashboard, widgets, event handling
- `pyyaml>=6.0` - Configuration parsing for connection profiles

**Testing:**
- `pytest>=9.0.2` - Test runner, assertions, fixtures (dev dependency)

**Build/Dev:**
- `uv_build` - Modern Python build backend replacing setuptools

## Key Dependencies

**Critical:**
- `asyncua` - OPC UA protocol implementation; handles connection, subscription, browsing, security modes
- `textual` - Terminal UI engine; provides app, widgets, bindings, message system for TUI

**Infrastructure:**
- `pyyaml` - Profile/config deserialization, supports nested structures for logging config
- `pytest` - Test execution framework for unit/integration tests

## Configuration

**Environment:**
- Runtime config via `src/opcua_client/.env` (package defaults)
- CLI argument overrides via `argparse`
- Per-connection YAML profiles in `connections/` or `~/.config/opcua-client/connections/`
- Configuration precedence: CLI args > connection profile YAML > `.env` defaults > code fallback

**Build:**
- `pyproject.toml` - Single source of truth for dependencies, metadata, scripts
- No setup.py, no requirements.txt (all in pyproject.toml)

**Entry Point:**
- `collectua` command defined in `[project.scripts]` → `opcua_client:main`

## Platform Requirements

**Development:**
- Python 3.12+ runtime
- UV installed for dependency management
- POSIX shell or Windows PowerShell for scripting (see `justfile`)

**Production:**
- Python 3.12+ runtime
- Internet connectivity to OPC UA servers (TCP port varies by server)
- Optional: certificate files for secure connections (`certs/` directory)
- Optional: writable `logs/debug/` directory for debug logging

## External Service Integration

**OPC UA Servers:**
- Targets industrial PLCs with OPC UA endpoints
- Siemens S7-1500 explicitly supported and tested
- Security modes: None (insecure), Sign, SignAndEncrypt
- Auto-profile setup probes server capabilities and generates profiles

**File System:**
- Reads/writes connection profiles: `connections/`, `~/.config/opcua-client/connections/`
- Writes alarm CSV exports to configurable path (default: `alarms.csv`)
- Manages client certificates in `certs/` directory
- Debug logs to `logs/debug/` when enabled

---

*Stack analysis: 2026-03-18*
