# External Integrations

**Analysis Date:** 2026-03-18

## APIs & External Services

**OPC UA Servers:**
- Industrial automation PLCs with OPC UA endpoints (e.g., Siemens S7-1500, generic OPC UA)
  - SDK/Client: `asyncua>=1.1.8`
  - Authentication: Username/password or certificate-based (configurable per connection)
  - Security: Supports insecure (None_), signed, and encrypted connections

## Data Storage

**Databases:**
- None - stateless command-line tool and TUI dashboard

**File Storage:**
- Local filesystem only
  - Connection profiles: `connections/` or `~/.config/opcua-client/connections/` (YAML)
  - Alarm/event exports: CSV files (default `alarms.csv`, configurable via `OPCUA_CSV_FILE`)
  - Client certificates: `certs/` directory (auto-generated or user-provided)
  - Debug logs: `logs/debug/` (when debug mode enabled)

**Caching:**
- None persistent - in-memory active alarm state during TUI/collector sessions

## Authentication & Identity

**Auth Provider:**
- Custom - per-connection authentication to OPC UA servers
  - Username/password auth (plaintext within secured TLS channel)
  - Certificate-based authentication (client cert + private key)
  - Insecure mode (no authentication)

**Credential Management:**
- Connection profiles store:
  - Username (plaintext in YAML, intended for read-only accounts)
  - Password (plaintext in YAML, password-protected YAML files recommended)
  - Certificate paths (`cert_file`, `key_file`, `server_cert`)
- Client certificates auto-generated if not provided: `certs/client.pem`, `certs/key.pem`
- Server certificate trust stored per-profile: `trust_cert` boolean flag
- Implementation: `src/opcua_client/profile_loader.py`, `src/opcua_client/cert_paths.py`

## Monitoring & Observability

**Error Tracking:**
- None - errors logged to console and optional file

**Logs:**
- Console: Real-time output via `logging` module
  - Production mode: INFO level
  - Debug mode: DEBUG level
- File (optional): Debug logs to `logs/debug/debug-{timestamp}-pid{pid}.log`
  - Enabled via `OPCUA_LOG_FILE_ENABLED` env var or connection profile `logging.file.enabled`
  - Configured per connection: `logging.level`, `logging.file.path`, `logging.file.name_pattern`
  - Configured globally via `.env`: `OPCUA_LOG_LEVEL`, `OPCUA_LOG_FILE_PATH`, etc.
- Implementation: `src/opcua_client/cli.py` (_configure_logging)

## CI/CD & Deployment

**Hosting:**
- Command-line tool distributed via PyPI (installable via `uv tool install`)
- TUI requires local terminal environment

**CI Pipeline:**
- GitHub Actions (inferred from `.github/` directory presence)
- Test via `pytest` (see `pyproject.toml` dev dependencies)

## Environment Configuration

**Required env vars:**
- `OPCUA_URL` - OPC UA server endpoint (e.g., `opc.tcp://192.168.1.100:4840`)

**Optional env vars (with defaults):**
- `OPCUA_MODE` - `prod` or `debug` (default: `prod`)
- `OPCUA_LOG_LEVEL` - DEBUG|INFO|WARNING|ERROR|CRITICAL (default: `INFO`)
- `OPCUA_TIMEOUT` - Connection timeout in seconds (default: 30.0)
- `OPCUA_SESSION_TIMEOUT` - OPC UA session timeout in ms (default: 60000)
- `OPCUA_REQUEST_TIMEOUT` - OPC UA request timeout in ms (default: 20000)
- `OPCUA_USERNAME` - OPC UA username (default: empty)
- `OPCUA_PASSWORD` - OPC UA password (default: empty, should be in secured profile YAML)
- `OPCUA_AUTH_POLICY` - OPC UA auth policy string (default: `None`)
- `OPCUA_SECURITY_MODE` - Security mode: `None_`, `Sign`, `SignAndEncrypt` (default: `None_`)
- `OPCUA_CERT_FILE` - Path to client certificate (auto-generated if not provided)
- `OPCUA_KEY_FILE` - Path to client key (auto-generated if not provided)
- `OPCUA_SERVER_CERT` - Path to server certificate file
- `OPCUA_TRUST_CERT` - Trust server certificate without verification (default: false)
- `OPCUA_CSV_FILE` - Alarm export CSV path (default: `alarms.csv`)
- `OPCUA_PUBLISH_INTERVAL_MS` - Event publish interval (default: 500)
- `OPCUA_RECONNECT_DELAY_SEC` - Reconnection delay (default: 5)
- `OPCUA_MAX_DEPTH` - Browse tree max depth (default: 3)
- `OPCUA_TARGET_NAMESPACES` - Comma-separated namespace indices to filter (default: empty = all)
- `OPCUA_PROFILE_DIR` - Directory for connection profiles (default: `connections`)
- `OPCUA_CERT_BASE_DIR` - Base directory for certificates (default: `certs`)
- `OPCUA_LOG_FILE_ENABLED` - Enable file logging (default: false, true in debug mode)
- `OPCUA_LOG_FILE_PATH` - Directory for debug logs (default: `logs/debug`)
- `OPCUA_LOG_FILE_NAME_PATTERN` - Log filename pattern (default: `debug-{timestamp}-pid{pid}.log`)

**Secrets location:**
- Connection profile YAML files (typically in `~/.config/opcua-client/connections/` for user profiles)
  - Should be protected with filesystem permissions (mode 0600 recommended)
  - Password-protected YAML can be used for additional security layer

## Webhooks & Callbacks

**Incoming:**
- None - tool initiates connections to OPC UA servers

**Outgoing:**
- CSV alarm events appended to local file (no network transmission)
- Connection profiles can be auto-generated and saved locally

---

*Integration audit: 2026-03-18*
