# Codebase Concerns

**Analysis Date:** 2026-03-18

## Tech Debt

**Large CLI Entry Point:**
- Issue: `src/opcua_client/cli.py` (591 lines) handles all command routing, argument parsing, and logging setup
- Files: `src/opcua_client/cli.py`
- Impact: Difficult to test individual command logic; tight coupling between CLI concerns and business logic
- Fix approach: Extract subcommand handlers into separate modules (`commands/browse.py`, `commands/collect.py`), keep `cli.py` for argument parsing only

**Lack of Explicit Error Handling Framework:**
- Issue: Error handling is ad-hoc; exception propagation relies on caller context
- Files: `src/opcua_client/cli.py`, `src/opcua_client/tui/app.py`
- Impact: Inconsistent error messages; TUI could crash on unexpected OPC UA errors
- Fix approach: Create custom exception hierarchy (`OpcuaConnectionError`, `ProfileNotFoundError`, etc.) with context-aware formatting

**Domain/Infrastructure Directories Unused:**
- Issue: `src/opcua_client/domain/` and `src/opcua_client/infrastructure/` directories exist but are empty
- Files: Structure definition in file system
- Impact: Misleading to future contributors; architecture intention unclear
- Fix approach: Either populate these directories with refactored modules or remove them and update documentation

**Credential Storage in Plain YAML:**
- Issue: Connection profiles store OPC UA passwords in plain text in YAML files
- Files: `connections/*.yaml` files (user-created, not committed)
- Impact: Secret exposure risk if profiles accidentally committed or stored insecurely
- Current mitigation: .gitignore excludes `connections/` directory; README recommends securing YAML files with filesystem permissions
- Recommendations: 
  - Document encryption recommendation (e.g., `ansible-vault` for profile YAML)
  - Consider prompting for password at runtime instead of storing in profile
  - Add validation check to warn if profile contains password and is world-readable

## Known Bugs

**WhereClause Filtering Rejected by Siemens S7-1500:**
- Symptoms: Events silently dropped on S7-1500 when using strict OPC UA EventFilter
- Files: `src/opcua_client/collector.py` (condition_refresh_with_retry wrapping)
- Trigger: Subscribe to ConditionType on Siemens S7-1500 with default asyncua settings
- Status: FIXED - `condition_refresh.py` sets `where_clause_generation=False` to disable strict filtering
- Historical: See CHANGELOG.md [Unreleased] section for event visibility fix

## Security Considerations

**Insecure Default Security Mode:**
- Risk: Tool defaults to `security_mode: None_` (no encryption or signing)
- Files: `src/opcua_client/runtime_config.py` (default), `src/opcua_client/.env`
- Current mitigation: CLI prompts user to configure security when profile doesn't exist; documentation warns about insecure mode
- Recommendations:
  - Warn in TUI if connecting in insecure mode
  - Consider requiring explicit `--insecure-mode` flag to enable None_ mode
  - Pre-generate secure connection examples in documentation

**Certificate Trust Validation:**
- Risk: First untrusted certificate prompts user to trust; implementation relies on user judgment
- Files: `src/opcua_client/cert_paths.py`, `src/opcua_client/profile_autosetup.py`
- Current mitigation: Shows certificate fingerprint and prompts interactively
- Recommendations:
  - Document fingerprint verification process in README
  - Consider storing certificate chain (not just server cert) for more robust validation
  - Add optional CA bundle support for enterprise environments

**Client Certificate Management:**
- Risk: Auto-generated client certificates stored in `certs/` directory (not committed but unencrypted)
- Files: `src/opcua_client/cert_paths.py`, `src/opcua_client/generate_certificates.py`
- Current mitigation: User-controlled file system permissions
- Recommendations:
  - Document recommended permissions: `chmod 600 certs/client.pem certs/key.pem`
  - Consider storing in system keyring (e.g., macOS Keychain, Windows Credential Manager) on supported platforms

## Performance Bottlenecks

