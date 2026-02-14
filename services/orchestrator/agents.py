from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from contracts.models import (
    ApprovalPackage,
    IncidentEnvelope,
    IncidentStatus,
    InvestigationPacket,
    PatchProposal,
    Severity,
    VerificationReport,
)
from services.tools.azure_monitor import AzureMonitorTool
from services.tools.copilot_agent import CopilotPatchGenerator
from services.tools.github_client import PullRequestInfo
from storage.pattern_store import PatternStore


@dataclass
class TriageResult:
    status: IncidentStatus
    severity: Severity
    allow_autonomous: bool
    reason: str


class TriageAgent:
    def __init__(self, autonomous_envs: tuple[str, ...]) -> None:
        self.autonomous_envs = set(autonomous_envs)

    def evaluate(self, incident: IncidentEnvelope, has_duplicates: bool) -> TriageResult:
        error_rate = float(incident.signal_payload.get("error_rate", 0.0))
        severity = Severity.LOW
        if error_rate >= 0.20:
            severity = Severity.CRITICAL
        elif error_rate >= 0.12:
            severity = Severity.HIGH
        elif error_rate >= 0.05:
            severity = Severity.MEDIUM

        if has_duplicates:
            return TriageResult(
                status=IncidentStatus.DUPLICATE,
                severity=severity,
                allow_autonomous=False,
                reason="Duplicate alert within dedupe window.",
            )

        if incident.signal_type != "http_5xx_rate":
            return TriageResult(
                status=IncidentStatus.BLOCKED,
                severity=severity,
                allow_autonomous=False,
                reason=f"Unsupported signal type for autonomous handling: {incident.signal_type}",
            )

        if incident.env not in self.autonomous_envs:
            return TriageResult(
                status=IncidentStatus.BLOCKED,
                severity=severity,
                allow_autonomous=False,
                reason=f"Environment '{incident.env}' is outside autonomous policy.",
            )

        return TriageResult(
            status=IncidentStatus.INVESTIGATING,
            severity=severity,
            allow_autonomous=True,
            reason="Incident accepted for autonomous pipeline.",
        )


class InvestigationAgent:
    def __init__(self, azure_tool: AzureMonitorTool, pattern_store: PatternStore) -> None:
        self.azure_tool = azure_tool
        self.pattern_store = pattern_store

    def investigate(self, incident: IncidentEnvelope) -> InvestigationPacket:
        deployments = self.azure_tool.get_recent_deployments(incident.service, incident.env)
        metrics = self.azure_tool.query_metrics(incident.service, incident.env, metric_name="http_5xx_rate")
        logs = self.azure_tool.query_logs(incident.service, incident.env)

        confidence = 0.30
        reason_parts = []

        suspected_release = "unknown"
        if deployments:
            suspected_release = deployments[0].get("version", deployments[0].get("deployment_id", "unknown"))
            confidence += 0.25
            reason_parts.append(f"Error spike follows deployment {suspected_release}.")

        max_5xx_rate = max((float(metric.get("value", 0.0)) for metric in metrics), default=0.0)
        if max_5xx_rate >= 0.05:
            confidence += 0.20
            reason_parts.append(f"Observed elevated 5xx rate at {max_5xx_rate:.2f}.")

        log_messages = [str(item.get("message", "")) for item in logs if item.get("level") in {"ERROR", "CRITICAL"}]
        if log_messages:
            confidence += 0.20
            reason_parts.append("Error logs indicate upstream timeout/retry exhaustion.")

        historical_match = self.pattern_store.find_latest(incident.fingerprint)
        if historical_match:
            confidence += 0.10
            reason_parts.append("Pattern store contains a similar historical incident.")

        confidence = min(confidence, 0.99)
        if not reason_parts:
            reason_parts.append("Insufficient telemetry correlation for root-cause confidence.")

        endpoints = sorted(
            set(
                metric.get("endpoint") for metric in metrics if metric.get("endpoint")
            )
        ) or [str(incident.signal_payload.get("endpoint", "global"))]
        correlated_metrics = {
            "max_5xx_rate": max_5xx_rate,
            "metric_points": len(metrics),
            "log_points": len(log_messages),
            "deployments_seen": len(deployments),
        }
        return InvestigationPacket(
            suspected_release=suspected_release,
            affected_endpoints=endpoints,
            correlated_metrics=correlated_metrics,
            log_evidence=log_messages[:5],
            confidence=confidence,
            reason=" ".join(reason_parts),
        )


