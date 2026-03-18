# Phase 1 Summary: DDD Foundation

**Date:** 2026-03-18
**Phase:** 1
**Status:** Complete

## Outcome

Phase 1 established a domain-first architecture foundation without changing CLI/TUI behavior. The codebase now has explicit domain entities/value objects and infrastructure adapters that can be used for gradual migration of existing command and TUI workflows.

## What Was Built

### Domain layer

- `src/opcua_client/domain/alarm.py`
  - `Alarm`, `AlarmId`, `AlarmSeverity`
  - Validation and domain state helpers (`is_active`, `is_acknowledged`, `is_retained`)

- `src/opcua_client/domain/connection.py`
  - `OPCUAConnection`, `Credentials`, `SecurityMode`, `AuthPolicy`
  - URL/timeout/security invariants and connection helper methods

- `src/opcua_client/domain/node.py`
  - `Node`, `NodeId`, `NodeClass`, `NodeTree`
  - Node invariants and hierarchy helper operations

- `src/opcua_client/domain/exceptions.py`
  - Domain exception hierarchy for validation/invariant failures

### Infrastructure layer

- `src/opcua_client/infrastructure/asyncua_adapter.py`
  - Maps asyncua event/node payloads into domain objects
  - Maps `RuntimeConfig` connection data into `OPCUAConnection`

- `src/opcua_client/infrastructure/config_loader.py`
  - Loads profile/CLI/env config into domain connection objects
  - Supports merge precedence handling

- `src/opcua_client/infrastructure/csv_writer.py`
  - Writes domain alarms to CSV and reads alarm history back into domain objects

- `src/opcua_client/infrastructure/repositories.py`
  - Repository interfaces and in-memory implementations for alarms and nodes

## Tests Added

- `tests/test_domain_alarm.py`
- `tests/test_domain_connection.py`
- `tests/test_domain_node.py`
- `tests/test_infrastructure_asyncua_adapter.py`
- `tests/test_infrastructure_config_loader.py`
- `tests/test_infrastructure_csv_writer.py`
- `tests/test_infrastructure_repositories.py`

## Verification

- Existing test suite still passes.
- New domain/infrastructure tests pass.
- Existing CLI and TUI modules remain unchanged and backward compatible.

## Dependency Boundary Rules Enforced

- `src/opcua_client/domain/*` imports only stdlib + `asyncua` + domain modules.
- `src/opcua_client/infrastructure/*` imports domain modules and external/runtime adapters.
- CLI/TUI continue orchestrating behavior and can adopt domain/infrastructure incrementally.

## Deferred to Next Phase

- Move collector and browse runtime behavior fully onto domain/application use-cases.
- Introduce an explicit application layer for use-case orchestration.
- Replace legacy active alarm state structures with domain repository-backed flows.