**Synchronous File I/O in Async Context:**
- Problem: CSV write operations (`csv.writer.writerow()`) are blocking calls in async code
- Files: `src/opcua_client/collector.py` (AlarmHandler.event_notification)
- Cause: Python's `csv` module is not async; writerow() blocks the event loop briefly
- Impact: High-frequency events (>100/sec) may cause delays in alarm UI refresh or event loss
- Improvement path:
  - Buffer events in memory and batch-write to CSV at intervals
  - Use `asyncio.to_thread()` to offload blocking I/O to thread pool
  - Consider async CSV library or switch to JSON-lines format

**Node Tree Traversal Not Parallelized:**
- Problem: `_browse_recursive()` traverses node tree depth-first, awaiting each node fetch sequentially
- Files: `src/opcua_client/browse.py` (_browse_recursive)
- Cause: Simple async recursion; no `asyncio.gather()` for sibling concurrency
- Impact: Large node trees (1000+ nodes) take minutes to browse; blocking on each read
- Improvement path:
  - Use `asyncio.gather(*sibling_reads)` to fetch siblings in parallel
  - Implement depth-first-with-breadth-parallelism: fetch all children of a node concurrently
  - Add optional `--parallel-reads` flag with configurable concurrency limit

**Event Handler State Lookup O(1) but Dict Not Thread-Safe:**
- Problem: `AlarmHandler._active_alarms` dict modified from async subscription callback
- Files: `src/opcua_client/collector.py` (AlarmHandler._update_active_alarms)
- Cause: asyncua event callbacks execute in asyncio context, but dict is not explicitly protected
- Impact: Unlikely in practice (single asyncio thread), but race condition risk if callback scheduling changes
- Improvement path:
  - Use `asyncio.Lock()` for explicit synchronization
  - Consider switching to thread-safe queue (e.g., `asyncio.Queue`) for event buffering
  - Document thread-safety guarantees

## Fragile Areas

**Profile YAML Loading with Defaults:**
- Files: `src/opcua_client/profile_loader.py`, `src/opcua_client/runtime_config.py`
- Why fragile: Missing keys in YAML silently use defaults from dataclass; easy to create broken profiles
- Safe modification: 
  - Always validate required fields (at minimum, `url`) with clear error messages
  - Use `@dataclass` with `field(default_factory=...)` to ensure consistent defaults
  - Add profile validation function with explicit checks
- Test coverage: `tests/test_profile_loader.py` covers missing keys, but error messages could be clearer

