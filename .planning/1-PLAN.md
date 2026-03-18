# Phase 1 Plan: Domain-Driven Design Architecture Refactor

**Plan Date:** 2026-03-18  
**Context:** `.planning/1-CONTEXT.md`

## Phase Goal

Refactor collectua toward Domain-Driven Design by extracting a domain layer (Alarm, Connection, Node entities) and infrastructure adapters, while keeping CLI/TUI unchanged. Establish strict import boundaries and domain invariants.

## Phase Breakdown

### Wave 1: Domain Entities & Value Objects

**Task 1.1: Create Alarm Domain Model**
- **Goal:** Extract alarm business logic from `collector.py` into domain entity
- **Files to create:** `src/opcua_client/domain/alarm.py`
- **Implementation:**
  - Define `AlarmSeverity` value object (enum: LOW, MEDIUM, HIGH, CRITICAL)
  - Define `AlarmId` value object (wraps condition_id string, provides validation)
  - Create `Alarm` entity with:
    - Attributes: id, name, source, message, severity, timestamp, retain_flag, active_state, acked_state
    - Methods: `is_active()`, `is_acknowledged()`, `is_retained()`
    - Invariants: severity must be valid enum, timestamp must be ISO format or datetime
  - Add docstrings explaining alarm semantics from OPC UA spec
- **Tests:** `tests/test_domain_alarm.py`
  - Test AlarmSeverity enum values
  - Test AlarmId validation and equality
  - Test Alarm entity invariants
  - Test Alarm state query methods
- **Verification:**
  - Alarm class has no imports from collector, browse, runtime_config, cli, tui
  - Alarm imports only: asyncua (if needed for types), stdlib, domain/
  - All tests pass

---

**Task 1.2: Create Connection Domain Model**
- **Goal:** Extract OPC UA connection concepts into domain entity
- **Files to create:** `src/opcua_client/domain/connection.py`
- **Implementation:**
  - Define `SecurityMode` value object (enum: NONE, SIGN, SIGN_AND_ENCRYPT)
  - Define `AuthPolicy` value object (enum: NONE, BASIC, etc.)
  - Define `Credentials` value object:
    - Attributes: username, password (password is optional for cert auth)
    - Methods: `is_certificate_auth()`, `is_username_auth()`
  - Define `OPCUAConnection` entity:
    - Attributes: url, timeout, session_timeout, request_timeout, security_mode, auth_policy, credentials, cert_path, key_path, server_cert_path
    - Methods: `is_secure()`, `requires_client_cert()`, `is_trusted()`
    - Invariants: url must be valid opc.tcp:// format, timeouts must be positive
  - Create `AuthConfig` value object (wrapper for auth-related fields)
- **Tests:** `tests/test_domain_connection.py`
  - Test SecurityMode and AuthPolicy enums
  - Test Credentials value object (auth type detection)
  - Test OPCUAConnection validation
  - Test invariants (invalid URLs, negative timeouts)
- **Verification:**
  - Connection class has no imports from runtime_config, profile_loader, cli, tui
  - Imports only: asyncua (if needed), stdlib, domain/
  - All tests pass

---

**Task 1.3: Create Node Domain Model**
- **Goal:** Extract OPC UA node concepts into domain entity
- **Files to create:** `src/opcua_client/domain/node.py`
- **Implementation:**
  - Define `NodeId` value object (wraps ua.NodeId or string, provides comparison)
  - Define `NodeClass` value object (enum: OBJECT, VARIABLE, METHOD, etc.)
  - Create `Node` entity:
    - Attributes: node_id, display_name, browse_name, node_class, namespace_index, parent_node_id
    - Methods: `is_variable()`, `is_object()`, `is_method()`, `path_from_root()`
    - Invariants: node_id must be non-empty, namespace_index >= 0
  - Create `NodeTree` value object (or collection helper):
    - Represents hierarchy without knowing how nodes are persisted
    - Methods: `add_child(node)`, `get_children()`, `find_by_id()`
