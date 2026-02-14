from __future__ import annotations

from contracts.models import IncidentEnvelope, InvestigationPacket, PatchProposal


class CopilotPatchGenerator:
    def __init__(self, repo_slug: str) -> None:
        self.repo_slug = repo_slug

    def generate_patch(
        self,
        incident: IncidentEnvelope,
        investigation: InvestigationPacket,
        attempt: int = 1,
    ) -> PatchProposal:
        summary = "Increase upstream timeout and retry budget for checkout dependency."
        changed_files = ["config/retries.yaml", "config/timeouts.yaml"]
        patch_text = (
            "--- a/config/timeouts.yaml\n"
            "+++ b/config/timeouts.yaml\n"
            "@@ -2,5 +2,5 @@\n"
            "-payments_timeout_ms: 400\n"
            "+payments_timeout_ms: 900\n"
            "--- a/config/retries.yaml\n"
            "+++ b/config/retries.yaml\n"
            "@@ -1,4 +1,4 @@\n"
            "-payments_max_retries: 1\n"
            "+payments_max_retries: 3\n"
        )
        lowered_evidence = " ".join(investigation.log_evidence).lower()
        if "connection" in lowered_evidence and "pool" in lowered_evidence:
            summary = "Increase DB pool ceiling and backoff for transient failures."
            changed_files = ["config/db_pool.yaml"]
            patch_text = (
                "--- a/config/db_pool.yaml\n"
                "+++ b/config/db_pool.yaml\n"
                "@@ -1,5 +1,5 @@\n"
                "-max_connections: 25\n"
                "+max_connections: 45\n"
            )

        return PatchProposal(
            repo=self.repo_slug,
            branch=f"sentinel/{incident.incident_id}-attempt-{attempt}",
            changed_files=changed_files,
            diff_summary=summary,
            hypothesis=investigation.reason,
            risk_level="low",
            patch_text=patch_text,
        )
