from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class IntegrationError(RuntimeError):
    pass


def _http_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise IntegrationError(f"{method} {url} failed: {exc.code} {details}") from exc
    except urllib.error.URLError as exc:
        raise IntegrationError(f"{method} {url} failed: {exc.reason}") from exc


class GitHubClient:
    def __init__(self) -> None:
        self.token = os.getenv("GITHUB_TOKEN")
        self.repository = os.getenv("GITHUB_REPOSITORY")
        self.base_branch = os.getenv("GITHUB_BASE_BRANCH", "main")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.repository)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def get_branch_sha(self, branch: str) -> str:
        response = _http_json(
            method="GET",
            url=f"https://api.github.com/repos/{self.repository}/git/ref/heads/{branch}",
            headers=self.headers,
        )
        return response["object"]["sha"]

    def create_branch(self, branch: str, from_branch: str | None = None) -> str:
        base_sha = self.get_branch_sha(from_branch or self.base_branch)
        try:
            _http_json(
                method="POST",
                url=f"https://api.github.com/repos/{self.repository}/git/refs",
                headers=self.headers,
                payload={"ref": f"refs/heads/{branch}", "sha": base_sha},
            )
        except IntegrationError as exc:
            if "Reference already exists" not in str(exc):
                raise
        return base_sha

    def create_issue(self, title: str, body: str) -> dict[str, Any]:
        return _http_json(
            method="POST",
            url=f"https://api.github.com/repos/{self.repository}/issues",
            headers=self.headers,
            payload={"title": title, "body": body},
        )

    def upsert_file(
        self,
        *,
        path: str,
        content: str,
        branch: str,
        message: str,
        author_name: str,
        author_email: str,
    ) -> dict[str, Any]:
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        url = f"https://api.github.com/repos/{self.repository}/contents/{path}"
        sha = None
        try:
            existing = _http_json(method="GET", url=f"{url}?ref={branch}", headers=self.headers)
            sha = existing.get("sha")
        except IntegrationError:
            sha = None

        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
            "committer": {"name": author_name, "email": author_email},
            "author": {"name": author_name, "email": author_email},
        }
        if sha:
            payload["sha"] = sha
        return _http_json(method="PUT", url=url, headers=self.headers, payload=payload)

    def create_pull_request(self, title: str, body: str, head: str) -> dict[str, Any]:
        return _http_json(
            method="POST",
            url=f"https://api.github.com/repos/{self.repository}/pulls",
            headers=self.headers,
            payload={
                "title": title,
                "body": body,
                "head": head,
                "base": self.base_branch,
            },
        )

    def post_inline_review_comment(
        self,
        *,
        pull_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
    ) -> dict[str, Any]:
        return _http_json(
            method="POST",
            url=f"https://api.github.com/repos/{self.repository}/pulls/{pull_number}/comments",
            headers=self.headers,
            payload={
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": "RIGHT",
            },
        )


class SlackClient:
    def __init__(self) -> None:
        self.token = os.getenv("SLACK_BOT_TOKEN")
        self.channel = os.getenv("SLACK_CHANNEL", "#launches")

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def post_blocks(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"channel": self.channel, "blocks": blocks}
        return _http_json(
            method="POST",
            url="https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )


class SendGridClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL")
        self.to_email = os.getenv("SENDGRID_TO_EMAIL")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.from_email and self.to_email)

    def send_email(self, subject: str, html_body: str) -> dict[str, Any]:
        return _http_json(
            method="POST",
            url="https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "personalizations": [{"to": [{"email": self.to_email}]}],
                "from": {"email": self.from_email},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_body}],
            },
        )

