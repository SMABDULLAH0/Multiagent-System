from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from integrations import GitHubClient, IntegrationError
from message_bus import AgentMessage


class QAAgent(BaseAgent):
    def __init__(self, *, github: GitHubClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.github = github

    def _review(self, product_spec: dict[str, Any], html: str, marketing_copy: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        first_feature = product_spec["features"][0]["name"]
        if first_feature.lower() not in html.lower():
            issues.append(f"The landing page does not mention the highest-priority feature: {first_feature}.")
        if "waitlist" not in html.lower() and "sign up" not in html.lower():
            issues.append("The landing page CTA is weak or missing a clear conversion action.")
        if len(marketing_copy["tagline"].split()) > 10:
            issues.append("The marketing tagline exceeds the 10-word limit.")
        if "reply" not in marketing_copy["email_body"].lower():
            issues.append("The cold outreach email lacks a direct reply-oriented call to action.")

        verdict = "fail" if issues else "pass"
        inline_comments = [
            {"path": "index.html", "line": 8, "body": "Consider sharpening the visual promise so the hero speaks more directly to the primary persona."},
            {"path": "index.html", "line": 22, "body": "The features section should foreground the top-priority feature before lower-priority benefits."},
        ]
        return {"verdict": verdict, "issues": issues, "inline_comments": inline_comments}

    def handle_message(self, message: AgentMessage) -> None:
        if message.message_type != "task":
            return

        product_spec = message.payload["product_spec"]
        engineer_result = message.payload["engineer_result"]
        marketing_result = message.payload["marketing_result"]
        review = self._review(
            product_spec,
            engineer_result["html_content"],
            marketing_result["marketing_copy"],
        )

        posted_comments: list[dict[str, Any]] = []
        if (
            self.github.enabled
            and not engineer_result.get("dry_run")
            and review["inline_comments"]
            and "github.com" in engineer_result["pr_url"]
        ):
            try:
                pull_number = int(engineer_result["pr_url"].rstrip("/").split("/")[-1])
                for comment in review["inline_comments"]:
                    posted = self.github.post_inline_review_comment(
                        pull_number=pull_number,
                        body=comment["body"],
                        commit_id=engineer_result["commit_sha"],
                        path=comment["path"],
                        line=comment["line"],
                    )
                    posted_comments.append(posted)
            except (IntegrationError, ValueError) as exc:
                self.log("Unable to post inline QA review comments.", {"error": str(exc)})

        self.send_message(
            to_agent="ceo",
            message_type="result",
            payload={
                "review": review,
                "posted_comments_count": len(posted_comments),
            },
            parent_message_id=message.message_id,
        )

