---
name: opcua-client-instructions
description: "Workspace instructions for OPC UA Client CLI project. Enforce documentation sync, UV tooling, Python conventions, async patterns, and mode-based design."
applyTo: "**"
---

# OPC UA Client Project Instructions

## Documentation Synchronization

**Always update project documentation after any feature addition, modification, or removal.** This is non-negotiable.

### CHANGELOG.md
- Add an entry in the `[Unreleased]` section under the appropriate subsection (`Added`, `Changed`, `Fixed`, `Removed`)
- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Be descriptive: include what was changed and why, not just what was done
- Example format:
  ```markdown
  - Added `--verbose` flag to browse command for detailed output
  - Fixed authentication timeout in debug mode
  ```

### README.md
- Update usage examples if command signatures or behaviors change
- Keep the TUI Keybindings, installation, and configuration sections in sync with code
- Add new command documentation to the "Available Commands" section
- Update the Examples section with practical use cases for new features
- Update debug workflow or logging options if those change

### When to Update

After:
- Adding or removing CLI commands or subcommands
- Adding, changing, or removing command flags/options
- Fixing bugs that affect user-facing behavior
- Changing runtime modes or logging configuration
- Adding or modifying TUI keybindings or panels

**Do not skip documentation.** If documenting feels unclear, ask clarifying questions in your response rather than proceeding without updates.

## Code Conventions

### Python & Type Hints
- Use Python 3.12+ syntax (e.g., `str | None` instead of `Optional[str]`)
- Include type hints on all function parameters and return types
- Use docstrings with `Args`, `Returns`, and `Raises` sections (Google style)
- Example:
  ```python
  async def collect_alarms(client: Client, interval_ms: int) -> list[Alarm]:
      """
      Subscribe to and collect alarms at specified interval.
      
      Args:
          client: Connected OPC UA client
          interval_ms: Publish interval in milliseconds
      
      Returns:
          List of collected alarm events
      
      Raises:
          ConnectionError: If client is not connected
      """
  ```

### Async Pattern
- Use `async`/`await` for I/O-bound operations (network, file)
- Default to async context managers (`async with`) for resource management
- Document blocking operations explicitly

### Logging
- Use the `logging` module supplied by `cli._configure_logging()`
- Log at appropriate levels:
  - `DEBUG`: Detailed diagnostic info (connection traces, full stack traces)
  - `INFO`: General flow (command started, connection established)
  - `WARNING` & `ERROR`: Issues that require user attention
- Production mode: INFO level console output (clean, concise)
- Debug mode: DEBUG level file output (comprehensive traces)

### Mode-Based Behavior
- Respect `prod` vs `debug` runtime modes throughout the codebase
- Debug mode enables additional detail, file logging, and verbose traces
- Production mode is lean—no verbose/debugging output to console
- Use `os.getenv("OPCUA_RUNTIME_MODE")` or `cli.RuntimeConfig` to check mode

## Tooling & Dependencies

### UV Package Manager
- All dependency management uses UV (no pip directly)
- Update `pyproject.toml` for new dependencies, not `requirements.txt`
- Install/sync with: `uv sync`
- Run commands with: `uv run <command>`
- Reference the [README.md](README.md) for installation instructions

### Dependency Updates
- Add dependencies to appropriate section in `pyproject.toml`:
  - Main project dependencies: `dependencies = [...]`
  - Development dependencies: `[project.optional-dependencies]` (if used)
- Test that `uv sync` works after changes
- Update CHANGELOG.md if dependency changes affect users

## Project Structure

- **CLI** commands: `src/opcua_client/cli.py` (entry point)
- **Commands**: `src/opcua_client/browse.py`, `src/opcua_client/collector.py`
- **TUI**: `src/opcua_client/tui/` (dashboard panels and app)
- **Config**: `src/opcua_client/runtime_config.py` (runtime settings)
- **Tests**: Tests are not enforced but consider impact when making changes
- **Logs**: Debug logs go to `logs/debug/` (auto-managed by `cli._configure_logging()`)

## Summary

1. **Always sync docs** (CHANGELOG.md + README.md) after any feature work
2. **Follow Python 3.12+ conventions** with type hints and docstrings
3. **Use async/await** for I/O operations
4. **Respect runtime modes**: prod vs debug behavior
5. **Use UV** for all package management
6. **Use project logging** configured in `cli._configure_logging()`

---

**Last Updated**: 2026-03-09
