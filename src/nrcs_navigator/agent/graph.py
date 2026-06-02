"""LangGraph ReAct agent assembly.

Wires the chosen LLM together with the four tools into a Reason / Act /
Observe loop. The LLM decides which tool to call at each step based on
context; nothing is hard coded into a fixed sequence. Out of scope handling
is not a tool; it lives in the system prompt (see agent/prompts.py).

Intended responsibilities:
    - build_agent(model_name): get the model from agent/llms.py, collect the
      four tool objects from the tools package, bind them to the model, and
      construct a LangGraph ReAct graph (for example via a prebuilt ReAct
      agent or a custom StateGraph).
    - Apply the system prompt from agent/prompts.py (role, scope guard, and
      the elicitation flow that gathers the farmer profile across turns).
    - Attach the Postgres LangGraph checkpointer (PostgresSaver, built on the
      shared engine from data/db.py) so conversation state persists in the same
      database as the payments and embeddings.
    - Return a runnable agent that accepts a user message and returns the final
      answer plus the intermediate tool steps (so traces capture the reasoning).
    - Because model_name is a parameter, the evaluation harness can build the
      same agent on two different LLMs for side by side comparison.

State schema (what the checkpointer persists, keyed by session / thread ID):
    - Message history: the running conversation between farmer and agent.
    - Accumulated farmer profile: the elicited fields (state and county,
      acreage, current practices, primary resource concern) so the agent does
      not re ask across turns.
    - Cached scrape results: practice standards and ranking dates fetched
      during the session, reused so the live scrape tools are not hit twice
      for the same data within a conversation.

Tracing is handled by LangSmith automatically once the environment variables
are set; no explicit logging code is required here.
"""
