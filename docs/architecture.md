# Sentinel MVP Architecture

## Goal
Deliver a hybrid-real autonomous incident-response loop that turns a `5xx-after-deploy` alert into a verified draft PR in under 10 minutes.

## Runtime Topology
1. **Orchestrator API (`services/orchestrator/app.py`)**
   Exposes incident APIs and runs workflow execution.
2. **Agent Runtime (`services/orchestrator/engine.py` + `services/orchestrator/agents.py`)**
   Implements Triage, Investigation, Patch, Verification, and Approval phases.
3. **Telemetry Tools (`services/tools/azure_monitor.py`)**
   Uses mock Azure Monitor data now; interface is shaped for real Azure integration.
4. **Patch Generation (`services/tools/copilot_agent.py`)**
   Encapsulates Copilot Agent Mode integration boundary.
5. **Verification (`services/verification/runner.py`)**
   Runs tests and canary replay checks.
6. **GitHub PR Publisher (`services/tools/github_client.py`)**
   Creates draft PRs in mock mode or real mode.
7. **Pattern Store (`storage/pattern_store.py`)**
   SQLite persistence for recurring incident patterns and fix signatures.
8. **Observability (`services/orchestrator/telemetry.py`)**
   OpenTelemetry-compatible span hooks for stage-level tracing.

## Control Flow
1. `POST /api/v1/incidents` ingests an alert as `IncidentEnvelope`.
2. `TriageAgent` performs severity classification, dedupe, and autonomy policy checks.
3. `InvestigationAgent` correlates deployments, metrics, and logs to produce `InvestigationPacket`.
4. `PatchAgent` generates `PatchProposal` candidate(s) with max attempt guardrail.
5. `VerificationRunner` validates with tests + canary replay into `VerificationReport`.
6. `ApprovalAgent` creates `ApprovalPackage` and the GitHub draft PR evidence bundle.
7. Human reviewer approves/rejects using `POST /api/v1/incidents/{id}/approve`.

## Guardrails
1. Duplicate suppression within configurable dedupe window.
2. Autonomous handling only for allowed environments and supported signal types.
3. Confidence threshold gate before patch generation.
4. Investigation tool retry with bounded attempts.
5. Verification gate with bounded patch retries before escalation.
6. No autonomous merge; workflow stops at draft PR + approval gate.

## Public Interfaces
1. `POST /api/v1/incidents` -> `{ incident_id, status }`
2. `GET /api/v1/incidents/{incident_id}` -> full incident state, confidence, artifacts, and event history.
3. `POST /api/v1/incidents/{incident_id}/approve` -> `{ state_transition }`
4. `POST /api/v1/incidents/{incident_id}/retry` -> rerun workflow from requested stage.

## Contracts and Schemas
1. `contracts/models.py` defines all runtime contracts.
2. JSON schemas:
   - `contracts/schemas/incident-envelope.schema.json`
   - `contracts/schemas/events.schema.json`
   - `contracts/schemas/approval-package.schema.json`

## Deployment Model
1. Local dev: run FastAPI with mock telemetry and mock GitHub mode.
2. Demo deployment: Azure Container Apps hosting orchestrator.
3. Hybrid-real: keep real GitHub + CI integration while telemetry remains mock or partially real.

## KPI and SLO Targets
1. Alert-to-draft-PR median under 10 minutes.
2. 100% PRs include RCA, evidence links, and rollback steps.
3. Stage-level SLOs:
   - Triage latency
   - Investigation latency
   - Verification duration
   - PR creation success rate
