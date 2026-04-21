# LaunchMind

LaunchMind is a multi-agent startup simulation built for the FAST Agentic AI / Multi-Agent Systems assignment. The system turns a startup idea into a product spec, a landing page pull request, launch messaging, and a final executive summary through a team of collaborating agents.

The codebase is designed to run in two modes:
- Dry-run mode for local development without API keys
- Live mode for the real assignment deliverables on GitHub, Slack, and SendGrid

## Startup Idea

The default idea is a campus marketplace for second-hand textbooks with trust signals based on verified university identities. The idea is configurable at runtime through `--idea` or `STARTUP_IDEA`.

## Live Links

- Repository: [SMABDULLAH0/Multiagent-System](https://github.com/SMABDULLAH0/Multiagent-System)
- GitHub issue created by the workflow: [Issue #1](https://github.com/SMABDULLAH0/Multiagent-System/issues/1)
- GitHub pull request created by the workflow: [PR #2](https://github.com/SMABDULLAH0/Multiagent-System/pull/2)
- Slack workspace output: posted in `#launches`
- Email test inbox: `smabdullah.ds@gmail.com`

The repo also contains a later rerun issue (`#3`) from before the GitHub idempotency fix was tightened. Future reruns now reuse the existing PR and the oldest matching issue instead of creating a fresh one each time.

## Agent Architecture

- `CEOAgent` decomposes the startup idea, reviews outputs, requests revisions, and posts a final summary.
- `ProductAgent` produces the product specification in structured JSON.
- `EngineerAgent` generates a landing page, creates a GitHub issue, commits `index.html`, and opens a pull request.
- `MarketingAgent` creates launch copy, sends an email, and posts a Slack launch message with Block Kit.
- `QAAgent` reviews the landing page and marketing outputs, posts GitHub review comments, and can force a revision loop.

The agents communicate over a shared in-memory message bus using the required JSON schema:
- `message_id`
- `from_agent`
- `to_agent`
- `message_type`
- `payload`
- `timestamp`
- `parent_message_id`

## Repository Structure

- `agents/` individual agent implementations
- `main.py` single entry point
- `message_bus.py` structured agent messaging and history log
- `integrations.py` GitHub, Slack, and SendGrid REST clients
- `llm.py` LLM wrapper with deterministic fallback behavior
- `.env.example` environment variable template
- `.gitignore` excludes `.env`

## Setup

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Fill in the real platform credentials:
   - `OPENAI_API_KEY` or `GEMINI_API_KEY`
   - `GITHUB_TOKEN`
   - `GITHUB_REPOSITORY`
   - `SLACK_BOT_TOKEN`
   - `SLACK_CHANNEL`
   - `SENDGRID_API_KEY`
   - `SENDGRID_FROM_EMAIL`
   - `SENDGRID_TO_EMAIL`
4. Run the system:

```bash
python main.py
```

Or provide a custom startup idea:

```bash
python main.py --idea "A browser extension that summarizes long articles before you read them"
```

## Real Platform Actions

- GitHub: the Engineer agent creates an issue, pushes `index.html` to a new branch, and opens a pull request.
- Slack: the Marketing agent posts a launch message and the CEO agent posts a final summary.
- Email: the Marketing agent sends a cold outreach email to a controlled inbox using SendGrid.

## Demo Artifacts

Each run writes the following into `artifacts/`:
- `index.html`
- `message_history.json`
- `decision_log.json`
- `final_summary.json`

## Assignment Notes

- `LAUNCHMIND_FORCE_FEEDBACK_LOOP=true` ensures there is at least one visible CEO revision cycle during demos.
- Set `ENABLE_QA_AGENT=true` to use the bonus QA flow for a 2-person group or the required QA flow for a 3-person group.
- Replace the placeholder startup idea and add your actual repository, Slack workspace link or screenshots, and PR URL before submission.
