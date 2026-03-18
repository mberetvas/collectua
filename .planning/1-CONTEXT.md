# Phase 1 Context: Domain-Driven Design Architecture Refactor

**Discussion Date:** 2026-03-18

## Phase Goal

Refactor the collectua architecture toward Domain-Driven Design (DDD) by introducing a domain layer that isolates business logic (alarm handling, connection management, node browsing) from infrastructure concerns (asyncua integration, CSV export, YAML config).

## Key Decisions

### Domain Isolation Strategy

**Domain Layer Dependencies:**
- ✅ **Allowed:** `asyncua` library (types only, not I/O)
- ✅ **Allowed:** Standard library
- ✅ **Allowed:** Logging and error raising
- ❌ **Forbidden:** CSV/file I/O
- ❌ **Forbidden:** Network calls
- ❌ **Forbidden:** Imports from `collector`, `browse`, `runtime_config`, `cli`, or `tui` modules

**Rationale:** Domain layer represents pure OPC UA business logic independent of storage or presentation. Using asyncua types (ua.NodeId, ua.Event) is conceptually appropriate since domain models OPC UA concepts. Avoiding I/O keeps domain testable and composable.

### Implementation Approach

**Start with entities and value objects, add services later.**

Order of extraction:
1. Create domain value objects (AlarmSeverity, AlarmId, Timestamp)
2. Create domain entities (Alarm, OPCUAConnection, Node)
3. Define entity methods and invariants
4. Add domain services (AlarmAggregator, NodeBrowser service)
5. Phase 2+: Add repositories, domain events, use cases

**Why bottom-up:** Clearer separation between data (entities/values) and behavior (services). Reduces risk of re-organizing later. Easier to test incrementally.

### Import Structure

**Strict dependency graph:**

```
src/opcua_client/
├── domain/                    # Pure domain layer
│   ├── alarm.py              # Alarm entity, AlarmSeverity value object, AlarmId
│   ├── connection.py         # OPCUAConnection entity, AuthConfig value object
│   ├── node.py               # Node entity, node tree traversal logic
│   └── exceptions.py         # Domain exceptions (AlarmValidationError, etc.)
│
├── infrastructure/            # Adapters, repositories, external service wrappers
│   ├── asyncua_adapter.py    # Bridge between domain and asyncua library
│   ├── repositories.py       # AlarmRepository, NodeRepository (persistence stubs for now)
│   ├── config_loader.py      # Load RuntimeConfig into domain objects
│   └── csv_writer.py         # CSV export adapter
│
├── application/              # Use cases and orchestration (Phase 2+)
│   └── (defer to phase 2)
│
├── cli.py                    # Command-line interface (unchanged for now)
├── tui/                      # Terminal UI (unchanged for now)
└── (existing modules remain until integrated)
```

**Import rules:**
- `domain/` imports: `asyncua`, `stdlib`, `domain/`
- `infrastructure/` imports: `domain/`, `asyncua`, `stdlib`, third-party (`yaml`, `csv`, etc.)
- `cli/tui/` imports: `infrastructure/`, `domain/`, anything else

**Rationale:** Prevents infrastructure from leaking into domain. Allows infrastructure to depend on domain without circular imports. CLI/TUI act as entry points that orchestrate via infrastructure.

## Code Context (Current State)

### Existing Domain Concepts (to be extracted)

**Alarm** — Currently in `src/opcua_client/collector.py`:
```python
@dataclass(frozen=True)
class ActiveAlarm:
    condition_id: str
    condition_name: str
    source_name: str
    message: str
    severity: str                    # Should become AlarmSeverity enum
    timestamp_utc: str
    retain: Optional[bool]
    active_state: Optional[bool]
    acked_state: Optional[bool]
    raw: str
```

