from __future__ import annotations

from contracts.models import IncidentEnvelope, PatchProposal, VerificationReport
from services.tools.ci_client import CIRunner


class VerificationRunner:
    def __init__(self, ci_runner: CIRunner) -> None:
        self.ci_runner = ci_runner

    def verify(self, incident: IncidentEnvelope, patch: PatchProposal) -> VerificationReport:
        test_results = self.ci_runner.run_tests(patch)
        canary = self.ci_runner.run_canary_replay(incident, patch)

        regression_flags: list[str] = []
        for suite_name, status in test_results.items():
            if status != "passed":
                regression_flags.append(f"{suite_name}_failed")
        if canary.get("status") != "passed":
            regression_flags.append("canary_replay_failed")
        if float(canary.get("latency_delta_ms", 0.0)) > 200.0:
            regression_flags.append("latency_regression")

        pass_fail = len(regression_flags) == 0
        return VerificationReport(
            test_results=test_results,
            canary_replay_result=canary,
            regression_flags=regression_flags,
            pass_fail=pass_fail,
        )