**TUI Widget State Synchronization:**
- Files: `src/opcua_client/tui/app.py`, `src/opcua_client/tui/widgets/`
- Why fragile: Alarm events posted as messages to TUI; multiple widgets may update shared state (active alarms dict)
- Safe modification:
  - Minimize shared state; favor message passing (Textual's message system is designed for this)
  - Document expected message sequence and widget responsibilities
  - Add assertions to verify widget assumptions (e.g., AlarmTable expects CSV_HEADERS to match event keys)
- Test coverage: `tests/test_tui_*.py` tests individual widgets but not multi-widget interactions

**OPC UA Connection Retry Logic:**
- Files: `src/opcua_client/condition_refresh.py` (condition_refresh_with_retry)
- Why fragile: Fixed retry delay and hardcoded max attempts; no exponential backoff or configurable limits
- Safe modification:
  - Make retry backoff and max attempts configurable via env vars or config
  - Document retry semantics clearly (e.g., "reconnects every 5 seconds indefinitely")
  - Test with network failures (e.g., firewall drop, timeout vs. hard disconnect)
- Test coverage: No explicit retry tests; relies on manual testing with real servers

## Scaling Limits

**CSV File I/O Single-Threaded:**
- Current capacity: ~100 events/second sustainable (Python csv module limit)
- Limit: Beyond 1000 events/sec, CSV writes become bottleneck
- Scaling path: Switch to async CSV writing or batch-buffer in memory with periodic flush

**Node Tree Memory Usage:**
- Current capacity: ~10,000 nodes browseable without memory pressure
- Limit: Node tree traversal stores all results in memory (list of strings); very large servers may exhaust heap
- Scaling path: Implement lazy loading (on-demand node expansion in TUI) or streaming output for browse command

**Active Alarm State Dictionary:**
- Current capacity: ~10,000 concurrent active alarms trackable
- Limit: Dict lookups remain O(1) but memory scales linearly; TUI rendering slows at high counts
- Scaling path: Implement sliding window (drop oldest alarms) or pagination in AlarmTable widget

## Dependencies at Risk

**asyncua Fragility Around Siemens S7-1500:**
- Risk: asyncua library has known issues with S7-1500 OPC UA server (event filtering rejection)
- Impact: Collectors on Siemens servers would silently lose events without the `where_clause_generation=False` workaround
- Migration plan: 
  - Monitor asyncua issue tracker for improvements
  - If library stalls, consider opcua-asyncio fork or alternative Python OPC UA library (python-opc)
  - Document server compatibility in README (Known Working / Known Issues)

**Textual Framework Stability:**
- Risk: Textual is actively developed; minor versions may introduce breaking changes to widget API
- Impact: TUI widgets may break on version bump if Textual changes Container, Widget, or Message APIs
- Migration plan:
  - Pin Textual to compatible minor version in pyproject.toml (e.g., `textual>=0.87.1,<0.88.0`)
  - Monitor Textual changelog before upgrading
  - Test TUI thoroughly after updates

**Python 3.12+ Requirement:**
- Risk: Locks out users on older Python versions; 3.12 is still relatively new
- Impact: Deployment friction in legacy environments
- Mitigation: Document requirement clearly in README and setup instructions
- Improvement: Consider supporting 3.11 if feasible (use `from __future__ import annotations` for type syntax)

## Missing Critical Features

**Secure Credential Storage:**
- Problem: No built-in credential encryption; passwords stored in plain YAML
- Blocks: Enterprise deployments requiring compliance (FIPS, SOC2)
- Recommended approach: Integrate with system keyring or add optional AES encryption for profile files

**Real-time Statistics and Alerting:**
- Problem: Collector logs events to CSV but provides no thresholds, summaries, or alerts
- Blocks: Operational use as primary alarm monitoring tool
- Recommended approach: Add optional Prometheus metrics endpoint, configurable alarm thresholds, email/Slack alerts

**Server Certificate Pinning:**
- Problem: No mechanism to pin server certificates for specific servers
- Blocks: Defense against MITM attacks in untrusted networks
- Recommended approach: Add `server_cert_sha256` field to profile YAML with validation on connect

**Offline Replay / History Navigation:**
- Problem: TUI shows live events only; no historical browsing or log replay
- Blocks: Post-incident analysis
- Recommended approach: Add CSV history tab, allow loading previous alarm logs, timeline navigation

## Test Coverage Gaps

**Async Event Handling in TUI:**
- Untested area: Message posting from subscription callback to TUI widgets under high-frequency events
- Files: `src/opcua_client/tui/app.py` (subscription task + message system)
- Risk: Race conditions or message loss under stress not caught by tests
- Priority: High (affects data integrity)

**Profile Autosetup Interactive Flow:**
- Untested area: User prompts and YAML generation in `profile_autosetup.py`
- Files: `src/opcua_client/profile_autosetup.py` (ensure_profile_for_url_interactive)
- Risk: Regressions in interactive setup undetected; user experience breaks
- Priority: Medium (affects first-time setup)

**Certificate Renewal and Expiration:**
- Untested area: No tests for auto-generated certificate expiration, renewal, or replacement
- Files: `src/opcua_client/generate_certificates.py`, `src/opcua_client/cert_paths.py`
- Risk: Expired certificates cause silent connection failures
- Priority: Medium (edge case but critical when it occurs)

**TUI Reconnection Under Network Failure:**
- Untested area: Network disconnect/reconnect behavior (connection lost, auto-retry, recovery)
- Files: `src/opcua_client/tui/app.py`, `src/opcua_client/condition_refresh.py`
- Risk: TUI hangs or crashes on network interruption
- Priority: High (affects production usability)

---

*Concerns audit: 2026-03-18*
