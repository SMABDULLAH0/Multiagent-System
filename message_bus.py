from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class AgentMessage:
    message_id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict[str, Any]
    timestamp: str
    parent_message_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: dict[str, Any],
        parent_message_id: str | None = None,
    ) -> "AgentMessage":
        return cls(
            message_id=f"msg-{uuid4()}",
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=utc_now_iso(),
            parent_message_id=parent_message_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MessageBus:
    def __init__(self) -> None:
        self._queues: dict[str, list[AgentMessage]] = defaultdict(list)
        self._history: list[AgentMessage] = []

    def send(self, message: AgentMessage) -> None:
        self._queues[message.to_agent].append(message)
        self._history.append(message)

    def pop_all(self, agent_name: str) -> list[AgentMessage]:
        messages = list(self._queues.get(agent_name, []))
        self._queues[agent_name].clear()
        return messages

    def history(self) -> list[dict[str, Any]]:
        return [message.to_dict() for message in self._history]

    def history_for(self, agent_name: str) -> list[dict[str, Any]]:
        return [
            message.to_dict()
            for message in self._history
            if message.from_agent == agent_name or message.to_agent == agent_name
        ]

    def dump_history(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.history(), indent=2), encoding="utf-8")

