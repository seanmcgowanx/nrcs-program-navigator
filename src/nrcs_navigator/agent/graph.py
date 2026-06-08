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
persistence decision in docs/architecture.md. Note that checkpoints are not
removed automatically, so a production deployment would add a retention policy.

Tracing is handled by LangSmith automatically when the environment variables are
set; no explicit logging code is required here.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from psycopg import Connection
from psycopg.rows import dict_row

from nrcs_navigator.agent import llms, prompts
from nrcs_navigator.data import db
from nrcs_navigator.tools.eligibility_screener import eligibility_screener

# The tools bound to the agent. Add practice_matcher, payment_estimator, and
# deadline_lookup here as they are implemented -- build_agent needs no other
# change for the agent to start reasoning over them.
TOOLS = [eligibility_screener]


def _checkpointer() -> PostgresSaver:
    """A LangGraph Postgres checkpointer on the shared database.

    The saver manages its own checkpoint tables through a raw psycopg connection
    (separate from the SQLAlchemy engine). autocommit and prepare_threshold=0
    are what the saver expects, and dict_row is the row format it reads; setup()
    creates its tables on first use and is idempotent thereafter.
    """
    conn = Connection.connect(
        db.psycopg_url(),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = PostgresSaver(conn)
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
