from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from message_bus import AgentMessage


class ProductAgent(BaseAgent):
    def _fallback_spec(self, idea: str) -> dict[str, Any]:
        idea_name = idea.strip().rstrip(".")
        return {
            "value_proposition": f"{idea_name} helps students save time, reduce trust friction, and complete transactions with more confidence.",
            "personas": [
                {"name": "Areeba", "role": "University student", "pain_point": "She needs affordable academic resources without wasting time in unreliable WhatsApp groups."},
                {"name": "Hamza", "role": "Recent graduate seller", "pain_point": "He wants a quick way to sell old study material to verified campus buyers."},
                {"name": "Sana", "role": "Society lead", "pain_point": "She wants trusted recommendations and less spam when helping juniors find resources."},
            ],
            "features": [
                {"name": "Verified campus profiles", "description": "Restrict accounts to university email users for safer transactions.", "priority": 1},
                {"name": "Smart search and filters", "description": "Filter by course code, subject, price, and condition.", "priority": 2},
                {"name": "Quick listing flow", "description": "Let sellers post an item with photos and pricing in under a minute.", "priority": 3},
                {"name": "In-app chat prompts", "description": "Help buyers and sellers negotiate with suggested messages.", "priority": 4},
                {"name": "Trust signals", "description": "Show response rate, repeat transactions, and verification badges.", "priority": 5},
            ],
            "user_stories": [
                "As a student buyer, I want to search by course code so that I can find the exact book I need quickly.",
                "As a student seller, I want to create a listing in under a minute so that I can sell unused material without friction.",
                "As a cautious first-time user, I want verified campus identities so that I feel safe meeting and paying another student.",
            ],
        }

    def _build_spec(self, idea: str, focus: str, feedback: str | None) -> dict[str, Any]:
        system_prompt = (
            "You are a product manager. Return only JSON with keys: "
            "value_proposition, personas, features, user_stories."
        )
        user_prompt = (
            f"Startup idea: {idea}\n"
            f"Focus areas: {focus}\n"
            f"Revision feedback: {feedback or 'None'}\n"
            "Requirements:\n"
            "- value_proposition: one sentence\n"
            "- personas: 2 or 3 objects with name, role, pain_point\n"
            "- features: 5 objects with name, description, priority (1 highest)\n"
            "- user_stories: 3 strings in 'As a / I want / so that' format\n"
            "Return valid JSON only."
        )
        return self.llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=lambda: self._fallback_spec(idea),
        )

    def handle_message(self, message: AgentMessage) -> None:
        if message.message_type not in {"task", "revision_request"}:
            return

        idea = message.payload["idea"]
        focus = message.payload.get("focus", "Define personas, features, and user stories.")
        feedback = message.payload.get("feedback")
        product_spec = self._build_spec(idea, focus, feedback)

        self.send_message(
            to_agent="ceo",
            message_type="result",
            payload={
                "product_spec": product_spec,
                "status": "ready",
            },
            parent_message_id=message.message_id,
        )

        self.send_message(
            to_agent="engineer",
            message_type="confirmation",
            payload={"status": "product_spec_ready"},
            parent_message_id=message.message_id,
        )

        self.send_message(
            to_agent="marketing",
            message_type="confirmation",
            payload={"status": "product_spec_ready"},
            parent_message_id=message.message_id,
        )
