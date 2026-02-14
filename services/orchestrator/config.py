from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    confidence_threshold: float = 0.65
    max_patch_attempts: int = 2
    tool_retry_attempts: int = 2
    dedupe_window_minutes: int = 20
    base_branch: str = "main"
    github_owner: str = "demo-org"
    github_repo: str = "demo-service"
    github_mode: str = "mock"
    github_token: str | None = None
    pattern_db_path: str = str(ROOT_DIR / "storage" / "patterns.db")
    autonomous_envs: tuple[str, ...] = ("prod", "staging")

    @classmethod
    def from_env(cls) -> "Settings":
        env_values = os.environ
        autonomous_envs = tuple(
            item.strip()
            for item in env_values.get("SENTINEL_AUTONOMOUS_ENVS", "prod,staging").split(",")
            if item.strip()
        )
        return cls(
            confidence_threshold=float(env_values.get("SENTINEL_CONFIDENCE_THRESHOLD", "0.65")),
            max_patch_attempts=int(env_values.get("SENTINEL_MAX_PATCH_ATTEMPTS", "2")),
            tool_retry_attempts=int(env_values.get("SENTINEL_TOOL_RETRY_ATTEMPTS", "2")),
            dedupe_window_minutes=int(env_values.get("SENTINEL_DEDUPE_WINDOW_MINUTES", "20")),
            base_branch=env_values.get("SENTINEL_BASE_BRANCH", "main"),
            github_owner=env_values.get("SENTINEL_GITHUB_OWNER", "demo-org"),
            github_repo=env_values.get("SENTINEL_GITHUB_REPO", "demo-service"),
            github_mode=env_values.get("SENTINEL_GITHUB_MODE", "mock"),
            github_token=env_values.get("GITHUB_TOKEN"),
            pattern_db_path=env_values.get(
                "SENTINEL_PATTERN_DB_PATH",
                str(ROOT_DIR / "storage" / "patterns.db"),
            ),
            autonomous_envs=autonomous_envs,
        )
