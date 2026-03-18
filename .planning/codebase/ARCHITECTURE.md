# Architecture

**Analysis Date:** 2026-03-18

## Pattern Overview

**Overall:** Layered architecture with async/await event-driven model

**Key Characteristics:**
- Async-first design using Python `asyncio` for non-blocking I/O
- Separation of concerns: CLI/TUI layer, business logic, infrastructure (OPC UA, config, certs)
- Command-based entry point with subcommands (browse, collect, connect, config)
- TUI dashboard as separate execution mode (`--tui` flag)
- Environment-driven configuration with hierarchical precedence (CLI > profile YAML > .env > code)

## Layers

**CLI Layer:**
- Purpose: Parse arguments, orchestrate command execution, display console output
- Location: `src/opcua_client/cli.py`, `src/opcua_client/browse.py`, `src/opcua_client/collector.py`
- Contains: Command handlers, logging configuration, argument parsing
- Depends on: Infrastructure (OPC UA client, config, certs), Domain models
- Used by: Entry point script `collectua`

**TUI Layer:**
- Purpose: Interactive terminal dashboard for monitoring and browsing
- Location: `src/opcua_client/tui/app.py`, `src/opcua_client/tui/widgets/`
- Contains: Textual App, widgets (AlarmTable, NodeTree, NodeInfo, LogStream, ConfigPanel), key bindings
- Depends on: CLI infrastructure (collector, browsing), config, logging
- Used by: CLI with `--tui` flag

**Business Logic Layer:**
- Purpose: Core data collection and node traversal
- Location: `src/opcua_client/collector.py`, `src/opcua_client/browse.py`, `src/opcua_client/condition_refresh.py`
- Contains: Alarm subscription logic, CSV export, node tree traversal
- Depends on: Infrastructure (asyncua, config)
- Used by: CLI and TUI layers

**Infrastructure Layer:**
- Purpose: External service integration, credentials, configuration
- Location: `src/opcua_client/runtime_config.py`, `src/opcua_client/profile_loader.py`, `src/opcua_client/cert_paths.py`, `src/opcua_client/env_defaults.py`, `src/opcua_client/profile_autosetup.py`, `src/opcua_client/generate_certificates.py`
- Contains: Config dataclasses, YAML profile loading, certificate generation, environment variable resolution
- Depends on: Third-party libs (asyncua, pyyaml)
- Used by: All layers

## Data Flow

**Browse Command Flow:**

1. CLI parses args, builds `ConnectionConfig`
2. Loads or creates connection profile (YAML)
3. Configures logging based on config precedence
4. Ensures client certificates exist (`cert_paths.py`)
5. Creates async OPC UA client with config
6. Calls `browse._browse_recursive()` to traverse node tree depth-first
7. Prints indented tree to console or CSV

**Collect Command Flow:**

1. CLI parses args, builds config
2. Ensures connection profile and certificates
3. Configures logging
4. Initializes CSV with headers
5. Creates OPC UA client and subscription
6. Calls `collector.subscribe()` with `AlarmHandler` callback
7. Handler receives events, writes to CSV, prints to console
8. Auto-reconnects on connection loss with configurable delay

**TUI Flow:**

1. CLI detects `--tui` flag
2. Initializes logging and connection config
3. Ensures certificates
4. Starts Textual App (`tui.app.CollectUAApp`)
5. App spawns subscription task (`condition_refresh_with_retry`)
6. Widgets receive events via messages and update displays
7. User interaction (keyboard shortcuts) triggers actions
8. On exit, cleanup (close client, save state)

**State Management:**
- Transient: In-memory active alarm dict in `AlarmHandler` (keyed by ConditionId)
- Persistent: Connection profiles (YAML), CSV exports, debug logs (filesystem)
- Configuration: Loaded once at startup, cached via `@lru_cache` for .env parsing

## Key Abstractions

**ConnectionConfig:**
- Purpose: Centralized OPC UA connection parameters
- Examples: `src/opcua_client/runtime_config.py` (dataclass)
- Pattern: Dataclass with `@dataclass` decorator, field defaults from `env_defaults` functions
- Includes: URL, timeout, security mode, credentials, certificate paths, logging settings

**AlarmHandler (Protocol):**
- Purpose: Pluggable event handler for OPC UA subscriptions
- Examples: `src/opcua_client/collector.py` (AlarmHandler class), TUI widgets
- Pattern: Implements `event_notification()` and `status_change_notification()` methods (duck-typing)

**RuntimeConfig:**
- Purpose: Complete runtime configuration (command, connection, browse, collect, logging)
- Examples: `src/opcua_client/runtime_config.py`
- Pattern: Dataclass aggregating command-specific configs

**ActiveAlarm:**
- Purpose: Snapshot of an active alarm keyed by ConditionId
- Examples: `src/opcua_client/collector.py` (frozen dataclass)
- Pattern: Immutable record for deduplication and state tracking

## Entry Points

**CLI Entry Point:**
- Location: `src/opcua_client/__init__.py` (exports `main()` function)
- Triggers: `python -m opcua_client` or `collectua` command (via pyproject.toml entry point)
- Responsibilities: Parse args, route to subcommand handler, initialize logging, handle exceptions

**TUI Entry Point:**
- Location: `src/opcua_client/tui/app.py` (CollectUAApp class)
- Triggers: `collectua --tui` flag in CLI
- Responsibilities: Initialize Textual app, setup widgets, handle async subscription, manage lifecycle

**Subcommand Handlers:**
- `browse`: `cli.py` + `browse.py` - Traverse and print node tree
- `collect`: `cli.py` + `collector.py` - Subscribe and log events
- `connect`: `cli.py` + `collector.py` - Test connectivity (no event collection)
- `config`: `cli.py` + `runtime_config.py` - Display resolved configuration

## Error Handling

**Strategy:** Exceptions propagate to CLI, caught and logged with user-friendly messages

**Patterns:**
- Async context managers for resource cleanup (`async with Client(...) as client`)
- Try-except around network operations with logging at WARN/ERROR level
- `ua.UaError` caught specifically for OPC UA protocol errors
- Graceful degradation (e.g., fallback to browse name if display name unavailable in `browse.py`)
- Auto-retry for connection loss in collector with configurable backoff

## Cross-Cutting Concerns

**Logging:** 
- Configured in `cli._configure_logging()` with mode (prod/debug) and level precedence
- Per-connection logging via `ConnectionConfig.logging_config`
- File logging pattern: `{timestamp}-pid{pid}.log` for uniqueness across runs

**Validation:** 
- Runtime config validates connectivity test in `connect` command
- Certificate validation implicit in asyncua library
- YAML profile parsing validates structure (missing keys use defaults)

**Authentication:** 
- Connection-level: Username/password or certificate (in ConnectionConfig)
- Server certificate trust: Interactive prompt on first untrusted cert, persisted to profile
- Client cert auto-generation if not provided (via `cert_paths.ensure_client_certificates()`)

---

*Architecture analysis: 2026-03-18*
