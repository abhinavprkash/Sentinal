# Sentinel MVP

Sentinel is an autonomous multi-agent SRE workflow that converts a `5xx-after-deploy` incident into a verified draft pull request with evidence and rollback steps.

## What Is Implemented
1. FastAPI orchestrator with required APIs:
   - `POST /api/v1/incidents`
   - `GET /api/v1/incidents/{incident_id}`
   - `POST /api/v1/incidents/{incident_id}/approve`
   - `POST /api/v1/incidents/{incident_id}/retry`
2. Full incident pipeline:
   - Triage (severity, dedupe, autonomy policy)
   - Investigation (deployment + metrics + logs correlation)
   - Patch generation (Copilot integration boundary)
   - Verification (tests + canary replay)
   - Approval package + draft PR creation
3. Guardrails:
   - Confidence threshold gate
   - Tool retry limits
   - Patch retry limits
   - No autonomous merge
4. Persistent pattern store (SQLite) for recurring incident memory.
5. OpenTelemetry-compatible tracing hooks.
6. Test suite covering happy path and failure modes.

## Project Structure
1. `contracts/`: canonical events and payload models (+ JSON schemas).
2. `services/orchestrator/`: API service, workflow engine, and agents.
3. `services/tools/`: Azure, GitHub, CI, and patch-generation adapters.
4. `services/verification/`: verification gate logic.
5. `storage/`: SQLite pattern store.
6. `docs/`: architecture, demo flow, and pitch assets.
7. `tests/`: acceptance and scenario tests.

## Quick Start
Install dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the API:

```bash
uvicorn services.orchestrator.app:app --reload --port 8000
```

Trigger a synthetic incident:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/incidents/synthetic/5xx \
  -H "content-type: application/json" \
  -d '{"incident_id":"inc-demo-001","service":"checkout-api","env":"prod"}'
```

## Configuration
Environment variables:
1. `SENTINEL_CONFIDENCE_THRESHOLD` (default `0.65`)
2. `SENTINEL_MAX_PATCH_ATTEMPTS` (default `2`)
3. `SENTINEL_TOOL_RETRY_ATTEMPTS` (default `2`)
4. `SENTINEL_GITHUB_MODE` (`mock` or `real`)
5. `SENTINEL_GITHUB_OWNER`, `SENTINEL_GITHUB_REPO`, `GITHUB_TOKEN`
6. `SENTINEL_PATTERN_DB_PATH`

## Testing
Run:

```bash
pytest -q
```
