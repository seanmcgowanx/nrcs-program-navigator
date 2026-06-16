"""FastAPI serving app exposing the agent over HTTP.

Lets a client hold a multi turn conversation with the
agent the same way the notebooks do, but over a network API.

Intended responsibilities:
    - Build the agent once on startup via agent/graph.build_agent_async(
      model_name), reusing the async Postgres checkpointer so conversation state
      survives across requests and tool events can be streamed.
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

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from nrcs_navigator import config
from nrcs_navigator.agent.cleanup import delete_idle_threads
from nrcs_navigator.agent.graph import build_agent_async
from nrcs_navigator.serving import trace

logger = logging.getLogger("nrcs_navigator.serving")

# The agent is built once on startup and reused across requests (it holds the
# Postgres checkpointer connection). Stored on app.state via the lifespan below.
_agent = None


async def _cleanup_loop():
    """Periodically delete conversation threads idle past the retention window.

    Runs a sweep immediately (covering any free-tier spin-down gap) and then once
    every CHECKPOINT_CLEANUP_INTERVAL_HOURS. delete_idle_threads is async (it uses
    the agent's async checkpointer), and a failed sweep is logged and retried next
    interval rather than crashing serving.
    """
    interval = config.CHECKPOINT_CLEANUP_INTERVAL_HOURS * 3600
    while True:
        try:
            removed = await delete_idle_threads(
                _agent.checkpointer,
                config.CHECKPOINT_RETENTION_DAYS,
            )
            logger.info("checkpoint cleanup removed %d idle thread(s)", removed)
        except Exception:
            logger.exception("checkpoint cleanup pass failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the agent once when the process starts, before serving requests.

    build_agent_async attaches an async Postgres checkpointer, so conversation
    state for a session_id persists across requests (and across worker processes,
    since the state lives in the shared database, not in memory) and the serving
    layer can stream per-tool events via astream_events.

    A background task then keeps that checkpointer bounded by deleting threads
    that have been idle past the retention window; both it and the checkpointer's
    connection pool are torn down on shutdown.
    """
    global _agent
    _agent = await build_agent_async(config.PREMIER_MODEL)
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        await _agent.checkpointer.conn.close()


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


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict:
    """Liveness check. Intentionally cheap: no database or LLM call, so the
    keep-warm ping that hits this every few minutes costs nothing.

    Accepts HEAD as well as GET because uptime monitors (the keep-warm pinger)
    default to HEAD on their free tiers; a GET-only route answers those with 405.
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Thread one user message through the agent under the given session_id.

    The thread_id is the session_id, so the checkpointer resumes the same
    conversation (the elicitation flow and elicited client profile) on every
    call with that id. A new session_id starts a fresh conversation.

    Non streaming sibling of /chat/stream, returning only the final reply. Async
    because the agent's checkpointer is async (the streaming path needs it).

    The recursion_limit caps the ReAct loop so a confused agent fails fast rather
    than running up latency. A trip is turned into a plain reply (the user gets
    guidance, not an error bubble); any other failure becomes a 503 so the
    frontend can show its error state and offer a retry.
    """
    try:
        result = await _agent.ainvoke(
            {"messages": [("user", req.message)]},
            config={
                "configurable": {"thread_id": req.session_id},
                "recursion_limit": config.AGENT_RECURSION_LIMIT,
            },
        )
    except GraphRecursionError:
        logger.warning("recursion limit hit for session %s", req.session_id)
        return ChatResponse(
            session_id=req.session_id,
            reply=(
                "I wasn't able to pull this together in time. Try narrowing the "
                "request, for example a single program or one practice, and "
                "include the client's state and operation type."
            ),
        )
    except Exception:
        logger.exception("agent invoke failed for session %s", req.session_id)
        raise HTTPException(
            status_code=503,
            detail="The navigator service hit an error handling that message.",
        )

    reply = result["messages"][-1].content
    return ChatResponse(session_id=req.session_id, reply=reply)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream one turn as newline delimited JSON so the UI can show the agent work.

    Same conversation semantics as /chat (the session_id is the thread_id), but
    instead of returning only the final reply it emits a sequence of trace events
    -- each tool call as it starts, an abbreviated result as that tool finishes,
    then the final answer -- as they happen. See serving/trace.py for the event
    shapes. Errors and the recursion cap are turned into events inside the stream
    rather than HTTP status codes, since the response headers are already sent
    once streaming.

    Each line is a JSON object; the client splits the body on newlines.
    """

    async def body():
        async for event in trace.aiter_agent_events(
            _agent, req.message, req.session_id
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(body(), media_type="application/x-ndjson")
