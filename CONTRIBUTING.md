# Contributing

This is a portfolio demo by Birra Gemedi. If you are forking it:

1. Copy `.env.example` to `.env`. Do not commit secrets.
2. Keep `AI_PROVIDER=heuristic` unless you intentionally want Ollama or OpenAI.
3. Run tests before opening a PR: `.venv/bin/pytest -q`
4. Keep API keys, Slack webhooks, and customer data out of source and fixtures. The n8n workflow must keep using `$env.OPS_AGENT_API_KEY`, not a pasted key.
5. Prefer small, readable changes over new abstraction layers.

Python 3.12 is the Docker and CI baseline.
