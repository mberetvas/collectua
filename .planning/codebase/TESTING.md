# Testing Patterns

**Analysis Date:** 2026-03-18

## Test Framework

**Runner:**
- pytest 9.0.2+ (from `pyproject.toml`)
- Config file: Not detected (uses pytest defaults)

**Assertion Library:**
- pytest built-in assertions (`assert`)

**Run Commands:**
```bash
uv run pytest                    # Run all tests
uv run pytest -v               # Verbose output
uv run pytest tests/test_collector_core.py  # Run single test file
uv run pytest -k test_name     # Run tests matching pattern
uv run pytest --cov            # Coverage (if plugin installed)
```

## Test File Organization

**Location:**
- Co-located with source: `tests/test_<module>.py` mirrors `src/opcua_client/<module>.py`
- Examples:
  - `src/opcua_client/collector.py` → `tests/test_collector_core.py`
  - `src/opcua_client/browse.py` → `tests/test_browse_helpers.py`
  - `src/opcua_client/profile_loader.py` → `tests/test_profile_loader.py`

**Naming:**
- Test functions: `test_<scenario>` or `test_<function>_<condition>`
- Test classes: `Test<ModuleName>` or split into functions (majority are function-based)

**Structure:**
```
tests/
├── test_collector_core.py       # AlarmHandler, event parsing
├── test_browse_helpers.py       # Node tree traversal
├── test_cert_paths.py           # Certificate generation
├── test_env_defaults.py         # Environment variable parsing
├── test_profile_loader.py       # YAML profile loading
├── test_cli_profiles.py         # CLI integration with profiles
├── test_runtime_config_*.py     # Configuration merging
├── test_tui_*.py                # Widget and TUI tests
└── __pycache__/
```

## Test Structure

**Suite Organization:**
```python
def test_condition_id_from_event_variants() -> None:
    """Test parsing condition IDs from different event formats."""
    handler = collector.AlarmHandler("dummy.csv")
    
    # Scenario 1: Event with string condition ID
    event1 = _DummyEvent(condition_id="cond-123")
    result = handler._condition_id_from_event(event1)
    assert result == "cond-123"
    
    # Scenario 2: Event with NodeId object
    event2 = _DummyEvent(condition_id=_DummyNodeId("ns=1;i=456"))
    result = handler._condition_id_from_event(event2)
    assert result == "ns=1;i=456"
```

**Patterns:**
- Setup: Create test fixtures/mocks at start of test
- Action: Call the function or method being tested
- Assert: Verify results match expected values
- Teardown: Cleanup (often implicit or via fixtures)

## Mocking

**Framework:** pytest with `monkeypatch` (built-in pytest fixture)

**Patterns:**

```python
# 1. Mock environment variables
def test_with_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPCUA_TIMEOUT", "99.5")
    config = RuntimeConfig()
    assert config.connection.timeout == 99.5

# 2. Mock file system paths
def test_with_temp_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPCUA_URL=opc.tcp://test:4840")
    monkeypatch.setenv("OPCUA_ENV_FILE", str(env_file))
    
    # Test code here
    config = RuntimeConfig.from_namespace(...)
    assert config.connection.url == "opc.tcp://test:4840"

# 3. Mock module functions
def test_with_patched_function(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    monkeypatch.setattr(
        profile_loader, 
        "profile_search_dirs", 
        lambda: [profiles_dir]
    )
    # profile_loader.profile_search_dirs() now returns [profiles_dir]

# 4. Mock async functions (less common, but when needed)
# Use pytest-asyncio or unittest.mock.AsyncMock if needed
```

**What to Mock:**
- External I/O: File paths, environment variables, OPC UA network calls
- Time-sensitive operations: Timestamps (use fixed test values)
- Large dependencies: OPC UA client connections (mock with dummy objects)

**What NOT to Mock:**
- Core business logic: Test actual CSV parsing, config merging
- Standard library functions: os.path, pathlib operations (test with temp files)
- Domain models: Test real dataclass behavior, not mocks

## Fixtures and Factories

**Test Data:**

