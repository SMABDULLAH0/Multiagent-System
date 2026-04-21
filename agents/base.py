from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from message_bus import AgentMessage, MessageBus


class BaseAgent:
    def __init__(
        self,
        *,
        name: str,
        bus: MessageBus,
        llm,
        output_dir: Path,
    ) -> None:
        self.name = name
        self.bus = bus
        self.llm = llm
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, payload: dict[str, Any] | None = None) -> None:
        print(f"[{self.name.upper()}] {message}")
        if payload:
            print(json.dumps(payload, indent=2))

    def send_message(
        self,
        *,
        to_agent: str,
        message_type: str,
        payload: dict[str, Any],
        parent_message_id: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage.create(
            from_agent=self.name,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            parent_message_id=parent_message_id,
        )
        self.bus.send(message)
        self.log(f"Sent {message_type} message to {to_agent}", message.to_dict())
        return message

    def process_pending(self) -> bool:
        inbox = self.bus.pop_all(self.name)
        if not inbox:
            return False
        for message in inbox:
            self.log(f"Received {message.message_type} from {message.from_agent}", message.to_dict())
            self.handle_message(message)
        return True

    def handle_message(self, message: AgentMessage) -> None:
        raise NotImplementedError

