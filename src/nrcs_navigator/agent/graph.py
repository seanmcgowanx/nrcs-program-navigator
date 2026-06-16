"""LangGraph ReAct agent assembly.

Wires the chosen LLM together with the tools into a Reason / Act / Observe loop
via LangGraph's prebuilt create_react_agent. The LLM decides which tool to call
at each step based on context; nothing is hard coded into a sequence. Out of
scope handling is not a tool; it lives in the system prompt (agent/prompts.py).

build_agent(model_name) gets the model from agent/llms.py, binds the tools,
applies the system prompt, and attaches a Postgres checkpointer so conversation
state (the message history, and with it the elicited client profile) persists in
the same database as the payments and embeddings, keyed by thread_id. Because
model_name is a parameter, the evaluation harness builds the same agent on two
models for a side by side comparison.

The checkpointer is Postgres rather than an in memory saver so conversation
state survives process restarts and is shared across a stateless serving layer's
workers (a later request can land on a different process than the first). See the
persistence decision in docs/architecture.md. Checkpoints are not removed by the
checkpointer itself, so a retention policy lives alongside it: the serving app
runs a background sweep (agent/cleanup.py) that deletes threads idle past
config.CHECKPOINT_RETENTION_DAYS, keeping the shared database bounded.

Tracing is handled by LangSmith automatically when the environment variables are
set; no explicit logging code is required here.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from nrcs_navigator.agent import llms, prompts
from nrcs_navigator.data import db
from nrcs_navigator.tools.eligibility_screener import eligibility_screener
from nrcs_navigator.tools.payment_estimator import payment_estimator
from nrcs_navigator.tools.practice_matcher import practice_matcher
from nrcs_navigator.tools.program_availability import program_availability


# The tools bound to the agent. Add practice_matcher, payment_estimator, and
# program_availability here as they are implemented -- build_agent needs no other
# change for the agent to start reasoning over them.
TOOLS = [eligibility_screener, payment_estimator, practice_matcher, program_availability]


def _checkpointer() -> PostgresSaver:
    """A LangGraph Postgres checkpointer on the shared database.

    Backed by a connection pool rather than a single long-lived connection. The
    database is serverless (Neon), so it drops idle connections and suspends
    compute between requests; a single connection opened at startup goes stale
    while a user reads a reply, and the next message then hangs on a half-open
    socket. The pool checks each connection before lending it (reconnecting dead
    ones) and recycles idle connections before the server would drop them, so a
    later message in a conversation reconnects transparently. The pool also gives
    each request in FastAPI's threadpool its own connection, since a psycopg
    connection is not safe to share across threads.

    autocommit, prepare_threshold=0, and dict_row are what PostgresSaver expects
    of its connections; setup() creates the checkpoint tables on first use and is
    idempotent thereafter.
    """
    pool = ConnectionPool(
        conninfo=db.psycopg_url(),
        min_size=1,
        max_size=4,
        # Recycle connections that have been idle longer than this (seconds),
        # comfortably under the serverless idle-drop window.
        max_idle=120,
        # Validate a connection (and reconnect if dead) before handing it out.
        check=ConnectionPool.check_connection,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


def build_agent(model_name: str | None = None):
    """Build the ReAct agent on the given model (defaults to the premier model).

    Returns a runnable LangGraph agent. Invoke it with a messages list and a
    thread_id so the checkpointer can persist and resume the conversation:

        agent.invoke(
            {"messages": [("user", "...")]},
            config={"configurable": {"thread_id": "session-1"}},
        )
    """
    model = llms.get_model(model_name)
    return create_react_agent(
        model,
        TOOLS,
        prompt=prompts.SYSTEM_PROMPT,
        checkpointer=_checkpointer(),
    )
