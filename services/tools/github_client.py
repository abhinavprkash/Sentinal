from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class PullRequestInfo:
    pr_url: str
    number: int | None
    title: str
    head_branch: str
    base_branch: str


class GitHubClient:
    def __init__(
        self,
        owner: str,
        repo: str,
        token: str | None = None,
        mode: str = "mock",
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.mode = mode
        self.created_prs: list[PullRequestInfo] = []

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def create_draft_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> PullRequestInfo:
        if self.mode == "real":
            return self._create_real_pr(title, body, head_branch, base_branch)
        return self._create_mock_pr(title, head_branch, base_branch)

    def _create_mock_pr(self, title: str, head_branch: str, base_branch: str) -> PullRequestInfo:
        pr_number = int(hashlib.sha256(head_branch.encode("utf-8")).hexdigest()[:6], 16) % 100000
        pr_url = f"https://github.com/{self.repo_slug}/pull/{pr_number}"
        pr_info = PullRequestInfo(
            pr_url=pr_url,
            number=pr_number,
            title=title,
            head_branch=head_branch,
            base_branch=base_branch,
        )
        self.created_prs.append(pr_info)
        return pr_info

    def _create_real_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> PullRequestInfo:
        if not self.token:
            raise RuntimeError("GitHub token is required for real mode.")
        payload = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
            "draft": True,
        }
        request = urllib.request.Request(
            url=f"https://api.github.com/repos/{self.repo_slug}/pulls",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "sentinel-mvp",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"GitHub API error ({exc.code}): {body_text}") from exc

        pr_info = PullRequestInfo(
            pr_url=str(data["html_url"]),
            number=int(data["number"]),
            title=str(data["title"]),
            head_branch=head_branch,
            base_branch=base_branch,
        )
        self.created_prs.append(pr_info)
        return pr_info

    def list_created_prs(self) -> list[dict[str, Any]]:
        return [pr.__dict__.copy() for pr in self.created_prs]
