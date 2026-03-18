# Codebase Structure

**Analysis Date:** 2026-03-18

## Directory Layout

```
opcua-client-tui/
├── src/opcua_client/              # Main package
│   ├── __init__.py                # Entry point: main() function
│   ├── cli.py                     # CLI argument parsing and command routing
│   ├── browse.py                  # Node tree traversal logic
│   ├── collector.py               # Alarm/event subscription and CSV export
│   ├── condition_refresh.py       # Event subscription with auto-retry
│   ├── runtime_config.py          # Configuration dataclasses and merging
│   ├── env_defaults.py            # Environment variable and .env file parsing
│   ├── profile_loader.py          # YAML profile loading and resolution
│   ├── profile_autosetup.py       # Interactive profile generation
│   ├── cert_paths.py              # Certificate generation and path resolution
│   ├── generate_certificates.py   # Certificate generation utilities
│   ├── .env                       # Package-level configuration defaults
│   ├── tui/
│   │   ├── __init__.py            # TUI module exports
│   │   ├── app.py                 # Textual App, TUI main container
│   │   └── widgets/               # Textual widgets
│   │       ├── __init__.py
│   │       ├── alarm_table.py     # Alarm display grid widget
│   │       ├── node_tree.py       # Node tree explorer widget
│   │       ├── node_info_panel.py # Node detail display
│   │       ├── connection_status.py # Connection state widget
│   │       ├── config_panel.py    # Connection config display
│   │       └── log_stream.py      # Log output widget
│   ├── domain/                    # [empty or future domain models]
│   └── infrastructure/            # [empty or future infrastructure code]
├── tests/                         # Test suite
│   ├── test_collector_core.py     # Alarm handler tests
│   ├── test_browse_helpers.py     # Node traversal tests
│   ├── test_cert_paths.py         # Certificate logic tests
│   ├── test_cli_profiles.py       # CLI profile resolution tests
│   ├── test_cli_utils.py          # CLI utility tests
│   ├── test_env_defaults.py       # Environment variable parsing tests
│   ├── test_profile_loader.py     # YAML profile loading tests
│   ├── test_runtime_config_security.py   # Config security tests
│   ├── test_runtime_config_validate_extra.py # Config validation tests
│   ├── test_tui_node_tree.py      # TUI widget tests
│   ├── test_tui_profiles.py       # TUI profile integration tests
│   └── test_tui_support.py        # TUI helper tests
├── connections/                   # [Runtime] Connection profile YAML files
├── certs/                         # [Runtime] Generated/stored client certificates
├── logs/                          # [Runtime] Log directory
│   └── debug/                     # Debug log files (when enabled)
├── pyproject.toml                 # Project metadata, dependencies, build config
├── uv.lock                        # UV dependency lockfile
├── justfile                       # Development task automation (just command)
├── README.md                      # User-facing documentation
├── CHANGELOG.md                   # Version history
├── CODE_OF_CONDUCT.md             # Community guidelines
├── CONTRIBUTING.md                # Contribution guidelines
├── LICENSE                        # Project license
└── .github/                       # GitHub metadata
    ├── skills/
    │   └── gsd-map-codebase/      # GSD mapping skill
    └── agents/                    # [potential GSD agent configs]
```

## Directory Purposes

**src/opcua_client/:**
- Purpose: Main Python package
- Contains: CLI, TUI, business logic, infrastructure
- Key entry: `__init__.py` exports `main()` function

**src/opcua_client/tui/:**
- Purpose: Terminal UI application
- Contains: Textual app and all widget implementations
- Key file: `app.py` contains CollectUAApp (Textual App subclass)

**tests/:**
- Purpose: Test suite
- Contains: Unit tests for all major modules
- Pattern: Co-located with source (same module name prefix)
- Runner: pytest (via `pyproject.toml`)

**connections/:**
- Purpose: Runtime directory for OPC UA connection profiles
- Contains: YAML files with connection parameters
- Generated: By interactive setup or user-created
- Committed: No (listed in .gitignore)

**certs/:**
- Purpose: Runtime directory for client certificates
- Contains: Auto-generated or user-provided certificate files
- Generated: By `cert_paths.ensure_client_certificates()`
- Committed: No (listed in .gitignore)

**logs/debug/:**
- Purpose: Debug log output
- Contains: Per-run log files with format `debug-{timestamp}-pid{pid}.log`
- Generated: When debug mode enabled or per-connection logging configured
- Committed: No (listed in .gitignore)

## Key File Locations

**Entry Points:**
- `src/opcua_client/__init__.py`: Main CLI entry point, exports `main()`
- `src/opcua_client/cli.py`: Argument parsing, command routing, logging setup
- `src/opcua_client/tui/app.py`: TUI application class (Textual App)

