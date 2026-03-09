# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **BREAKING: OPC UA URL is now required** for all CLI commands and TUI
  - `--url` argument changed from optional (with hardcoded default) to **required**
  - Affects all commands: `browse`, `collect`, `connect`, `config`, and `opcua-tui`
  - Removed hardcoded endpoint defaults (`opc.tcp://10.205.139.4:4840`) from codebase
  - Improves security by preventing accidental connections to unintended servers

## [0.1.0] - 2026-03-06

### Added
- Initial OPC UA client CLI with command-line interface
- **UV package manager support** - Run project using `uv run opcua-client` or `uv sync` for dependency management
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
