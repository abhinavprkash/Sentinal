from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameworkStatus:
    semantic_kernel_available: bool
    autogen_available: bool


def detect_framework_status() -> FrameworkStatus:
    semantic_kernel_available = importlib.util.find_spec("semantic_kernel") is not None
    autogen_available = importlib.util.find_spec("autogen") is not None

    return FrameworkStatus(
        semantic_kernel_available=semantic_kernel_available,
        autogen_available=autogen_available,
    )
