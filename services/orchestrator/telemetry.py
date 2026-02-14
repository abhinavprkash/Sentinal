from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover - optional dependency
    trace = None


def _get_tracer():
    if trace is None:
        return None
    return trace.get_tracer("sentinel.orchestrator")


@contextmanager
def traced_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    tracer = _get_tracer()
    if tracer is None:
        yield
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield
