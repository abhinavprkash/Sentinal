# Sentinel Hackathon Pitch Outline

## 1. Problem
Cloud-native on-call teams lose hours per incident to manual correlation and coordination. MTTR is often driven by toil, not fix complexity.

## 2. Solution
Sentinel is a multi-agent SRE system that converts production alerts into verified draft PRs:
1. Triage
2. Investigation
3. Patch generation
4. Verification
5. Human approval gate

## 3. Differentiators
1. End-to-end alert-to-PR automation.
2. Evidence-backed outputs: logs, metrics, deployment correlation, RCA.
3. Safe-by-default controls: confidence threshold, retry limits, verification gate, no auto-merge.
4. Pattern memory: recurring incidents become faster and more standardized.

## 4. Demo Narrative
1. Trigger synthetic 5xx-after-deploy incident.
2. Show correlated telemetry and root-cause hypothesis.
3. Show generated patch and verification report.
4. Show draft PR containing RCA, evidence links, rollback plan.
5. Show explicit human approval step.

## 5. Impact Metrics
1. Alert-to-draft-PR under 10 minutes.
2. 100% of PRs include rollback plan and telemetry evidence.
3. Reduced repeated on-call toil for known incident patterns.

## 6. Technical Stack Alignment
1. Microsoft Agent Framework-compatible orchestration boundary.
2. Azure MCP-style tool adapters.
3. GitHub Copilot Agent Mode integration boundary.
4. Azure Container Apps deployment target.
5. OpenTelemetry-compatible trace instrumentation.
