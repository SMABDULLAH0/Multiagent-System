from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent
from integrations import IntegrationError, SendGridClient, SlackClient
from message_bus import AgentMessage


class MarketingAgent(BaseAgent):
    def __init__(self, *, slack: SlackClient, sendgrid: SendGridClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self.slack = slack
        self.sendgrid = sendgrid

    def _fallback_copy(self, product_spec: dict[str, Any], pr_url: str) -> dict[str, Any]:
        first_feature = product_spec["features"][0]["name"]
        return {
            "tagline": "Campus selling, minus the chaos",
            "description": (
                f"{product_spec['value_proposition']} The first launch highlights {first_feature} "
                "and a faster path from listing to first interested buyer."
            ),
            "email_subject": "Early access invite for a simpler campus marketplace",
            "email_body": (
                f"Hi there,\n\nWe are launching a focused product for students who need a cleaner way to buy "
                f"and sell academic essentials. {product_spec['value_proposition']}\n\n"
                f"We just shipped the first landing page here: {pr_url}\n"
                "If this sounds useful, reply and we will add you to the first test group.\n\nBest,\nLaunchMind"
            ),
            "social_posts": {
                "twitter": "Students should not have to scroll through spam to find the right book. A cleaner campus marketplace is on the way.",
                "linkedin": "We are building a student-first marketplace focused on trust, speed, and affordability. Early launch assets are live for review.",
                "instagram": "Less spam. More deals. A campus marketplace designed for actual student workflows is almost here.",
            },
        }

    def _generate_copy(self, product_spec: dict[str, Any], pr_url: str, feedback: str | None) -> dict[str, Any]:
        system_prompt = (
            "You are a growth marketer. Return only JSON with keys: tagline, description, "
            "email_subject, email_body, social_posts."
        )
        user_prompt = (
            f"Product spec:\n{json.dumps(product_spec, indent=2)}\n"
            f"GitHub PR URL: {pr_url}\n"
            f"Revision feedback: {feedback or 'None'}\n"
            "Rules:\n"
            "- tagline under 10 words\n"
            "- description 2 to 3 sentences\n"
            "- email should be a cold outreach email with a clear CTA\n"
            "- social_posts should contain twitter, linkedin, instagram\n"
            "Return valid JSON only."
        )
        return self.llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=lambda: self._fallback_copy(product_spec, pr_url),
        )

    def _slack_blocks(self, tagline: str, description: str, pr_url: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"New Launch: {tagline}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": description},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*GitHub PR:*\n<{pr_url}|View pull request>"},
                    {"type": "mrkdwn", "text": "*Status:*\nReady for review"},
                ],
            },
        ]

    def handle_message(self, message: AgentMessage) -> None:
        if message.message_type not in {"task", "revision_request"}:
            return

        product_spec = message.payload["product_spec"]
        pr_url = message.payload["pr_url"]
        feedback = message.payload.get("feedback")
        marketing_copy = self._generate_copy(product_spec, pr_url, feedback)

        email_status = {"mode": "dry-run"}
        slack_status = {"mode": "dry-run"}

        if self.sendgrid.enabled:
            try:
                self.sendgrid.send_email(
                    subject=marketing_copy["email_subject"],
                    html_body=marketing_copy["email_body"].replace("\n", "<br />"),
                )
                email_status = {"mode": "live", "to": self.sendgrid.to_email}
            except IntegrationError as exc:
                email_status = {"mode": "failed", "error": str(exc)}

        if self.slack.enabled:
            try:
                self.slack.post_blocks(
                    self._slack_blocks(
                        marketing_copy["tagline"],
                        marketing_copy["description"],
                        pr_url,
                    )
                )
                slack_status = {"mode": "live", "channel": self.slack.channel}
            except IntegrationError as exc:
                slack_status = {"mode": "failed", "error": str(exc)}

        self.send_message(
            to_agent="ceo",
            message_type="result",
            payload={
                "marketing_copy": marketing_copy,
                "email_status": email_status,
                "slack_status": slack_status,
            },
            parent_message_id=message.message_id,
        )

