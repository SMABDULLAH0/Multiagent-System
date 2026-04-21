from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from config import env_flag
from integrations import IntegrationError, SlackClient
from message_bus import AgentMessage


class CEOAgent(BaseAgent):
    def __init__(self, *, slack: SlackClient, include_qa: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self.slack = slack
        self.include_qa = include_qa
        self.force_feedback_loop = env_flag("LAUNCHMIND_FORCE_FEEDBACK_LOOP", True)
        self.completed = False
        self.decisions: list[dict[str, Any]] = []
        self.decomposition: dict[str, Any] = {}
        self.startup_idea = ""
        self.product_spec: dict[str, Any] | None = None
        self.engineer_result: dict[str, Any] | None = None
        self.marketing_result: dict[str, Any] | None = None
        self.qa_result: dict[str, Any] | None = None
        self.product_revision_cycles = 0
        self.qa_revision_cycles = 0
        self.marketing_started = False
        self.engineering_started = False
        self.qa_started = False

    def _record_decision(self, decision: str, reason: str) -> None:
        item = {"decision": decision, "reason": reason}
        self.decisions.append(item)
        self.log("Decision recorded", item)

    def _fallback_decomposition(self, idea: str) -> dict[str, Any]:
        return {
            "product": {
                "focus": "Define user personas, rank the top five features, and make the user stories concrete.",
            },
            "engineer": {
                "focus": "Build a polished HTML landing page with a strong hero, top features, and a clear CTA.",
            },
            "marketing": {
                "focus": "Create launch messaging, a cold outreach email, and social copy for an early product reveal.",
            },
            "qa": {
                "focus": "Check that the landing page and marketing copy match the product spec and flag anything vague.",
            },
            "summary": f"Launch a micro-startup around: {idea}",
        }

    def bootstrap(self, startup_idea: str) -> None:
        self.startup_idea = startup_idea
        system_prompt = "You are a startup CEO. Return only JSON with keys product, engineer, marketing, qa, summary."
        user_prompt = (
            f"Startup idea: {startup_idea}\n"
            "Create structured task guidance for the Product, Engineer, Marketing, and QA agents."
        )
        self.decomposition = self.llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=lambda: self._fallback_decomposition(startup_idea),
        )
        self._record_decision("decompose_startup", "The startup idea was decomposed into role-specific tasks.")
        self.send_message(
            to_agent="product",
            message_type="task",
            payload={
                "idea": startup_idea,
                "focus": self.decomposition["product"]["focus"],
            },
        )

    def _review_product_spec(self, product_spec: dict[str, Any]) -> dict[str, Any]:
        system_prompt = "You are a CEO reviewing product specifications. Return only JSON."
        user_prompt = (
            "Review this product spec for specificity and usefulness. "
            "Return JSON with keys approved (boolean), feedback (string), strengths (array).\n"
            f"{json.dumps(product_spec, indent=2)}"
        )
        fallback = {
            "approved": True,
            "feedback": "Approved.",
            "strengths": ["Clear value proposition", "Feature prioritization is present"],
        }
        review = self.llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=lambda: fallback,
        )

        if self.force_feedback_loop and self.product_revision_cycles == 0:
            review["approved"] = False
            review["feedback"] = (
                "Tighten the personas with more concrete pain points and make the feature priorities feel more differentiated."
            )
        return review

    def _review_qa_report(self, review: dict[str, Any]) -> tuple[bool, str]:
        if review["verdict"] == "pass":
            return True, "QA passed. Proceed to final launch summary."
        return False, "QA found issues that should trigger a revision cycle."

    def _maybe_start_engineering(self) -> None:
        if self.product_spec and not self.engineering_started:
            self.engineering_started = True
            self._record_decision("start_engineering", "The product spec was approved and is ready for implementation.")
            self.send_message(
                to_agent="engineer",
                message_type="task",
                payload={
                    "product_spec": self.product_spec,
                    "focus": self.decomposition["engineer"]["focus"],
                },
            )

    def _maybe_start_marketing(self) -> None:
        if self.product_spec and self.engineer_result and not self.marketing_started:
            self.marketing_started = True
            self._record_decision("start_marketing", "The PR URL is available, so marketing can send launch assets to Slack and email.")
            self.send_message(
                to_agent="marketing",
                message_type="task",
                payload={
                    "product_spec": self.product_spec,
                    "pr_url": self.engineer_result["pr_url"],
                    "focus": self.decomposition["marketing"]["focus"],
                },
            )

    def _maybe_start_qa(self) -> None:
        if (
            self.include_qa
            and self.product_spec
            and self.engineer_result
            and self.marketing_result
            and not self.qa_started
        ):
            self.qa_started = True
            self._record_decision("start_qa", "Both engineering and marketing outputs are ready for review.")
            self.send_message(
                to_agent="qa",
                message_type="task",
                payload={
                    "product_spec": self.product_spec,
                    "engineer_result": self.engineer_result,
                    "marketing_result": self.marketing_result,
                    "focus": self.decomposition["qa"]["focus"],
                },
            )

    def _post_final_summary(self) -> dict[str, Any]:
        summary = {
            "idea": self.startup_idea,
            "product_value_proposition": self.product_spec["value_proposition"] if self.product_spec else "",
            "pr_url": self.engineer_result["pr_url"] if self.engineer_result else "",
            "issue_url": self.engineer_result["issue_url"] if self.engineer_result else "",
            "tagline": self.marketing_result["marketing_copy"]["tagline"] if self.marketing_result else "",
            "qa_verdict": self.qa_result["review"]["verdict"] if self.qa_result else "not_run",
            "decision_count": len(self.decisions),
        }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "LaunchMind Final Summary"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Idea:* {summary['idea']}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Tagline:*\n{summary['tagline']}"},
                    {"type": "mrkdwn", "text": f"*QA verdict:*\n{summary['qa_verdict']}"},
                    {"type": "mrkdwn", "text": f"*PR:*\n<{summary['pr_url']}|Open PR>"},
                    {"type": "mrkdwn", "text": f"*Issue:*\n<{summary['issue_url']}|Open issue>"},
                ],
            },
        ]
        slack_result = {"mode": "dry-run"}
        if self.slack.enabled:
            try:
                self.slack.post_blocks(blocks)
                slack_result = {"mode": "live", "channel": self.slack.channel}
            except IntegrationError as exc:
                slack_result = {"mode": "failed", "error": str(exc)}

        decision_log_path = self.output_dir / "decision_log.json"
        decision_log_path.write_text(json.dumps(self.decisions, indent=2), encoding="utf-8")
        summary["slack_result"] = slack_result
        summary["decision_log_path"] = str(decision_log_path)
        return summary

    def _finalize(self) -> None:
        if self.completed:
            return
        summary = self._post_final_summary()
        summary_path = self.output_dir / "final_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self.completed = True
        self._record_decision("finalize", "All required outputs were collected and summarized.")
        self.log("LaunchMind run completed", summary)

    def handle_message(self, message: AgentMessage) -> None:
        if message.from_agent == "product" and message.message_type == "result":
            product_spec = message.payload["product_spec"]
            review = self._review_product_spec(product_spec)
            if review.get("approved"):
                self.product_spec = product_spec
                self._record_decision("approve_product_spec", "The product specification passed CEO review.")
                self._maybe_start_engineering()
            else:
                self.product_revision_cycles += 1
                self._record_decision("request_product_revision", review["feedback"])
                self.send_message(
                    to_agent="product",
                    message_type="revision_request",
                    payload={
                        "idea": self.startup_idea,
                        "focus": self.decomposition["product"]["focus"],
                        "feedback": review["feedback"],
                    },
                    parent_message_id=message.message_id,
                )
            return

        if message.from_agent == "engineer" and message.message_type == "result":
            self.engineer_result = message.payload
            self._record_decision("receive_engineer_output", "Engineering delivered an HTML page, issue, and PR metadata.")
            self._maybe_start_marketing()
            if self.include_qa and self.marketing_result:
                self._maybe_start_qa()
            elif self.marketing_result:
                self._finalize()
            return

        if message.from_agent == "marketing" and message.message_type == "result":
            self.marketing_result = message.payload
            self._record_decision("receive_marketing_output", "Marketing delivered launch copy and platform actions.")
            if self.include_qa:
                self._maybe_start_qa()
            elif self.engineer_result:
                self._finalize()
            return

        if message.from_agent == "qa" and message.message_type == "result":
            self.qa_result = message.payload
            approved, reason = self._review_qa_report(message.payload["review"])
            self._record_decision("review_qa_report", reason)
            if approved or self.qa_revision_cycles >= 1:
                self._finalize()
                return

            self.qa_revision_cycles += 1
            issues = message.payload["review"]["issues"]
            feedback = " ".join(issues) if issues else "Address QA concerns."
            self.qa_started = False
            self.send_message(
                to_agent="engineer",
                message_type="revision_request",
                payload={
                    "product_spec": self.product_spec,
                    "feedback": feedback,
                },
                parent_message_id=message.message_id,
            )
            return
