"""FastAPI serving app exposing the agent over HTTP.

Optional for grading. Lets a client hold a multi turn conversation with the
agent the same way the notebooks do, but over a network API.

Intended responsibilities:
    - Build the agent once on startup via agent/graph.build_agent(model_name),
      reusing the Postgres checkpointer so conversation state survives across
      requests.
    - Expose POST /chat that accepts a session_id and a user message, threads
      the call through the agent using that session_id (so the elicitation
      flow and farmer profile persist across calls), and returns the agent's
      reply. Optionally include the intermediate tool steps for debugging.
    - Expose GET /health for a simple liveness check.
    - Read the model name and database settings from config.py; never hard
      code secrets here.

Run locally with: uvicorn nrcs_navigator.serving.app:app --reload

Request and response shapes (illustrative):
    POST /chat  { "session_id": "abc", "message": "I farm 200 acres ..." }
            ->  { "session_id": "abc", "reply": "...", "steps": [...] }

App only. The reasoning lives in agent/graph.py; the tools live in tools/.
"""