```python
# Dummy objects for OPC UA types
class _DummyNodeId:
    def __init__(self, value: str) -> None:
        self._value = value
    def to_string(self) -> str:
        return self._value

class _DummyEvent:
    """Mock OPC UA event with configurable attributes."""
    def __init__(
        self,
        *,
        condition_id: Any | None = None,
        retain: Any | None = None,
        active_state: Any | None = None,
        acked_state: Any | None = None,
    ) -> None:
        self.Time = "2024-01-01T00:00:00Z"
        self.EventType = "BaseEventType"
        self.SourceName = "SRC"
        self.Message = "msg"
        self.Severity = 1
        self.ConditionName = "cond"
        self.EventId = "evt-1"
        if condition_id is not None:
            self.ConditionId = condition_id
        # ... other optional attributes

class _DummyState:
    def __init__(self, value: Any) -> None:
        self.Id = value
```

**Location:**
- Defined at top of test file (e.g., `test_collector_core.py`)
- Reused across multiple test functions in same module

**Pattern:** Simple classes (not pytest fixtures) for OPC UA domain objects

## Coverage

**Requirements:** Not explicitly enforced (no .coveragerc found)

**View Coverage:**
```bash
uv run pytest --cov=src/opcua_client --cov-report=html
# Generates htmlcov/index.html with detailed coverage report
```

## Test Types

**Unit Tests:**
- Scope: Single function/method in isolation
- Approach: Mock external dependencies (network, file system)
- Examples:
  - `test_condition_id_from_event_variants()` - Tests event parsing
  - `test_runtime_config_from_namespace_uses_env_defaults()` - Tests config merging
  - `test_cli_explicit_arg_overrides_profile()` - Tests arg precedence

**Integration Tests:**
- Scope: Multiple modules interacting (but not real OPC UA server)
- Approach: Use real config loading, mocked profiles, temp file system
- Examples:
  - `test_cli_config_uses_profile_values()` - CLI + profile loader
  - `test_cli_profile_not_found_returns_error()` - CLI error handling
  - `test_browse_with_namespace_filtering()` - Browse logic + node mocking

**E2E Tests:**
- Framework: Not found (no E2E test directory)
- Note: Could be added for real OPC UA server testing (currently requires manual testing)

## Common Patterns

**Async Testing:**
```python
# Async tests use pytest-asyncio or asyncio.run()
async def test_browse_recursive_returns_list() -> None:
    node = _DummyNode(...)
    result = await browse._browse_recursive(node, depth=0, max_depth=3, ...)
    assert isinstance(result, list)
    assert len(result) > 0
```

**Error Testing:**
```python
def test_invalid_profile_returns_error() -> None:
    rc = cli.main(["config", "--connection-profile", "missing", "--action", "show"])
    assert rc == 2  # Error exit code
    # Optionally check error message via capsys

def test_config_from_invalid_yaml_raises_error(tmp_path: Path) -> None:
    invalid_yaml = tmp_path / "bad.yaml"
    invalid_yaml.write_text("{ incomplete yaml", encoding="utf-8")
    
    with pytest.raises(yaml.YAMLError):
        profile_loader.load_profile(str(invalid_yaml))
```

**CSV/File I/O Testing:**
```python
def test_alarm_handler_writes_csv_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "test.csv"
    handler = collector.AlarmHandler(str(csv_path))
    
    # Check header was written
    content = csv_path.read_text()
    assert "timestamp_utc" in content
    assert "event_type" in content
```

**Parameterized Tests:**
```python
@pytest.mark.parametrize("input,expected", [
    ("1", True),
    ("true", True),
    ("yes", True),
    ("0", False),
    ("false", False),
])
def test_get_bool_parsing(input: str, expected: bool) -> None:
    assert env_defaults.get_bool("TEST", input) == expected
```

## Cache Clearing

**Pattern:** Tests that use env variable caching must clear cache
```python
def test_env_defaults_respects_override(monkeypatch: pytest.MonkeyPatch) -> None:
    env_defaults.clear_env_defaults_cache()  # Clear before test
    monkeypatch.setenv("OPCUA_URL", "opc.tcp://test:4840")
    
    config = RuntimeConfig()
    assert config.connection.url == "opc.tcp://test:4840"
    
    env_defaults.clear_env_defaults_cache()  # Clean up after
```

---

*Testing analysis: 2026-03-18*