- **Tests:** `tests/test_domain_node.py`
  - Test NodeId comparison and equality
  - Test Node entity creation and queries
  - Test NodeTree traversal and child lookup
- **Verification:**
  - Node class has no imports from browse, cli, tui
  - Imports only: asyncua (for NodeId types), stdlib, domain/
  - All tests pass

---

**Task 1.4: Create Domain Exceptions**
- **Goal:** Define custom exceptions for domain validation and invariant violations
- **Files to create:** `src/opcua_client/domain/exceptions.py`
- **Implementation:**
  - Base exception: `DomainException`
  - Alarm exceptions: `InvalidAlarmSeverity`, `AlarmValidationError`
  - Connection exceptions: `InvalidOPCUAUrl`, `InvalidSecurityMode`, `ConnectionValidationError`
  - Node exceptions: `InvalidNodeId`, `NodeValidationError`
  - Subscription exceptions: `SubscriptionFailed`
  - Each exception includes context (what failed, why)
- **Usage:**
  - Import in domain entities, raise on invariant violation
  - No logging here; exceptions carry all context
- **Verification:**
  - All exceptions inherit from DomainException
  - Exceptions have informative error messages
  - No circular imports

---

### Wave 2: Infrastructure Adapters

**Task 2.1: Create asyncua Adapter**
- **Goal:** Convert asyncua types/events to domain objects
- **Files to create:** `src/opcua_client/infrastructure/asyncua_adapter.py`
- **Implementation:**
  - Function: `event_to_alarm(asyncua_event) -> Alarm`
    - Parses ua.Event attributes into Alarm entity
    - Handles missing/malformed fields (returns default or raises)
    - Maps ua.Severity enum to domain AlarmSeverity
  - Function: `node_to_domain_node(asyncua_node) -> Node`
    - Converts ua.Node to domain Node entity
    - Resolves display name, browse name, node class
  - Function: `create_connection_from_config(runtime_config) -> OPCUAConnection`
    - Builds OPCUAConnection entity from RuntimeConfig (migration helper)
  - Include docstrings showing mapping rules
- **Tests:** `tests/test_infrastructure_asyncua_adapter.py`
  - Test event_to_alarm with various event types and missing fields
  - Test node_to_domain_node with different node classes
  - Test create_connection_from_config with various configs
- **Verification:**
  - Adapter handles edge cases (missing severity, null values, etc.)
  - Error messages indicate which field was problematic
  - Tests cover real OPC UA event structures

---

**Task 2.2: Create Config Loader**
- **Goal:** Load YAML profiles and environment into domain Connection objects
- **Files to create:** `src/opcua_client/infrastructure/config_loader.py`
- **Implementation:**
  - Function: `load_connection_from_profile(profile_name) -> OPCUAConnection`
    - Reads YAML, validates, returns domain Connection
  - Function: `load_connection_from_cli_args(args) -> OPCUAConnection`
    - Maps CLI arguments to OPCUAConnection
  - Function: `merge_configs(profile, cli_args, env) -> OPCUAConnection`
    - Implements precedence: CLI > profile YAML > .env > defaults
  - Error handling: Raise `ConnectionValidationError` on invalid config
- **Tests:** `tests/test_infrastructure_config_loader.py`
  - Test loading valid YAML profile
  - Test precedence (CLI overrides profile)
  - Test invalid profile (missing URL, bad timeout)
  - Test env var overrides
- **Verification:**
  - No side effects (pure function, no file writes)
  - All validation errors are domain exceptions
  - Tests cover precedence order

---

**Task 2.3: Create CSV Writer Adapter**
- **Goal:** Export domain Alarm objects to CSV file
- **Files to create:** `src/opcua_client/infrastructure/csv_writer.py`
- **Implementation:**
  - Class: `CSVAlarmWriter`
    - Method: `__init__(file_path: str)` → initializes, writes header if file missing
    - Method: `write_alarm(alarm: Alarm) -> None` → appends Alarm row to CSV
    - Method: `get_alarm_history(limit: int) -> list[Alarm]` → reads CSV, returns Alarm objects
  - CSV headers match Alarm attributes (condition_id, message, severity, etc.)
  - Includes metadata row (timestamp written, PID, etc.) for debugging
