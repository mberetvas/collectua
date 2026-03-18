# Coding Conventions

**Analysis Date:** 2026-03-18

## Naming Patterns

**Files:**
- Lowercase with underscores: `collector.py`, `browse.py`, `runtime_config.py`
- Test files: `test_<module>.py` (mirrors source module name)
- Widget files: Descriptive lowercase: `alarm_table.py`, `node_tree.py`, `log_stream.py`

**Functions:**
- snake_case: `subscribe()`, `ensure_client_certificates()`, `load_env_defaults()`
- Private (module-internal): Prefixed with `_` → `_browse_recursive()`, `_condition_id_from_event()`
- Async functions: No special prefix, use `async def` keyword

**Variables:**
- snake_case for locals and instance attrs: `csv_path`, `active_alarms`, `event_type`
- Constants (module-level): UPPERCASE → `CSV_HEADERS`, `TIMEOUT`, `MAX_DEPTH`, `RETRO_GREEN`
- Instance attrs: snake_case → `self._active_alarms`, `self.csv_path`

**Types:**
- PascalCase for classes: `AlarmHandler`, `ConnectionConfig`, `CollectUAApp`, `ActiveAlarm`
- Type hints: Use Python 3.12+ union syntax → `str | None` instead of `Optional[str]`
- Protocol classes: Explicit `Protocol` inheritance → `class AlarmEventHandler(Protocol):`
- Dataclasses: `@dataclass` decorator with field defaults

## Code Style

**Formatting:**
- No explicit formatter (likely enforced by linting)
- Imports grouped: standard library, third-party, local (in that order)
- Line length: Appears to follow standard (~88 chars based on samples)

**Linting:**
- Style enforced implicitly (no .eslintrc or .prettierrc found)
- Assume standard Python conventions (PEP 8)
- Type hints present throughout (no bare functions without annotations)

## Import Organization

**Order:**
1. Standard library (`os`, `asyncio`, `logging`, `csv`, `pathlib`, `dataclasses`, etc.)
2. Third-party (`asyncua`, `textual`, `pyyaml`, `pytest`)
3. Local package (`from . import`, `from .module import`)

**Path Aliases:**
- None detected (imports use relative imports within package)
- Example: `from . import browse, collector` in `cli.py`

**Import Examples:**
```python
# Standard library
import asyncio
import csv
import logging
import os
from pathlib import Path

# Third-party
from asyncua import Client, ua
from textual.app import App
import yaml

# Local
from . import browse, collector
from .env_defaults import get_str, get_int
from .runtime_config import ConnectionConfig
```

## Error Handling

**Patterns:**
- Async context managers for resource cleanup: `async with Client(...) as client:`
- Specific exception handling: `except ua.UaError:` for OPC UA errors
- Graceful fallback: If display name read fails, use browse name as fallback
- Auto-retry wrapper: `condition_refresh_with_retry()` wraps subscription logic with reconnect

**Example from browse.py:**
```python
try:
    name = (await node.read_browse_name()).to_string()
    node_id = node.nodeid.to_string()
    ...
except ua.UaError as e:
    return [f"{'  ' * depth}├── [error: {e}]", *child_lines]
```

## Logging

**Framework:** Python `logging` module

**Setup:** Centralized in `cli._configure_logging()`
- Creates named loggers: `logging.getLogger("collector")`, `logging.getLogger("tui")`
- Root logger configured with handlers (console, optional file)
- Formatter: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

**Patterns:**
```python
_logger = logging.getLogger(__name__)

# Info: flow events
_logger.info("Connected to %s", endpoint)

# Debug: detailed diagnostics
_logger.debug("Clearing active alarm for ConditionId=%s", condition_id)

# Warning: recoverable issues
_logger.warning("Connection lost; reconnecting...")

# Error: failures but not fatal
_logger.error("Failed to read node: %s", error)
```

**Levels:**
- DEBUG: Detailed state transitions, connection traces, full event objects
- INFO: Command start/end, connection established, subscriptions created
- WARNING: Recoverable failures (retry, fallback), missed events
- ERROR: Unrecoverable failures, exit-triggering issues

## Comments

**When to Comment:**
- Non-obvious algorithms (e.g., namespace filtering logic in `_browse_recursive`)
- Workarounds or intentional deviations from standard patterns
- Complex state transitions or synchronization logic
- Do NOT comment obvious code (`x = 1  # set x to 1` is noise)

**JSDoc/TSDoc:**
- Google-style docstrings on functions and classes
- Format: Single-line summary, blank line, detailed description (if needed), Args/Returns/Raises sections

**Example:**
```python
async def subscribe(
    client: Client, 
    handler: AlarmEventHandler, 
    publish_interval_ms: int
) -> None:
    """
    Subscribe to alarms/events on the OPC UA server.
    
    Args:
        client: Connected OPC UA client instance
        handler: Event handler implementing alarm notification callbacks
        publish_interval_ms: Publish interval in milliseconds
    
    Raises:
        ua.UaError: If subscription creation fails
    """
```

## Function Design

**Size:** Typically 10–50 lines (shorter is better for testability)
- Recursive functions (e.g., `_browse_recursive`) may be slightly longer due to tree traversal
- Handlers/callbacks: As short as possible, delegate to helper functions

**Parameters:**
- Use dataclasses for multi-param configs → `ConnectionConfig` instead of 10+ positional args
- Async functions default to single config param: `async def run(endpoint: str, max_depth: int, ...)`
- Type hints on all parameters and return values

**Return Values:**
- Prefer explicit types over unions (unless union is intentional)
- Return None explicitly for functions with side effects (logging, CSV writes)
- Return data structures (lists, dicts) for query functions

**Example:**
```python
async def _browse_recursive(
    node, 
    depth: int, 
    max_depth: int, 
    target_namespaces: set[int]
) -> list[str]:
    """Return list of formatted tree lines."""
    if depth > max_depth:
        return []
    # ... tree traversal logic
    return [current_line, *child_lines]
```

## Module Design

**Exports:**
- Public API exported at module level (e.g., `run()`, `subscribe()` in collector)
- Private helpers prefixed with `_` to signal internal use
- No `__all__` observed, but convention is clear from naming

**Barrel Files:**
- `src/opcua_client/__init__.py` exports `main()` entry point
- `src/opcua_client/tui/__init__.py` likely re-exports TUI app or widgets

**Example from collector.py:**
```python
# Public API
class AlarmHandler: ...
async def subscribe(...): ...

# Internal helpers
def _condition_id_from_event(...): ...
def _bool_from_state(...): ...
```

## Type Hints

**Usage:** Present on all functions and methods

**Style:** Python 3.12+ syntax
- Union: `str | None` (not `Optional[str]`)
- Generics: `list[str]`, `dict[str, int]` (not `List[str]`, `Dict[str, int]`)
- Protocols: Explicit `Protocol` class inheritance

**Example:**
```python
@dataclass
class ConnectionConfig:
    url: str
    timeout: float
    security_mode: str
    cert_file: str | None = None
    logging_config: LoggingConfig | None = None
    
async def subscribe(client: Client, handler: AlarmEventHandler) -> None: ...
def get_str(name: str, default: str = "") -> str: ...
```

---

*Convention analysis: 2026-03-18*