**Connection** — Currently spread across:
- `src/opcua_client/runtime_config.py` (ConnectionConfig dataclass with 15+ fields)
- `src/opcua_client/cert_paths.py` (certificate path resolution)
- `src/opcua_client/profile_autosetup.py` (auto-setup logic)
- `src/opcua_client/profile_loader.py` (YAML loading)

**Node** — Currently in `src/opcua_client/browse.py`:
```python
async def _browse_recursive(node, depth: int, max_depth: int, target_namespaces: set[int]) -> list[str]:
    # Logic mixes asyncua client calls with tree structure building
```

### Existing Infrastructure Concepts

**AlarmHandler** (currently in `collector.py`) — Should move to infrastructure:
- Accepts raw asyncua events
- Converts to ActiveAlarm/Alarm
- Writes to CSV
- Updates in-memory state

**Profile Loading** (currently in `profile_loader.py`, `runtime_config.py`) — Should move to infrastructure:
- Reads YAML profiles
- Validates config
- Maps to domain connection objects

**CSV Export** (currently in `collector.py`, `AlarmHandler`) — Should move to infrastructure:
- Writes headers
- Appends rows
- Could become generic repository pattern later

## Constraints & Risks

**No Changes to CLI/TUI Yet:**
- Phase 1 focuses on extracting domain layer
- CLI and TUI continue using existing modules as-is
- Phase 2 will integrate domain via application layer / use cases
- Risk: Temporary duplication (domain Alarm + old ActiveAlarm) until full integration
- Mitigation: Keep old code, add new domain code alongside; remove old code when fully integrated

**Backward Compatibility:**
- Tests must continue passing
- Existing commands (browse, collect, connect, config) must work
- Add new tests for domain layer without touching CLI tests yet

**Infrastructure Adapter Complexity:**
- Converting asyncua events to domain Alarm objects requires careful mapping
- First pass may need iteration to find right adapter boundaries
- Be prepared to adjust domain model if adapters become unwieldy (sign of poor domain design)

## Success Criteria

**Phase 1 is complete when:**

✅ `src/opcua_client/domain/` populated with:
   - Alarm entity (with invariants like "severity must be valid")
   - AlarmSeverity value object (enum or custom)
   - AlarmId value object (wraps condition_id string)
   - Connection entity (with nested AuthConfig value object)
   - Node entity (with parent/children relationships, attributes)

✅ `src/opcua_client/infrastructure/` populated with:
   - `asyncua_adapter.py` — converts asyncua events/nodes to domain objects
   - `config_loader.py` — loads yaml/env into domain Connection
   - `csv_writer.py` — writes domain Alarm to CSV
   - Stubs for repositories (AlarmRepository, NodeRepository interfaces defined)

✅ Domain layer is isolated:
   - Domain/ imports only asyncua + stdlib (verified by linter or manual check)
   - No circular imports
   - Domain exceptions defined and used

✅ Existing functionality preserved:
   - All current tests pass
   - CLI commands work unchanged
   - TUI still functional

✅ Documentation:
   - ARCHITECTURE.md updated with new domain/infrastructure layers
   - Comments in domain/ explain entity boundaries and invariants

## Questions for Planner/Executor

**What should domain Alarm aggregate include?**
- Just alarm data (id, message, severity, timestamp)?
- Or also derived fields (is_active, is_acknowledged)?
- Or also collection logic (Alarm repository with query methods)?

**How to handle OPC UA Node complexity in domain model?**
- Node type hierarchy (Object, Variable, Method)?
- Attributes (value, datatype, accessLevel)?
- How deep into OPC UA spec should domain go?

**For Connection entity, what's the aggregate root?**
- Is it OPCUAConnection?
- Or is Server the root, owning connections, subscriptions, nodes?
- Affects how we model relationships later

*(These will be answered during planning phase)*

## Next Steps

→ **Run `/gsd-plan-phase 1`** to create detailed PLAN.md with tasks breakdown, file structure, and implementation steps.

---

*Context captured: 2026-03-18*
