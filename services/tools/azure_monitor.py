from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.tools.synthetic_data import default_telemetry_dataset


class AzureMonitorTool:
    def get_recent_deployments(self, service: str, env: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_metrics(
        self,
        service: str,
        env: str,
        metric_name: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_logs(
        self,
        service: str,
        env: str,
        contains: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockAzureMonitorTool(AzureMonitorTool):
    def __init__(self, dataset: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] | None = None) -> None:
        self.dataset = dataset or default_telemetry_dataset()

    def _bucket(self, service: str, env: str) -> dict[str, list[dict[str, Any]]]:
        return self.dataset.get((service, env), {"deployments": [], "metrics": [], "logs": []})

    def get_recent_deployments(self, service: str, env: str) -> list[dict[str, Any]]:
        deployments = deepcopy(self._bucket(service, env).get("deployments", []))
        deployments.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return deployments

    def query_metrics(
        self,
        service: str,
        env: str,
        metric_name: str | None = None,
    ) -> list[dict[str, Any]]:
        metrics = deepcopy(self._bucket(service, env).get("metrics", []))
        if metric_name:
            metrics = [metric for metric in metrics if metric.get("name") == metric_name]
        metrics.sort(key=lambda item: item.get("timestamp", ""))
        return metrics

    def query_logs(
        self,
        service: str,
        env: str,
        contains: str | None = None,
    ) -> list[dict[str, Any]]:
        logs = deepcopy(self._bucket(service, env).get("logs", []))
        if contains:
            token = contains.lower()
            logs = [log for log in logs if token in str(log.get("message", "")).lower()]
        logs.sort(key=lambda item: item.get("timestamp", ""))
        return logs