- **Tests:** `tests/test_infrastructure_csv_writer.py`
  - Test writing single alarm to new file
  - Test appending alarm to existing file
  - Test header creation
  - Test reading alarms back
  - Test malformed CSV graceful handling
- **Verification:**
  - CSV format is readable, compatible with existing tools
  - No Alarm data lost in serialization/deserialization
  - File I/O errors handled gracefully

---

**Task 2.4: Create Repository Stubs & Interfaces**
- **Goal:** Define repository patterns for future phase (Phase 2+)
- **Files to create:** `src/opcua_client/infrastructure/repositories.py`
- **Implementation:**
  - Abstract base: `AlarmRepository(ABC)`
    - Methods: `add(alarm: Alarm)`, `get_by_id(id: AlarmId) -> Alarm | None`, `list_active() -> list[Alarm]`
  - Stub implementation: `InMemoryAlarmRepository` (stores alarms in dict)
  - Abstract base: `NodeRepository(ABC)`
    - Methods: `add(node: Node)`, `get_by_id(node_id: NodeId) -> Node | None`, `list_children(parent_id) -> list[Node]`
  - Stub implementation: `InMemoryNodeRepository`
  - Document that Phase 2 will add SQL/file-based persistence
- **Tests:** `tests/test_infrastructure_repositories.py`
  - Test repository interface behavior
  - Test in-memory implementation
- **Verification:**
  - Repository abstraction is clear
  - Stubs work and pass basic tests
  - Ready for concrete implementations in Phase 2

---

### Wave 3: Integration & Verification

**Task 3.1: Update ARCHITECTURE.md**
- **Goal:** Document new domain/infrastructure layers
- **Changes:**
  - Add Domain Layer section (entities, value objects, invariants)
  - Add Infrastructure Layer section (adapters, repositories)
  - Update data flow diagrams to show domain concepts
  - Clarify import boundaries with visual dependency graph
- **Verification:**
  - README readers understand DDD structure
  - File paths are current and correct
  - Example code snippets work

---

**Task 3.2: Verify Import Boundaries**
- **Goal:** Ensure domain layer isolation
- **Implementation:**
  - Script: Check that `domain/` imports don't reference collector, browse, runtime_config, cli, tui
  - Script: Check for circular imports between domain, infrastructure, cli
  - Manual review: Spot-check import statements in key files
- **Tests:** Create linting rule (or manual checklist) for CI/CD
- **Verification:**
  - All domain imports are clean (only asyncua, stdlib, domain/)
  - No circular imports detected
  - Import graph is acyclic

---

**Task 3.3: Ensure Backward Compatibility**
- **Goal:** Existing CLI/TUI work unchanged
- **Testing:**
  - Run existing test suite: `pytest tests/` (all non-domain tests)
  - Manual test: `collectua browse --url opc.tcp://...`
  - Manual test: `collectua collect --url opc.tcp://... --csv alarms.csv`
  - Manual test: `collectua --tui`
- **Verification:**
  - All existing tests pass
  - CLI commands produce same output as before
  - TUI displays correctly

---

**Task 3.4: Create Phase 1 Summary Documentation**
- **Goal:** Document what was extracted and why
- **Files to create:** `.planning/1-SUMMARY.md`
- **Content:**
  - Overview of domain layer (Alarm, Connection, Node)
  - Overview of infrastructure adapters
  - Import boundaries explained
  - Code examples: how to use domain entities
  - What's not done yet (use cases, full integration, Phase 2 work)
- **Verification:**
  - Documentation is clear enough for someone unfamiliar to understand
  - Code examples run without error

---

## Implementation Order

**Recommended sequence (respects dependencies):**