class PatchAgent:
    def __init__(self, generator: CopilotPatchGenerator) -> None:
        self.generator = generator

    def propose_patch(
        self,
        incident: IncidentEnvelope,
        investigation: InvestigationPacket,
        attempt: int,
    ) -> PatchProposal:
        return self.generator.generate_patch(incident, investigation, attempt=attempt)


class ApprovalAgent:
    def __init__(self, base_branch: str) -> None:
        self.base_branch = base_branch

    def build_approval_package(
        self,
        incident: IncidentEnvelope,
        investigation: InvestigationPacket,
        patch: PatchProposal,
        verification: VerificationReport,
        pr_info: PullRequestInfo,
    ) -> ApprovalPackage:
        evidence_links = {
            "metrics_dashboard": (
                f"https://portal.azure.com/#blade/SentinelMetrics/{incident.service}/{incident.env}"
            ),
            "logs_query": (
                f"https://portal.azure.com/#blade/SentinelLogs/{incident.service}/{incident.env}"
            ),
            "deployment_trace": (
                f"https://dev.azure.com/demo/{incident.service}/_releaseProgress?release={investigation.suspected_release}"
            ),
        }
        rollback_steps = [
            f"Create rollback branch from {self.base_branch}.",
            f"Revert deployment/config changes associated with release {investigation.suspected_release}.",
            "Re-run staging verification and monitor 5xx for 15 minutes before production rollout.",
        ]
        telemetry_snapshot = {
            "incident_id": incident.incident_id,
            "service": incident.service,
            "env": incident.env,
            "max_5xx_rate": investigation.correlated_metrics.get("max_5xx_rate"),
            "canary_post_patch_5xx_rate": verification.canary_replay_result.get("post_patch_5xx_rate"),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        rca_summary = (
            f"Deployment {investigation.suspected_release} introduced elevated 5xx responses "
            f"on {', '.join(investigation.affected_endpoints)}; logs indicate upstream timeout pressure."
        )
        return ApprovalPackage(
            pr_url=pr_info.pr_url,
            rca_summary=rca_summary,
            evidence_links=evidence_links,
            rollback_steps=rollback_steps,
            telemetry_snapshot=telemetry_snapshot,
        )

    def build_pr_body(
        self,
        incident: IncidentEnvelope,
        investigation: InvestigationPacket,
        patch: PatchProposal,
        verification: VerificationReport,
        package: ApprovalPackage,
    ) -> str:
        evidence_lines = "\n".join(
            [f"- {label}: {url}" for label, url in package.evidence_links.items()]
        )
        rollback_lines = "\n".join([f"1. {step}" for step in package.rollback_steps])
        regression = ", ".join(verification.regression_flags) if verification.regression_flags else "none"
        return (
            f"## Sentinel Auto-Generated Fix\n\n"
            f"Incident: `{incident.incident_id}`\n"
            f"Service: `{incident.service}`\n"
            f"Environment: `{incident.env}`\n\n"
            f"### Root Cause Analysis\n"
            f"{package.rca_summary}\n\n"
            f"### Patch Hypothesis\n"
            f"{patch.hypothesis}\n\n"
            f"### Verification Summary\n"
            f"- pass_fail: `{verification.pass_fail}`\n"
            f"- regression_flags: `{regression}`\n"
            f"- canary_result: `{verification.canary_replay_result}`\n\n"
            f"### Evidence Links\n"
            f"{evidence_lines}\n\n"
            f"### Rollback Plan\n"
            f"{rollback_lines}\n\n"
            f"### Diff Summary\n"
            f"{patch.diff_summary}\n"
        )
