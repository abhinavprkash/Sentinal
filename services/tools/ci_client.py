from __future__ import annotations

from typing import Callable

from contracts.models import IncidentEnvelope, PatchProposal


class CIRunner:
    def __init__(
        self,
        force_test_failure: bool = False,
        force_canary_failure: bool = False,
        custom_test_runner: Callable[[PatchProposal], dict[str, str]] | None = None,
    ) -> None:
        self.force_test_failure = force_test_failure
        self.force_canary_failure = force_canary_failure
        self.custom_test_runner = custom_test_runner

    def run_tests(self, patch: PatchProposal) -> dict[str, str]:
        if self.custom_test_runner:
            return self.custom_test_runner(patch)
        if self.force_test_failure:
            return {
                "unit": "passed",
                "integration": "failed",
                "smoke": "passed",
            }
        return {
            "unit": "passed",
            "integration": "passed",
            "smoke": "passed",
        }

    def run_canary_replay(self, incident: IncidentEnvelope, patch: PatchProposal) -> dict[str, float | str]:
        if self.force_canary_failure:
            return {
                "status": "failed",
                "baseline_5xx_rate": float(incident.signal_payload.get("error_rate", 0.2)),
                "post_patch_5xx_rate": float(incident.signal_payload.get("error_rate", 0.2)),
                "latency_delta_ms": 320.0,
            }

        baseline = float(incident.signal_payload.get("error_rate", 0.2))
        summary = patch.diff_summary.lower()
        reduction = 0.15 if "timeout" in summary or "retry" in summary else 0.03
        post_patch = max(0.0, baseline - reduction)
        latency_delta = -250.0 if reduction >= 0.1 else 120.0
        return {
            "status": "passed" if post_patch < baseline and latency_delta < 200.0 else "failed",
            "baseline_5xx_rate": baseline,
            "post_patch_5xx_rate": post_patch,
            "latency_delta_ms": latency_delta,
        }
