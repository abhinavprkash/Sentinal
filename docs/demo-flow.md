# Sentinel Demo Flow

## Prerequisites
1. Python 3.11+
2. Install dependencies:
   `python -m pip install -e ".[dev]"`
3. Optional real GitHub PR mode:
   - `export SENTINEL_GITHUB_MODE=real`
   - `export SENTINEL_GITHUB_OWNER=<owner>`
   - `export SENTINEL_GITHUB_REPO=<repo>`
   - `export GITHUB_TOKEN=<token>`

## Start the Orchestrator
Run:

```bash
uvicorn services.orchestrator.app:app --reload --port 8000
```

## Demo Script (Synthetic Incident)
1. Trigger synthetic 5xx incident:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/incidents/synthetic/5xx \
  -H "content-type: application/json" \
  -d '{"incident_id":"inc-demo-001","service":"checkout-api","env":"prod"}'
```

2. Fetch full incident evidence:

```bash
curl -sS http://127.0.0.1:8000/api/v1/incidents/inc-demo-001
```

3. Approve from GitHub-style gate:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/incidents/inc-demo-001/approve \
  -H "content-type: application/json" \
  -d '{"approved_by":"oncall@example.com","decision":"approve","notes":"Reviewed and accepted"}'
```

## Talking Points During Demo
1. Triage dedupe and policy checks prevent unsafe autonomous action.
2. Investigation links 5xx spike to latest deployment and error logs.
3. Patch is constrained and rollback-safe.
4. Verification blocks regressions before PR creation.
5. Approval package provides RCA, telemetry evidence, and executable rollback plan.
6. No autonomous merge occurs without explicit human sign-off.

## Failure-Path Demo Options
1. Low confidence path:
   send unsupported signal type (`cpu_high`) and show escalation.
2. Verification failure path:
   run with `CIRunner(force_test_failure=True)` in tests to show blocked PR.
3. Tool outage path:
   use failing Azure tool mock and show retry + safe stop behavior.
