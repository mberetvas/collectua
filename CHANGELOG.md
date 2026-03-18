# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **DDD domain and infrastructure foundation** - Added explicit domain and adapter layers for Phase 1 architecture refactor
  - Added domain package: `src/opcua_client/domain/alarm.py`, `src/opcua_client/domain/connection.py`, `src/opcua_client/domain/node.py`, `src/opcua_client/domain/exceptions.py`
  - Added infrastructure package: `src/opcua_client/infrastructure/asyncua_adapter.py`, `src/opcua_client/infrastructure/config_loader.py`, `src/opcua_client/infrastructure/csv_writer.py`, `src/opcua_client/infrastructure/repositories.py`
  - Added focused test coverage for new domain/infrastructure modules under `tests/test_domain_*.py` and `tests/test_infrastructure_*.py`
- **TUI multi-node selection and bulk Node ID copy** - Select multiple nodes in the Node Tree and copy all Node IDs as newline-separated output for bulk operations
  - Added `Ctrl+Space` to toggle selection of the currently focused node in the Node Tree
  - Added `Esc` to clear the current multi-selection set in the Node Tree
  - Updated `Ctrl+Shift+C` to copy all selected Node IDs, with fallback to the currently focused node when no multi-selection exists
  - Added visual selected-row marker (`☑`) in the Node Tree for selected nodes
- **Per-connection logging configuration** - Define logging behavior directly in connection YAML profiles
  - Configure log level per connection: `logging.level: DEBUG|INFO|WARNING|ERROR|CRITICAL`
  - Enable/disable file logging per connection: `logging.file.enabled: true|false`
  - Customize log file path and filename pattern per connection
  - Connection logging settings override global CLI flags (`--log-level`, `--mode`)
  - Useful for debugging specific connections while keeping others in production mode
  - See `connections/example.yaml` for configuration examples
 - **Server certificate trust metadata** - Centralized client certificate with per-profile server trust
  - Connection profiles now store server certificate metadata: `server_cert` and `trust_cert`
  - Client certificate and private key are generated or resolved automatically (no longer configured per profile)
  - On first secure connection when `trust_cert` is false, the CLI collects the server certificate, shows its fingerprint, and prompts the user to trust it
  - When a profile is used, accepting trust writes the collected server certificate next to the profile YAML and persists `trust_cert: true`
  - Connections without a backing profile can still be trusted for the current run, but trust is not persisted
- **TUI Node ID quick copy** - Added a `Copy Node ID` button and `Ctrl+Shift+C` shortcut in Node Info to copy the selected node identifier to the system clipboard

### Changed
- **Architecture documentation now includes DDD layering guidance**
  - Updated `.planning/codebase/ARCHITECTURE.md` with domain/infrastructure layers and dependency direction rules
  - Updated README project structure to reflect new `domain/` and `infrastructure/` directories
- **Centralized package defaults in `src/opcua_client/.env`**
  - Runtime defaults for CLI, TUI, collector, browse depth, logging, certificate paths, and profile directories are now sourced from `src/opcua_client/.env`
  - Configuration precedence is now CLI args > connection profile YAML > `.env` defaults > code fallback
  - Auto-profile setup now reuses `.env` timeout defaults so generated profiles stay aligned with the rest of the app
- **BREAKING: TUI launch method changed** - Use `collectua --tui` instead of separate `opcua-tui` command
  - The `opcua-tui` command has been removed as a separate entry point
  - Instead, use `collectua --tui` to launch the terminal dashboard
  - All TUI flags and options remain the same: `collectua --tui --url opc.tcp://server:4840`
  - `collectua --tui` and `collectua [subcommand]` are mutually exclusive
  - Simplifies the CLI surface and reduces code duplication
  - Shell alias example: `alias opcua-tui='collectua --tui'` for legacy compatibility

### Fixed
- **Explicit secure client certificate paths are now honored**
  - Secure CLI and TUI connections now use configured `cert_file` and `key_file` values when present
  - Auto-generated certificates remain the fallback when explicit paths are not supplied
- **Siemens S7-1500 alarm/event visibility in TUI and collector**
  - Subscriptions now request both `BaseEventType` (general events) and `ConditionType` (Siemens OPC UA Alarms & Conditions) simultaneously
  - Added `where_clause_generation=False` to prevent asyncua from sending a strict EventFilter WhereClause that Siemens S7-1500 OPC UA server rejects, which previously caused all incoming events to be silently dropped
  - `ConditionRefresh` is now invoked correctly on the `ConditionType` node (not the `Server` node) per the OPC UA specification, so the PLC pushes its full active-alarm backlog immediately on subscription
  - Added debug logging of raw incoming event payloads to simplify diagnostics when vendor-specific event fields are missing

## [0.1.1] - 2026-03-09

### Added
- **Connection profiles (YAML)** - Reusable configuration files for OPC UA connections
  - Store profiles in `./connections/` or `~/.config/opcua-client/connections/`
  - Flat YAML schema matching `ConnectionConfig` fields (url, timeout, username, password, auth_policy, security_mode, cert_file, key_file)
  - Profile discovery searches repo-local then user config directory
  - Strict key validation with helpful error messages for unknown fields
- **`--connection-profile` flag** - Use a named profile with any CLI command or TUI
  - `collectua config --connection-profile prod --action show`
  - `opcua-tui --connection-profile staging`
  - Explicit CLI args override profile values (deterministic precedence)
- **`collectua list-profiles` command** - Display available connection profiles
  - Lists all discovered profiles by name
  - Useful for automation and script workflows
- **TUI no-args default behavior** - Interactive profile selection on startup
  - Running `opcua-tui` with no arguments now prompts user to choose a profile
  - If no profiles are found, provides clear guidance to create one or use CLI args
  - Makes TUI more user-friendly for repeated connections
- **Sample profile** - `connections/example.yaml` included in repository
  - Provides template for users to create their own profiles

### Changed
- TUI no longer requires `--url` when connection profiles are available
  - `opcua-tui` with no args now launches interactive profile picker
  - `opcua-tui --url opc.tcp://server:4840` still works (explicit args always honored)

## [0.1.0] - 2026-03-06

### Changed
- **BREAKING: OPC UA URL is now required** for all CLI commands and TUI
  - `--url` argument changed from optional (with hardcoded default) to **required**
  - Affects all commands: `browse`, `collect`, `connect`, `config`, and `opcua-tui`
  - Removed hardcoded endpoint defaults (`opc.tcp://10.205.139.4:4840`) from codebase
  - Improves security by preventing accidental connections to unintended servers

## [0.1.0] - 2026-03-06

### Added
- Initial OPC UA client CLI with command-line interface
- **UV package manager support** - Run project using `uv run collectua` or `uv sync` for dependency management
- Production and debug runtime modes with configurable logging
- Debug log file generation with per-run timestamps
- Four main CLI commands:
  - `browse` - Browse OPC UA node tree with configurable depth
  - `collect` - Subscribe to alarms/events and export to CSV
  - `connect` - Connection smoke test with protocol/security validation
  - `config` - Display or validate runtime configuration
- Secure and insecure authentication modes
- Command-line configuration options for all runtime settings
- Comprehensive logging with mode-aware defaults:
  - Production mode: INFO level console only
  - Debug mode: INFO console + DEBUG file with full stack traces
