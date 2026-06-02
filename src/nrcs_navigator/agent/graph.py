"""LangGraph ReAct agent assembly.

Wires the chosen LLM together with the five tools into a Reason / Act /
Observe loop. The LLM decides which tool to call at each step based on
context; nothing is hard coded into a fixed sequence.

Intended responsibilities:
    - build_agent(model_name): get the model from agent/llms.py, collect the
      five tool objects from the tools package, bind them to the model, and
      construct a LangGraph ReAct graph (for example via a prebuilt ReAct
      agent or a custom StateGraph).
    - Apply the system prompt from agent/prompts.py.
    - Attach the Postgres LangGraph checkpointer (PostgresSaver, built on the
      shared engine from data/db.py) so conversation state persists in the same
      database as the payments and embeddings.
    - Return a runnable agent that accepts a user message and returns the final
      answer plus the intermediate tool steps (so traces capture the reasoning).
    - Because model_name is a parameter, the evaluation harness can build the
      same agent on two different LLMs for side by side comparison.

Tracing is handled by LangSmith automatically once the environment variables
are set; no explicit logging code is required here.
"""