1. **Task 1.1** (Alarm entity) — No dependencies, starts domain layer
2. **Task 1.4** (Exceptions) — Used by all domain entities
3. **Task 1.2** (Connection entity) — Uses exceptions from 1.4
4. **Task 1.3** (Node entity) — Uses exceptions from 1.4
5. **Task 2.1** (asyncua adapter) — Depends on domain entities (1.1, 1.2, 1.3)
6. **Task 2.2** (Config loader) — Depends on Connection entity (1.2)
7. **Task 2.3** (CSV writer) — Depends on Alarm entity (1.1)
8. **Task 2.4** (Repository stubs) — Depends on domain entities (1.1, 1.3)
9. **Task 3.1** (Update docs) — Depends on all domain/infra work
10. **Task 3.2** (Verify boundaries) — Depends on all code in place
11. **Task 3.3** (Backward compat) — Verify existing code still works
12. **Task 3.4** (Summary docs) — Final documentation

## Success Criteria

✅ **Domain Layer Complete:**
- `src/opcua_client/domain/alarm.py` (Alarm, AlarmSeverity, AlarmId)
- `src/opcua_client/domain/connection.py` (OPCUAConnection, SecurityMode, AuthPolicy, Credentials)
- `src/opcua_client/domain/node.py` (Node, NodeId, NodeClass)
- `src/opcua_client/domain/exceptions.py` (domain-specific exceptions)

✅ **Infrastructure Adapters Complete:**
- `src/opcua_client/infrastructure/asyncua_adapter.py` (event/node converters)
- `src/opcua_client/infrastructure/config_loader.py` (config merging)
- `src/opcua_client/infrastructure/csv_writer.py` (alarm export)
- `src/opcua_client/infrastructure/repositories.py` (repository interfaces)

✅ **Isolation Verified:**
- Domain layer imports only asyncua + stdlib
- No circular imports
- Import graph documented

✅ **Tests Pass:**
- 40+ new unit tests for domain entities
- 15+ new tests for infrastructure adapters
- All existing tests still pass

✅ **Documentation Updated:**
- ARCHITECTURE.md reflects new layers
- 1-SUMMARY.md explains structure and next steps
- Code examples included

✅ **Backward Compatibility:**
- All CLI commands work
- All TUI features work
- No user-facing changes

## Risk Mitigation

**Risk:** Domain model doesn't match reality (missing fields, wrong structure)
- **Mitigation:** Review AlarmHandler current usage to ensure Alarm captures all needed fields
- **Fallback:** Keep both old ActiveAlarm and new Alarm during Phase 1; Phase 2 migrates fully

**Risk:** Adapter complexity reveals poor domain design
- **Mitigation:** Iterate on domain based on adapter feedback; be ready to refactor
- **Fallback:** Revert to pragmatic design if pure DDD becomes too complex

**Risk:** Import boundary violations creep in during implementation
- **Mitigation:** Manual code review per task, use linter to enforce
- **Fallback:** Fix violations immediately; document exceptions if truly necessary

**Risk:** Existing tests break due to new code
- **Mitigation:** Don't modify existing modules yet; only add new files
- **Fallback:** Update CLI/TUI adapters to call domain services if integration needed

---

## Estimated Effort

- **Wave 1 (Domain entities):** 6-8 hours
  - Task 1.1: 1.5 hrs
  - Task 1.2: 1.5 hrs
  - Task 1.3: 1.5 hrs
  - Task 1.4: 0.5 hrs

- **Wave 2 (Infrastructure adapters):** 4-6 hours
  - Task 2.1: 1.5 hrs
  - Task 2.2: 1 hr
  - Task 2.3: 1 hr
  - Task 2.4: 1 hr

- **Wave 3 (Integration & verification):** 2-3 hours
  - Task 3.1: 0.5 hrs
  - Task 3.2: 0.5 hrs
  - Task 3.3: 0.5 hrs
  - Task 3.4: 1 hr

**Total: 12-17 hours (1-2 days of focused work)**

---

## Next Steps

→ **Execute Phase 1:** Run `/gsd-execute-phase 1` to begin implementation  
→ **Or refine plan:** Ask clarifying questions before starting

---

*Plan created: 2026-03-18*
