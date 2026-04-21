from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from agents import CEOAgent, EngineerAgent, MarketingAgent, ProductAgent, QAAgent
from config import env_flag, load_dotenv_if_present
from integrations import GitHubClient, SendGridClient, SlackClient
from llm import LLMClient
from message_bus import MessageBus


class LaunchMindApp:
    def __init__(self, startup_idea: str) -> None:
        load_dotenv_if_present()
        output_dir = Path(os.getenv("OUTPUT_DIR", "artifacts"))

        self.bus = MessageBus()
        self.llm = LLMClient()
        self.github = GitHubClient()
        self.slack = SlackClient()
        self.sendgrid = SendGridClient()
        self.output_dir = output_dir
        self.startup_idea = startup_idea
        include_qa = env_flag("ENABLE_QA_AGENT", True)

        self.agents = [
            CEOAgent(
                name="ceo",
                bus=self.bus,
                llm=self.llm,
                output_dir=output_dir,
                slack=self.slack,
                include_qa=include_qa,
            ),
            ProductAgent(
                name="product",
                bus=self.bus,
                llm=self.llm,
                output_dir=output_dir,
            ),
            EngineerAgent(
                name="engineer",
                bus=self.bus,
                llm=self.llm,
                output_dir=output_dir,
                github=self.github,
            ),
            MarketingAgent(
                name="marketing",
                bus=self.bus,
                llm=self.llm,
                output_dir=output_dir,
                slack=self.slack,
                sendgrid=self.sendgrid,
            ),
        ]
        if include_qa:
            self.agents.append(
                QAAgent(
                    name="qa",
                    bus=self.bus,
                    llm=self.llm,
                    output_dir=output_dir,
                    github=self.github,
                )
            )

        self.ceo = self.agents[0]

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ceo.bootstrap(self.startup_idea)

        for _ in range(25):
            progress = False
            for agent in self.agents:
                progress = agent.process_pending() or progress
            if self.ceo.completed:
                break
            if not progress:
                break

        self.bus.dump_history(self.output_dir / "message_history.json")

        summary = {
            "completed": self.ceo.completed,
            "output_dir": str(self.output_dir.resolve()),
            "message_history": str((self.output_dir / "message_history.json").resolve()),
        }
        print("[SYSTEM] Run summary")
        print(json.dumps(summary, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LaunchMind multi-agent startup simulator.")
    parser.add_argument(
        "--idea",
        default=os.getenv(
            "STARTUP_IDEA",
            "A platform where students buy and sell second-hand textbooks with campus-only trust signals.",
        ),
        help="Startup idea to execute.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    LaunchMindApp(args.idea).run()