**Configuration:**
- `src/opcua_client/.env`: Package-level default values (env var fallbacks)
- `src/opcua_client/runtime_config.py`: Configuration dataclasses (ConnectionConfig, RuntimeConfig)
- `src/opcua_client/env_defaults.py`: .env file parsing and env var resolution

**Core Logic:**
- `src/opcua_client/browse.py`: Node tree traversal (`_browse_recursive()`)
- `src/opcua_client/collector.py`: Alarm subscription and CSV export (AlarmHandler, subscribe())
- `src/opcua_client/condition_refresh.py`: Event subscription with retry logic

**Infrastructure:**
- `src/opcua_client/profile_loader.py`: YAML profile loading and path resolution
- `src/opcua_client/profile_autosetup.py`: Interactive profile generation
- `src/opcua_client/cert_paths.py`: Certificate path resolution and generation

**Testing:**
- `tests/test_collector_core.py`: Alarm handler and CSV logic tests
- `tests/test_browse_helpers.py`: Node traversal algorithm tests
- `tests/test_cli_profiles.py`: Profile loading integration tests

## Naming Conventions

**Files:**
- Lowercase with underscores: `collect_ua.py`, `alarm_handler.py`
- Test files: `test_<module>.py` (matches source module)
- Widget files: `<widget_name>.py` (e.g., `alarm_table.py`, `node_tree.py`)

**Directories:**
- Lowercase with underscores: `src/opcua_client/`, `tui/widgets/`
- Runtime directories: `connections/`, `certs/`, `logs/`

**Classes:**
- PascalCase: `CollectUAApp`, `AlarmHandler`, `ConnectionConfig`
- Protocol: `AlarmEventHandler` (explicit Protocol marker)

**Functions:**
- snake_case: `_browse_recursive()`, `subscribe()`, `ensure_client_certificates()`
- Private (internal): Prefixed with `_` (e.g., `_node_sort_name()`)

**Constants:**
- UPPERCASE: `CSV_HEADERS`, `RETRO_GREEN`, `TIMEOUT`
- Package exports: `__init__.py` lists public API

## Where to Add New Code

**New Feature (e.g., new browse filter):**
- Primary code: `src/opcua_client/browse.py` (add function or modify `_browse_recursive()`)
- Tests: `tests/test_browse_helpers.py`
- Config: Update `BrowseConfig` in `src/opcua_client/runtime_config.py` if new params needed
- Documentation: Update `README.md` and `CHANGELOG.md`

**New TUI Widget:**
- Implementation: `src/opcua_client/tui/widgets/<widget_name>.py`
- Integration: Import and compose in `src/opcua_client/tui/app.py` (in CollectUAApp.compose())
- Tests: `tests/test_tui_<widget_name>.py`
- Keybindings: Add to `CollectUAApp.BINDINGS` list or widget's own BINDINGS

**New CLI Command (subcommand):**
- Handler: Add function to `src/opcua_client/cli.py`
- Argument setup: Add to `argparse` subparsers in `_setup_subcommands()`
- Business logic: Create new module (e.g., `src/opcua_client/my_command.py`) if significant
- Integration: Add to main() routing logic
- Tests: `tests/test_cli_<command>.py`
- Documentation: Update `README.md` with usage examples

**New Configuration Parameter:**
- Dataclass: Add field to appropriate dataclass in `src/opcua_client/runtime_config.py`
- Env defaults: Add to `.env` with default value
- Parsing: Add accessor function in `src/opcua_client/env_defaults.py` if custom type
- Documentation: Update `README.md` Configuration section

**Utility or Helper Function:**
- General utilities: Add to existing module (e.g., `env_defaults.py`) if small
- Domain-specific: Create new `src/opcua_client/<domain>.py` (e.g., `cert_utils.py`)
- Keep private (underscore prefix) unless explicitly public API

## Special Directories

**`.env` (src/opcua_client/.env):**
- Purpose: Package-level configuration defaults
- Generated: User-maintained
- Committed: Yes (but no secrets; plaintext only)
- Usage: Fallback for env vars, loaded via `env_defaults.load_env_defaults()`

**`pyproject.toml`:**
- Purpose: Single source of truth for project metadata and dependencies
- Generated: User-maintained
- Committed: Yes
- Structure: [project], [build-system], [dependency-groups]

**`.planning/codebase/` (GSD):**
- Purpose: Codebase analysis documents for GSD workflow
- Generated: By `/gsd-map-codebase` skill
- Committed: Yes (documents git structure and conventions)
- Contents: ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

---

*Structure analysis: 2026-03-18*
