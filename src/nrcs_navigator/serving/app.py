"""FastAPI serving app exposing the agent over HTTP.

Lets a client hold a multi turn conversation with the
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

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nrcs_navigator import config
from nrcs_navigator.agent.graph import build_agent

# The agent is built once on startup and reused across requests (it holds the
# Postgres checkpointer connection). Stored on app.state via the lifespan below.
_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the agent once when the process starts, before serving requests.

    build_agent attaches the Postgres checkpointer, so conversation state for a
    session_id persists across requests (and across worker processes, since the
    state lives in the shared database, not in memory).
    """
    global _agent
    _agent = build_agent(config.PREMIER_MODEL)
    yield


app = FastAPI(title="NRCS Program Navigator", lifespan=lifespan)

# The browser frontend calls this API cross origin. Allow the deployed frontend
# origin plus localhost for development. Set FRONTEND_ORIGINS in the environment
# as a comma separated list once the Vercel URL is known.
_origins = [
    o.strip()
    for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@app.get("/health")
def health() -> dict:
    """Liveness check. Intentionally cheap: no database or LLM call, so the
    keep-warm ping that hits this every few minutes costs nothing.
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Thread one user message through the agent under the given session_id.

    The thread_id is the session_id, so the checkpointer resumes the same
    conversation (the elicitation flow and elicited client profile) on every
    call with that id. A new session_id starts a fresh conversation.
    """
    result = _agent.invoke(
        {"messages": [("user", req.message)]},
        config={"configurable": {"thread_id": req.session_id}},
    )
    reply = result["messages"][-1].content
    return ChatResponse(session_id=req.session_id, reply=reply)
